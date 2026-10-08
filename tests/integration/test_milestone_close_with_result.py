# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import pytest

from django.urls import reverse

from taiga.base.utils import json
from taiga.projects.milestones.models import GoalAchievement, Milestone

from .. import factories as f


pytestmark = pytest.mark.django_db


def _project_with_admin():
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    role = f.RoleFactory.create(project=project)
    f.MembershipFactory.create(project=project, user=user, role=role, is_admin=True)
    return user, project


def _member_with_permissions(project, permissions):
    member = f.UserFactory.create()
    role = f.RoleFactory.create(project=project, permissions=permissions)
    f.MembershipFactory.create(project=project, user=member, role=role, is_admin=False)
    return member


def _sprints(project, owner):
    sprint = f.MilestoneFactory.create(project=project, owner=owner, name="Sprint 1")
    destination = f.MilestoneFactory.create(project=project, owner=owner, name="Sprint 2")
    return sprint, destination


def _closed_and_open_userstories(project, owner, sprint):
    closed_status = f.UserStoryStatusFactory.create(project=project, is_closed=True)
    open_status = f.UserStoryStatusFactory.create(project=project, is_closed=False)
    closed_us = f.create_userstory(project=project, owner=owner, milestone=sprint,
                                   status=closed_status, sprint_order=1)
    open_us = f.create_userstory(project=project, owner=owner, milestone=sprint,
                                 status=open_status, sprint_order=2)
    return closed_us, open_us


def _payload(**extra):
    payload = {"goal_achievement": "achieved", "result": "Login entregue"}
    payload.update(extra)
    return payload


def _url(sprint):
    return reverse("milestones-close-with-result", kwargs={"pk": sprint.pk})


def _assert_nothing_registered(sprint):
    sprint.refresh_from_db()
    assert sprint.closed is False
    assert sprint.goal_achievement is None
    assert sprint.result is None
    assert sprint.result_date is None
    assert sprint.result_by is None


# Fluxos válidos

def test_close_with_result_moves_open_userstory_closes_sprint_and_registers_result(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 200, response.data
    assert response.data["closed"] is True
    assert response.data["goal_achievement"] == "achieved"
    assert response.data["result"] == "Login entregue"
    assert response.data["result_date"] is not None
    assert response.data["result_by"] == user.pk

    sprint.refresh_from_db()
    closed_us.refresh_from_db()
    open_us.refresh_from_db()
    assert sprint.closed is True
    assert sprint.goal_achievement == GoalAchievement.ACHIEVED
    assert sprint.result == "Login entregue"
    assert sprint.result_date is not None
    assert sprint.result_by == user
    assert closed_us.milestone_id == sprint.pk
    assert open_us.milestone_id == destination.pk


def test_close_with_result_without_open_items_only_registers(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user)
    closed_status = f.UserStoryStatusFactory.create(project=project, is_closed=True)
    f.create_userstory(project=project, owner=user, milestone=sprint, status=closed_status)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(goal_achievement="partially_achieved",
                                                                  result="  Metade entregue  ")))

    assert response.status_code == 200, response.data
    sprint.refresh_from_db()
    assert sprint.closed is True
    assert sprint.goal_achievement == GoalAchievement.PARTIALLY_ACHIEVED
    assert sprint.result == "Metade entregue"
    assert sprint.result_by == user


def test_close_with_result_moves_open_task_without_story_and_open_issue(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)
    open_task_status = f.TaskStatusFactory.create(project=project, is_closed=False)
    closed_task_status = f.TaskStatusFactory.create(project=project, is_closed=True)
    open_task = f.create_task(project=project, owner=user, milestone=sprint, user_story=None,
                              status=open_task_status, taskboard_order=1)
    closed_task = f.create_task(project=project, owner=user, milestone=sprint, user_story=None,
                                status=closed_task_status, taskboard_order=2)
    open_issue_status = f.IssueStatusFactory.create(project=project, is_closed=False)
    closed_issue_status = f.IssueStatusFactory.create(project=project, is_closed=True)
    open_issue = f.create_issue(project=project, owner=user, milestone=sprint, status=open_issue_status)
    closed_issue = f.create_issue(project=project, owner=user, milestone=sprint, status=closed_issue_status)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 200, response.data
    for item in (open_us, open_task, open_issue):
        item.refresh_from_db()
        assert item.milestone_id == destination.pk
    for item in (closed_us, closed_task, closed_issue):
        item.refresh_from_db()
        assert item.milestone_id == sprint.pk
    sprint.refresh_from_db()
    assert sprint.closed is True
    assert sprint.result == "Login entregue"


