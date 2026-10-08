# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from decimal import Decimal

from django.urls import reverse

from taiga.base.utils import json
from taiga.projects.models import Project
from taiga.projects.epics.models import Epic, RelatedUserStory
from taiga.projects.userstories.models import UserStory
from tests import factories as f

pytestmark = pytest.mark.django_db



def test_calculate_completion_percent_progress_with_user_stories():
    project = f.ProjectFactory.create()

    # cria status com percentuais diferentes
    status_todo = f.TaskStatusFactory.create(project=project, name="A Fazer", completion_percent=0, is_closed=False)
    status_doing = f.TaskStatusFactory.create(project=project, name="Em Progresso", completion_percent=50, is_closed=False)
    status_done = f.TaskStatusFactory.create(project=project, name="Concluída", completion_percent=100, is_closed=True)

    # cria a história
    us = f.UserStoryFactory.create(project=project)

    # cria tasks em status diferentes (isso muda automaticamente o completion_percent_progress)
    f.TaskFactory.create(user_story=us, project=project, status=status_todo)
    f.TaskFactory.create(user_story=us, project=project, status=status_doing)
    f.TaskFactory.create(user_story=us, project=project, status=status_done)

    # força o recálculo da história
    us.update_completion_percent()

    # tasks fechadas têm progress=0; progresso médio: (0 + 50 + 0) / 3 = 16.67
    assert us.completion_percent_progress == Decimal("16.67")

    # done médio: apenas tasks fechadas (100) / total (3) = 33.33
    assert us.completion_percent_done == Decimal("33.33")



def test_task_reopen_task_reset_done_and_update_progress():
    project = f.ProjectFactory.create()

    # status
    status_done = f.TaskStatusFactory.create(project=project, name="Concluída", completion_percent=100, is_closed=True)
    status_doing = f.TaskStatusFactory.create(project=project, name="Em Progresso", completion_percent=50, is_closed=False)

    # cria task como concluída
    task = f.TaskFactory.create(project=project, status=status_done)
    assert task.completion_percent_progress == Decimal("0.00")
    assert task.completion_percent_done == Decimal("100.00")
    assert task.finished_date is not None  # data de conclusão setada

    # move task para coluna "Em Progresso"
    task.status = status_doing
    task.save()
    task.refresh_from_db()

    # verifica se zerou o done e atualizou progress
    assert task.completion_percent_progress == Decimal("50.00")
    assert task.completion_percent_done == Decimal("0.00")
    assert task.finished_date is None

def test_task_reinside_in_done_update_progress_and_done():
    project = f.ProjectFactory.create()
    status_doing = f.TaskStatusFactory.create(project=project, name="Em Progresso", completion_percent=60, is_closed=False)
    status_done = f.TaskStatusFactory.create(project=project, name="Concluída", completion_percent=100, is_closed=True)

    task = f.TaskFactory.create(project=project, status=status_doing)
    assert task.completion_percent_progress == Decimal("60.00")
    assert task.completion_percent_done == Decimal("0.00")

    # agora move pra coluna done
    task.status = status_done
    task.save()
    task.refresh_from_db()

    assert task.completion_percent_progress == Decimal("0.00")
    assert task.completion_percent_done == Decimal("100.00")
    assert task.finished_date is not None

def test_task_update_progress_when_percentual_of_status_changes():
    project = f.ProjectFactory.create()
    status = f.TaskStatusFactory.create(project=project, name="Em Progresso", completion_percent=40, is_closed=False)

    task = f.TaskFactory.create(project=project, status=status)
    assert task.completion_percent_progress == Decimal("40.00")

    # muda o percentual da própria coluna
    status.completion_percent = 70
    status.save()

    # força o resave da task (simulando que foi movida internamente)
    task.save()
    task.refresh_from_db()

    assert task.completion_percent_progress == Decimal("70.00")

