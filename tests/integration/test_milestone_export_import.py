# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import io

import pytest

from django.urls import reverse
from django.utils import timezone

from taiga.base.utils import json
from taiga.export_import import services
from taiga.export_import.services import render_project
from taiga.projects.milestones.models import GoalAchievement, OBJETIVO_IMPORTACAO

from .. import factories as f


pytestmark = pytest.mark.django_db


RESULT_DATE = "2026-09-01T10:00:00+0000"


def _project_with_admin():
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_admin=True)
    return user, project


def _export(project):
    output = io.BytesIO()
    render_project(project, output)
    return json.loads(output.getvalue())


def _milestone_dump(**extra):
    data = {
        "name": "Sprint importada",
        "estimated_start": "2026-09-01",
        "estimated_finish": "2026-09-15",
    }
    data.update(extra)
    return data


#######################################################
## exportação
#######################################################

def test_export_closed_milestone_with_result(client):
    user, project = _project_with_admin()
    result_by = f.UserFactory.create(email="registrou-export@example.com")
    f.MilestoneFactory.create(project=project, owner=user, name="Sprint fechada", closed=True,
                              goal="Entregar o login", goal_achievement=GoalAchievement.ACHIEVED,
                              result="Login entregue", result_date=RESULT_DATE, result_by=result_by)

    project_data = _export(project)

    milestone = project_data["milestones"][0]
    assert milestone["goal"] == "Entregar o login"
    assert milestone["goal_achievement"] == "achieved"
    assert milestone["result"] == "Login entregue"
    assert milestone["result_date"] == RESULT_DATE
    assert milestone["result_by"] == "registrou-export@example.com"


def test_export_open_milestone_without_result(client):
    user, project = _project_with_admin()
    f.MilestoneFactory.create(project=project, owner=user, name="Sprint aberta", goal="Objetivo aberto")

    project_data = _export(project)

    milestone = project_data["milestones"][0]
    assert milestone["goal"] == "Objetivo aberto"
    assert milestone["goal_achievement"] is None
    assert milestone["result"] is None
    assert milestone["result_date"] is None
    assert milestone["result_by"] is None


#######################################################
## importação via dump de projeto
#######################################################

def test_import_dump_recreates_milestone_result_fields(client):
    owner = f.UserFactory.create()
    # E-mail próprio do teste: o importador guarda usuário por e-mail em cache de processo.
    result_by = f.UserFactory.create(email="registrou-dump@example.com")
    data = {
        "name": "Imported project",
        "description": "Imported project",
        "milestones": [_milestone_dump(
            goal="Entregar o login",
            closed=True,
            goal_achievement="partially_achieved",
            result="Login entregue sem MFA",
            result_date=RESULT_DATE,
            result_by="registrou-dump@example.com",
        )],
    }

    project = services.store_project_from_dict(data, owner=owner)

    milestone = project.milestones.get()
    assert milestone.goal == "Entregar o login"
    assert milestone.goal_achievement == GoalAchievement.PARTIALLY_ACHIEVED
    assert milestone.result == "Login entregue sem MFA"
    assert milestone.result_date == timezone.datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    assert milestone.result_by == result_by


def test_import_dump_with_unknown_result_by_leaves_it_null(client):
    owner = f.UserFactory.create()
    data = {
        "name": "Imported project",
        "description": "Imported project",
        "milestones": [_milestone_dump(
            goal="Entregar o login",
            closed=True,
            goal_achievement="not_achieved",
            result="Não entregue",
            result_date=RESULT_DATE,
            result_by="ninguem@example.com",
        )],
    }

    project = services.store_project_from_dict(data, owner=owner)

    milestone = project.milestones.get()
    assert milestone.goal_achievement == GoalAchievement.NOT_ACHIEVED
    assert milestone.result == "Não entregue"
    assert milestone.result_by is None


def test_import_dump_without_goal_uses_fixed_text(client):
    owner = f.UserFactory.create()
    data = {
        "name": "Imported project",
        "description": "Imported project",
        "milestones": [_milestone_dump()],
    }

    project = services.store_project_from_dict(data, owner=owner)

    milestone = project.milestones.get()
    assert milestone.goal == OBJETIVO_IMPORTACAO
    assert milestone.goal_achievement is None
    assert milestone.result is None
    assert milestone.result_date is None
    assert milestone.result_by is None


def test_export_then_import_round_trip_keeps_milestone_result(client):
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    role = f.RoleFactory.create(project=project)
    f.MembershipFactory.create(project=project, user=user, role=role, is_admin=True)
    result_by = f.UserFactory.create(email="registrou-roundtrip@example.com")
    f.MilestoneFactory.create(project=project, owner=user, name="Sprint fechada", closed=True,
                              goal="Entregar o login", goal_achievement=GoalAchievement.ACHIEVED,
                              result="Login entregue", result_date=RESULT_DATE, result_by=result_by)
    project_data = _export(project)
    project_data["name"] = "Projeto reimportado"
    project_data["slug"] = "projeto-reimportado"

    imported = services.store_project_from_dict(project_data, owner=user)

    assert imported.pk != project.pk
    milestone = imported.milestones.get()
    assert milestone.goal == "Entregar o login"
    assert milestone.goal_achievement == GoalAchievement.ACHIEVED
    assert milestone.result == "Login entregue"
    assert milestone.result_date == timezone.datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    assert milestone.result_by == result_by


#######################################################
## importação via api/v1/importer/<project>/milestone
#######################################################

def test_milestone_import_with_invalid_goal_achievement_is_rejected(client):
    user, project = _project_with_admin()
    client.login(user)

    url = reverse("importer-milestone", args=[project.pk])
    data = _milestone_dump(goal="Objetivo", goal_achievement="quase", result="Resultado")

    response = client.json.post(url, json.dumps(data))
    assert response.status_code == 400
    assert "goal_achievement" in response.data["milestones"][0]
    assert project.milestones.count() == 0


def test_milestone_import_with_goal_achievement_without_result_is_rejected(client):
    user, project = _project_with_admin()
    client.login(user)

    url = reverse("importer-milestone", args=[project.pk])
    data = _milestone_dump(goal="Objetivo", goal_achievement="achieved")

    response = client.json.post(url, json.dumps(data))
    assert response.status_code == 400
    assert "goal_achievement" in response.data["milestones"][0]
    assert project.milestones.count() == 0


def test_milestone_import_with_result_in_open_sprint_is_accepted(client):
    user, project = _project_with_admin()
    client.login(user)

    url = reverse("importer-milestone", args=[project.pk])
    data = _milestone_dump(goal="Objetivo", closed=False, goal_achievement="achieved",
                           result="Resultado registrado e sprint reaberta", result_date=RESULT_DATE)

    response = client.json.post(url, json.dumps(data))
    assert response.status_code == 201
    assert response.data["goal_achievement"] == "achieved"
    assert response.data["result"] == "Resultado registrado e sprint reaberta"
    assert response.data["result_date"] == RESULT_DATE
    assert response.data["result_by"] is None
    milestone = project.milestones.get()
    assert milestone.closed is False
    assert milestone.goal_achievement == GoalAchievement.ACHIEVED