# Payload inválido

@pytest.mark.parametrize("payload, key", [
    ({"result": "Login entregue"}, "goal_achievement"),
    ({"goal_achievement": "achieved"}, "result"),
    ({"goal_achievement": "achieved", "result": "   "}, "result"),
    ({"goal_achievement": "almost", "result": "Login entregue"}, "goal_achievement"),
])
def test_close_with_result_with_invalid_payload_is_rejected(client, payload, key):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)
    payload["milestone_id"] = destination.pk

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(payload))

    assert response.status_code == 400
    assert key in response.data
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_without_any_closed_activity_is_rejected(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    open_status = f.UserStoryStatusFactory.create(project=project, is_closed=False)
    open_us = f.create_userstory(project=project, owner=user, milestone=sprint, status=open_status)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 400
    assert "_error_message" in response.data
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_with_open_items_and_no_destination_is_rejected(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload()))

    assert response.status_code == 400
    assert "milestone_id" in response.data
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_to_closed_destination_is_rejected(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    Milestone.objects.filter(pk=destination.pk).update(closed=True)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 400
    assert "milestone_id" in response.data
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_to_destination_of_another_project_is_rejected(client):
    user, project = _project_with_admin()
    other_user, other_project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user)
    other_destination = f.MilestoneFactory.create(project=other_project, owner=other_user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=other_destination.pk)))

    assert response.status_code == 400
    assert "milestone_id" in response.data
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_to_itself_is_rejected(client):
    user, project = _project_with_admin()
    sprint = f.MilestoneFactory.create(project=project, owner=user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=sprint.pk)))

    assert response.status_code == 400
    assert "milestone_id" in response.data
    _assert_nothing_registered(sprint)


def test_second_close_with_result_is_rejected(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    _closed_and_open_userstories(project, user, sprint)

    client.login(user)
    first = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))
    second = client.json.post(_url(sprint), json.dumps(_payload(goal_achievement="not_achieved",
                                                                result="Segunda tentativa")))

    assert first.status_code == 200, first.data
    assert second.status_code == 400
    assert "_error_message" in second.data
    sprint.refresh_from_db()
    assert sprint.goal_achievement == GoalAchievement.ACHIEVED
    assert sprint.result == "Login entregue"


def test_reopened_sprint_keeps_result_and_refuses_new_close_with_result(client):
    user, project = _project_with_admin()
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)
    open_status = open_us.status

    client.login(user)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))
    assert response.status_code == 200, response.data

    closed_us.refresh_from_db()
    closed_us.status = open_status
    closed_us.save()

    sprint.refresh_from_db()
    assert sprint.closed is False
    assert sprint.goal_achievement == GoalAchievement.ACHIEVED
    assert sprint.result == "Login entregue"
    assert sprint.result_by == user

    again = client.json.post(_url(sprint), json.dumps(_payload(result="De novo")))
    assert again.status_code == 400
    sprint.refresh_from_db()
    assert sprint.result == "Login entregue"


# Autorização

def test_close_with_result_without_modify_milestone_is_forbidden(client):
    user, project = _project_with_admin()
    member = _member_with_permissions(project, ["view_milestones", "modify_us"])
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(member)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 403
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_without_modify_us_and_stories_to_move_is_forbidden_and_rolls_back(client):
    user, project = _project_with_admin()
    member = _member_with_permissions(project, ["view_milestones", "modify_milestone"])
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(member)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 403
    _assert_nothing_registered(sprint)
    open_us.refresh_from_db()
    assert open_us.milestone_id == sprint.pk


def test_close_with_result_by_member_with_modify_milestone_and_modify_us_succeeds(client):
    user, project = _project_with_admin()
    member = _member_with_permissions(project, ["view_milestones", "modify_milestone", "modify_us"])
    sprint, destination = _sprints(project, user)
    closed_us, open_us = _closed_and_open_userstories(project, user, sprint)

    client.login(member)
    response = client.json.post(_url(sprint), json.dumps(_payload(milestone_id=destination.pk)))

    assert response.status_code == 200, response.data
    sprint.refresh_from_db()
    assert sprint.closed is True
    assert sprint.result_by == member