def test_task_initial_without_closed_status():
    project = f.ProjectFactory.create()
    status_open = f.TaskStatusFactory.create(project=project, name="A Fazer", completion_percent=0, is_closed=False)

    task = f.TaskFactory.create(project=project, status=status_open)

    assert task.completion_percent_progress == Decimal("0.00")
    assert task.completion_percent_done == Decimal("0.00")
    assert task.finished_date is None

def test_task_inicial_closed_generates_finished_date():
    project = f.ProjectFactory.create()
    status_done = f.TaskStatusFactory.create(project=project, name="Concluída", completion_percent=100, is_closed=True)

    task = f.TaskFactory.create(project=project, status=status_done)

    assert task.completion_percent_progress == Decimal("0.00")
    assert task.completion_percent_done == Decimal("100.00")
    assert task.finished_date is not None


def test_user_story_updates_when_reopening_task():
    """When a done task moves back to a non-closed status, the story updates progress and resets done."""
    project = f.ProjectFactory.create()

    # Task statuses
    status_done = f.TaskStatusFactory.create(project=project, name="Done", completion_percent=100, is_closed=True)
    status_doing = f.TaskStatusFactory.create(project=project, name="Doing", completion_percent=50, is_closed=False)

    # Create User Story
    us = f.UserStoryFactory.create(project=project)

    # Create tasks
    t1 = f.TaskFactory.create(user_story=us, project=project, status=status_done)
    t2 = f.TaskFactory.create(user_story=us, project=project, status=status_done)
    us.update_completion_percent()
    us.refresh_from_db()

    # Initially, both done → tasks have progress=0; shortcut: progress=0, done=100
    assert us.completion_percent_progress == Decimal("0.00")
    assert us.completion_percent_done == Decimal("100.00")

    # Reopen one task (change status)
    t1.status = status_doing
    t1.save()
    us.update_completion_percent()
    us.refresh_from_db()

    # Now: done task has progress=0; (0 + 50) / 2 = 25 progress; 1/2 done = 50 done
    assert us.completion_percent_progress == Decimal("25.00")
    assert us.completion_percent_done == Decimal("50.00")


def test_user_story_resets_done_when_all_tasks_reopened():
    """If all tasks move out of closed statuses, done returns to 0."""
    project = f.ProjectFactory.create()

    status_done = f.TaskStatusFactory.create(project=project, name="Done", completion_percent=100, is_closed=True)
    status_todo = f.TaskStatusFactory.create(project=project, name="To Do", completion_percent=0, is_closed=False)

    us = f.UserStoryFactory.create(project=project)
    t1 = f.TaskFactory.create(user_story=us, project=project, status=status_done)
    t2 = f.TaskFactory.create(user_story=us, project=project, status=status_done)

    us.update_completion_percent()
    us.refresh_from_db()
    assert us.completion_percent_done == Decimal("100.00")

    # Reopen both
    t1.status = status_todo
    t2.status = status_todo
    t1.save(); t2.save()
    us.update_completion_percent()
    us.refresh_from_db()

    assert us.completion_percent_progress == Decimal("0.00")
    assert us.completion_percent_done == Decimal("0.00")



