# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from unittest import mock

from django.urls import reverse

from taiga.base.utils import json

from .. import factories as f

import pytest
pytestmark = pytest.mark.django_db

# `emit_event` é o ponto por onde `emit_event_for_model` e `emit_event_for_ids`
# publicam; ele registra o envio em `on_commit`, então o mock fica antes disso
# e não depende de transação real.
EMIT = "taiga.events.events.emit_event"


def _epics_key(project):
    return "changes.project.{}.epics".format(project.pk)


def _epic_events(emit):
    return [(call.kwargs["routing_key"], call.kwargs["data"])
            for call in emit.call_args_list
            if call.kwargs["data"].get("matches") == "epics.epic"]


def test_create_epic_emits_create_event_on_project_epics_key():
    project = f.ProjectFactory.create()
    status = f.EpicStatusFactory.create(project=project)

    with mock.patch(EMIT) as emit:
        epic = f.EpicFactory.create(project=project, status=status, owner=project.owner)

    # A geração do `ref` (references.attach_sequence) regrava a épica dentro do
    # primeiro post_save, como já acontece com história, tarefa e issue; por isso
    # o `create` vem acompanhado de um `change`, e aqui se exige o `create`.
    events = _epic_events(emit)
    assert (_epics_key(project), {"type": "create", "matches": "epics.epic", "pk": epic.pk}) in events
    assert {routing_key for routing_key, _ in events} == {_epics_key(project)}


def test_update_epic_emits_change_event():
    epic = f.EpicFactory.create()

    with mock.patch(EMIT) as emit:
        epic.subject = "Épica renomeada"
        epic.save()

    assert _epic_events(emit) == [
        (_epics_key(epic.project), {"type": "change", "matches": "epics.epic", "pk": epic.pk})
    ]


def test_delete_epic_emits_delete_event():
    epic = f.EpicFactory.create()
    project = epic.project
    epic_pk = epic.pk

    with mock.patch(EMIT) as emit:
        epic.delete()

    assert (_epics_key(project), {"type": "delete", "matches": "epics.epic", "pk": epic_pk}) \
        in _epic_events(emit)


def test_link_userstory_to_epic_emits_epic_change_event():
    epic = f.EpicFactory.create()
    us = f.UserStoryFactory.create(project=epic.project)

    with mock.patch(EMIT) as emit:
        f.RelatedUserStory.create(epic=epic, user_story=us)

    assert _epic_events(emit) == [
        (_epics_key(epic.project), {"type": "change", "matches": "epics.epic", "pk": epic.pk})
    ]


def test_unlink_userstory_from_epic_emits_epic_change_event():
    epic = f.EpicFactory.create()
    us = f.UserStoryFactory.create(project=epic.project)
    related = f.RelatedUserStory.create(epic=epic, user_story=us)

    with mock.patch(EMIT) as emit:
        related.delete()

    assert _epic_events(emit) == [
        (_epics_key(epic.project), {"type": "change", "matches": "epics.epic", "pk": epic.pk})
    ]


def test_link_userstory_via_api_emits_epic_change_event(client):
    user = f.UserFactory.create()
    epic = f.EpicFactory.create()
    us = f.UserStoryFactory.create(project=epic.project)
    f.MembershipFactory.create(project=epic.project, user=user, is_admin=True)

    url = reverse("epics-related-userstories-list", args=[epic.pk])
    data = {"user_story": us.pk, "epic": epic.pk}
    client.login(user)

    with mock.patch(EMIT) as emit:
        response = client.json.post(url, json.dumps(data))

    assert response.status_code == 201
    assert _epic_events(emit) == [
        (_epics_key(epic.project), {"type": "change", "matches": "epics.epic", "pk": epic.pk})
    ]


def test_bulk_create_related_userstories_emits_single_epic_change_event(client):
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    epic = f.EpicFactory.create(project=project)
    f.MembershipFactory.create(project=project, user=user, is_admin=True)

    url = reverse("epics-related-userstories-bulk-create", args=[epic.pk])
    data = {"bulk_userstories": "história 1\nhistória 2\nhistória 3", "project_id": project.pk}
    client.login(user)

    with mock.patch(EMIT) as emit:
        response = client.json.post(url, json.dumps(data))

    assert response.status_code == 200
    assert len(response.data) == 3
    assert _epic_events(emit) == [
        (_epics_key(project), {"type": "change", "matches": "epics.epic", "pk": epic.pk})
    ]


def test_unwatched_type_related_to_epic_does_not_emit():
    epic = f.EpicFactory.create()

    with mock.patch(EMIT) as emit:
        f.EpicAttachmentFactory.create(content_object=epic, project=epic.project,
                                       owner=epic.owner)

    assert emit.call_count == 0


def test_epic_event_goes_only_to_its_own_project_key():
    other_project = f.ProjectFactory.create()
    epic = f.EpicFactory.create()

    with mock.patch(EMIT) as emit:
        epic.subject = "Só o projeto dono ouve"
        epic.save()

    keys = {routing_key for routing_key, _ in _epic_events(emit)}
    assert keys == {_epics_key(epic.project)}
    assert _epics_key(other_project) not in keys
