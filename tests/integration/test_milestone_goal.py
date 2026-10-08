# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import importlib

import pytest

from django.apps import apps
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from taiga.base.utils import json
from taiga.projects.milestones.models import GoalAchievement, Milestone, RESULTADO_LEGADO

from .. import factories as f


pytestmark = pytest.mark.django_db

migration_0005 = importlib.import_module(
    "taiga.projects.milestones.migrations.0005_milestone_legacy_result")


def _project_with_admin():
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    role = f.RoleFactory.create(project=project)
    f.MembershipFactory.create(project=project, user=user, role=role, is_admin=True)
    return user, project


def _member_with_modify_milestone(project):
    member = f.UserFactory.create()
    role = f.RoleFactory.create(project=project,
                                permissions=["view_milestones", "modify_milestone"])
    f.MembershipFactory.create(project=project, user=member, role=role, is_admin=False)
    return member


def _sprint_payload(project, **extra):
    payload = {
        "name": "Sprint 1",
        "estimated_start": "2026-09-01",
        "estimated_finish": "2026-09-15",
        "project": project.pk,
    }
    payload.update(extra)
    return payload


def test_create_milestone_without_goal_is_rejected(client):
    user, project = _project_with_admin()
    url = reverse("milestones-list")

    client.login(user)
    response = client.json.post(url, json.dumps(_sprint_payload(project)))

    assert response.status_code == 400
    assert "goal" in response.data
    assert Milestone.objects.filter(project=project).count() == 0


def test_create_milestone_with_blank_goal_is_rejected(client):
    user, project = _project_with_admin()
    url = reverse("milestones-list")

    client.login(user)
    response_empty = client.json.post(url, json.dumps(_sprint_payload(project, goal="")))
    response_spaces = client.json.post(url, json.dumps(_sprint_payload(project, goal="   ")))

    assert response_empty.status_code == 400
    assert "goal" in response_empty.data
    assert response_spaces.status_code == 400
    assert "goal" in response_spaces.data
    assert Milestone.objects.filter(project=project).count() == 0


def test_create_milestone_with_goal_returns_it(client):
    user, project = _project_with_admin()
    url = reverse("milestones-list")

    client.login(user)
    response = client.json.post(url, json.dumps(_sprint_payload(project, goal="Entregar o login")))

    assert response.status_code == 201, response.data
    assert response.data["goal"] == "Entregar o login"
    assert Milestone.objects.get(pk=response.data["id"]).goal == "Entregar o login"


def test_patch_goal_by_member_with_modify_milestone_is_rejected(client):
    user, project = _project_with_admin()
    member = _member_with_modify_milestone(project)
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Objetivo original")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(member)
    response = client.json.patch(url, json.dumps({"goal": "Objetivo alterado"}))

    assert response.status_code == 400
    assert "goal" in response.data
    sprint.refresh_from_db()
    assert sprint.goal == "Objetivo original"


def test_patch_goal_by_project_admin_is_rejected(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Objetivo original")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.patch(url, json.dumps({"goal": "Objetivo alterado"}))

    assert response.status_code == 400
    assert "goal" in response.data
    sprint.refresh_from_db()
    assert sprint.goal == "Objetivo original"


def test_patch_goal_by_superuser_is_rejected(client):
    user, project = _project_with_admin()
    superuser = f.UserFactory.create(is_superuser=True)
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Objetivo original")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(superuser)
    response = client.json.patch(url, json.dumps({"goal": "Objetivo alterado"}))

    assert response.status_code == 400
    assert "goal" in response.data
    sprint.refresh_from_db()
    assert sprint.goal == "Objetivo original"


def test_patch_dates_without_goal_keeps_goal(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Objetivo original")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.patch(url, json.dumps({
        "estimated_start": "2026-10-01",
        "estimated_finish": "2026-10-15",
    }))

    assert response.status_code == 200, response.data
    sprint.refresh_from_db()
    assert sprint.goal == "Objetivo original"
    assert str(sprint.estimated_start) == "2026-10-01"


def test_put_with_same_goal_is_accepted(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Objetivo original")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.put(url, json.dumps(_sprint_payload(
        project, name="Sprint renomeada", goal="Objetivo original")))

    assert response.status_code == 200, response.data
    sprint.refresh_from_db()
    assert sprint.goal == "Objetivo original"
    assert sprint.name == "Sprint renomeada"


def test_get_milestone_returns_goal_and_result_fields(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user, goal="Entregar o login")
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.get(url)

    assert response.status_code == 200
    assert response.data["goal"] == "Entregar o login"
    assert response.data["goal_achievement"] is None
    assert response.data["result"] is None
    assert response.data["result_date"] is None
    assert response.data["result_by"] is None


def test_get_milestone_returns_registered_result(client):
    user, project = _project_with_admin()
    when = timezone.now()
    sprint = f.MilestoneFactory.create(project=project, owner=user, closed=True,
                                       goal_achievement=GoalAchievement.ACHIEVED,
                                       result="Tudo entregue", result_date=when, result_by=user)
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.get(url)

    assert response.status_code == 200
    assert response.data["goal_achievement"] == "achieved"
    assert response.data["result"] == "Tudo entregue"
    assert response.data["result_date"] is not None
    assert response.data["result_by"] == user.id


def test_patch_milestone_ignores_result_fields(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user)
    url = reverse("milestones-detail", args=[sprint.pk])

    client.login(user)
    response = client.json.patch(url, json.dumps({
        "goal_achievement": "achieved",
        "result": "tentativa pela API",
        "result_date": timezone.now().isoformat(),
        "result_by": user.id,
    }))

    assert response.status_code == 200
    sprint.refresh_from_db()
    assert sprint.goal_achievement is None
    assert sprint.result is None
    assert sprint.result_date is None
    assert sprint.result_by is None


def test_achievement_without_result_is_rejected_by_database():
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Milestone.objects.filter(pk=sprint.pk).update(goal_achievement=GoalAchievement.ACHIEVED)


def test_migration_0005_fills_legacy_result_only_on_closed_milestones():
    user, project = _project_with_admin()
    closed = f.MilestoneFactory.create(project=project, owner=user, closed=True)
    opened = f.MilestoneFactory.create(project=project, owner=user, closed=False)
    closed_with_result = f.MilestoneFactory.create(project=project, owner=user, closed=True,
                                                   result="Resultado já registrado")

    migration_0005.preencher_resultado_legado(apps, None)

    closed.refresh_from_db()
    opened.refresh_from_db()
    closed_with_result.refresh_from_db()
    assert closed.result == RESULTADO_LEGADO
    assert closed.goal_achievement is None
    assert closed.result_date is None
    assert closed.result_by is None
    assert opened.result is None
    assert closed_with_result.result == "Resultado já registrado"


def test_migration_0005_reverse_clears_only_legacy_result():
    user, project = _project_with_admin()
    legacy = f.MilestoneFactory.create(project=project, owner=user, closed=True,
                                       result=RESULTADO_LEGADO)
    real = f.MilestoneFactory.create(project=project, owner=user, closed=True,
                                     result="Resultado real")

    migration_0005.limpar_resultado_legado(apps, None)

    legacy.refresh_from_db()
    real.refresh_from_db()
    assert legacy.result is None
    assert real.result == "Resultado real"