def test_epic_updates_average_when_user_story_changes():
    """When a user story changes its completion, the epic updates its average correctly."""
    project = f.ProjectFactory.create()
    epic = f.EpicFactory.create(project=project)

    # statuses
    status_done  = f.TaskStatusFactory.create(project=project, name="Done",  completion_percent=100, is_closed=True)
    status_doing = f.TaskStatusFactory.create(project=project, name="Doing", completion_percent=50,  is_closed=False)
    status_todo  = f.TaskStatusFactory.create(project=project, name="To Do", completion_percent=0,   is_closed=False)

    # US1: 100% (done)
    us1 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us1, project=project, status=status_done)
    us1.update_completion_percent()

    # US2: 0% (todo)
    us2 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us2, project=project, status=status_todo)
    us2.update_completion_percent()

    # US3: 50% (doing)
    us3 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us3, project=project, status=status_doing)
    us3.update_completion_percent()

    # link to epic
    RelatedUserStory.objects.create(epic=epic, user_story=us1)
    RelatedUserStory.objects.create(epic=epic, user_story=us2)
    RelatedUserStory.objects.create(epic=epic, user_story=us3)

    # initial epic calc
    epic.update_completion_percent()
    epic.refresh_from_db()
    assert epic.completion_percent_progress == Decimal("16.67")   # done task has progress=0: (0+0+50)/3
    assert epic.completion_percent_done == Decimal("33.33")       # (100+0+0)/3

    # Reopen US1: Done -> Doing (50/0)
    task = us1.tasks.first()
    task.status = status_doing
    task.save()
    us1.update_completion_percent()

    # epic after change
    epic.update_completion_percent()
    epic.refresh_from_db()
    assert epic.completion_percent_progress == Decimal("33.33")   # (50+0+50)/3
    assert epic.completion_percent_done == Decimal("0.00")        # (0+0+0)/3




def test_epic_reaches_full_done_when_all_stories_closed():
    """Epic should reach 100% when all user stories are fully completed."""
    project = f.ProjectFactory.create()
    epic = f.EpicFactory.create(project=project)

    status_done = f.TaskStatusFactory.create(project=project, name="Done", completion_percent=100, is_closed=True)

    # Create US1 and US2 with tasks 100% done
    us1 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us1, project=project, status=status_done)
    us1.update_completion_percent()

    us2 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us2, project=project, status=status_done)
    us2.update_completion_percent()

    # Link to epic
    RelatedUserStory.objects.create(epic=epic, user_story=us1)
    RelatedUserStory.objects.create(epic=epic, user_story=us2)

    # Update epic progress
    epic.update_completion_percent()
    epic.refresh_from_db()

    assert epic.completion_percent_progress == Decimal("0.00")
    assert epic.completion_percent_done == Decimal("100.00")


def test_epic_returns_to_partial_when_story_reopened():
    """If one story reopens, epic progress and done should reflect partial values."""
    project = f.ProjectFactory.create()
    epic = f.EpicFactory.create(project=project)

    status_done = f.TaskStatusFactory.create(project=project, name="Done", completion_percent=100, is_closed=True)
    status_doing = f.TaskStatusFactory.create(project=project, name="Doing", completion_percent=60, is_closed=False)

    # Create US1 (done)
    us1 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us1, project=project, status=status_done)
    us1.update_completion_percent()

    # Create US2 (done)
    us2 = f.UserStoryFactory.create(project=project)
    f.TaskFactory.create(user_story=us2, project=project, status=status_done)
    us2.update_completion_percent()

    # Link both to epic
    RelatedUserStory.objects.create(epic=epic, user_story=us1)
    RelatedUserStory.objects.create(epic=epic, user_story=us2)

    epic.update_completion_percent()
    epic.refresh_from_db()
    assert epic.completion_percent_progress == Decimal("0.00")

    # Reopen US2 (change its task to doing)
    task = us2.tasks.first()
    task.status = status_doing
    task.save()
    us2.update_completion_percent()

    # Update epic again
    epic.update_completion_percent()
    epic.refresh_from_db()

    # done task has progress=0; average: (0 + 60) / 2 = 30 progress
    assert epic.completion_percent_progress == Decimal("30.00")
    assert epic.completion_percent_done == Decimal("50.00")

####################################################################################
# copia do completion_percent dos status de tarefa por template / duplicacao
####################################################################################

def _template_with_task_statuses(task_statuses, default_task_status_name):
    return f.ProjectTemplateFactory.create(
        slug="template-completion-percent",
        task_statuses=task_statuses,
        default_options={"task_status": default_task_status_name},
    )


def test_duplicate_project_copies_task_status_completion_percent(client):
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    f.TaskStatusFactory.create(project=project, name="A Fazer", completion_percent=30, is_closed=False)
    f.TaskStatusFactory.create(project=project, name="Em Progresso", completion_percent=70, is_closed=False)
    f.TaskStatusFactory.create(project=project, name="Concluída", completion_percent=100, is_closed=True)
    project.default_task_status = project.task_statuses.get(name="A Fazer")
    project.save()

    role = f.RoleFactory.create(project=project, permissions=["view_project"])
    f.MembershipFactory.create(project=project, user=user, role=role, is_admin=True)

    client.login(user)
    url = reverse("projects-duplicate", args=(project.id,))
    response = client.json.post(url, json.dumps({
        "name": "copia",
        "description": "copia",
        "is_private": True,
        "users": [],
    }))
    assert response.status_code == 201

    new_project = Project.objects.get(id=response.data["id"])
    copied = {s.name: (s.completion_percent, s.is_closed) for s in new_project.task_statuses.all()}
    assert copied["A Fazer"] == (30, False)
    assert copied["Em Progresso"] == (70, False)
    assert copied["Concluída"] == (100, True)


def test_apply_template_copies_task_status_completion_percent():
    template = _template_with_task_statuses([
        {"name": "A Fazer", "slug": "a-fazer", "is_closed": False, "color": "#999999", "order": 1,
         "completion_percent": 10},
        {"name": "Em Progresso", "slug": "em-progresso", "is_closed": False, "color": "#999999", "order": 2,
         "completion_percent": 60},
    ], "A Fazer")
    project = f.ProjectFactory.create()

    template.apply_to_project(project)

    copied = {s.name: s.completion_percent for s in project.task_statuses.all()}
    assert copied["A Fazer"] == 10
    assert copied["Em Progresso"] == 60


def test_apply_template_without_completion_percent_key_creates_status_with_none():
    template = _template_with_task_statuses([
        {"name": "Novo", "slug": "novo", "is_closed": False, "color": "#999999", "order": 1},
        {"name": "Fechado", "slug": "fechado", "is_closed": True, "color": "#999999", "order": 2},
    ], "Novo")
    project = f.ProjectFactory.create()

    template.apply_to_project(project)

    copied = {s.name: s.completion_percent for s in project.task_statuses.all()}
    assert copied["Novo"] is None
    # status fechado é sempre 100, mesmo sem valor no template
    assert copied["Fechado"] == 100


def test_apply_template_normalizes_100_on_open_status_and_forces_100_on_closed():
    template = _template_with_task_statuses([
        {"name": "Quase", "slug": "quase", "is_closed": False, "color": "#999999", "order": 1,
         "completion_percent": 100},
        {"name": "Fechado", "slug": "fechado", "is_closed": True, "color": "#999999", "order": 2,
         "completion_percent": 40},
    ], "Quase")
    project = f.ProjectFactory.create()

    template.apply_to_project(project)

    copied = {s.name: s.completion_percent for s in project.task_statuses.all()}
    assert copied["Quase"] == 99
    assert copied["Fechado"] == 100


def test_apply_template_rejects_completion_percent_out_of_range():
    template = _template_with_task_statuses([
        {"name": "Alto", "slug": "alto", "is_closed": False, "color": "#999999", "order": 1,
         "completion_percent": 150},
        {"name": "Negativo", "slug": "negativo", "is_closed": False, "color": "#999999", "order": 2,
         "completion_percent": -5},
        {"name": "Texto", "slug": "texto", "is_closed": False, "color": "#999999", "order": 3,
         "completion_percent": "50"},
    ], "Alto")
    project = f.ProjectFactory.create()

    template.apply_to_project(project)

    copied = {s.name: s.completion_percent for s in project.task_statuses.all()}
    assert copied["Alto"] is None
    assert copied["Negativo"] is None
    assert copied["Texto"] is None
