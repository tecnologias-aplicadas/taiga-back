# -*- coding: utf-8 -*-
# Cartão 12 · Notificação por e-mail e histórico do card sem o JSON da relação
#
# O e-mail de notificação não pode exibir o JSON da relação entre cards, nem
# quando a entrada é a da própria relação, nem quando é uma entrada legada com
# "card_relation" vazado para o diff do card. As outras notificações seguem
# iguais.

import pytest

from .. import factories as f

from taiga.projects.card_relations.models import CardRelation
from taiga.projects.card_relations.choices import CardType, RelationType
from taiga.projects.history.models import HistoryEntry
from taiga.projects.history.choices import HistoryType
from taiga.projects.history.services import take_snapshot
from taiga.projects.history.cardrelation_history_helpers import (
    CARDRELATION_DIFF_KEY,
    build_history_key,
    create_cardrelation_activity_entries,
)
from taiga.projects.notifications import services

pytestmark = pytest.mark.django_db(transaction=True)

# Tokens do JSON da relação que nunca podem aparecer em um corpo de e-mail.
RELATION_JSON_TOKENS = (
    CARDRELATION_DIFF_KEY,
    "source_ref",
    "target_ref",
    "relation_type",
    "source_type",
    "target_type",
)


@pytest.fixture
def mail():
    from django.core import mail
    mail.outbox = []
    return mail


@pytest.fixture
def notifications_sync(settings):
    settings.CHANGE_NOTIFICATIONS_MIN_INTERVAL = 0
    return settings


@pytest.fixture
def project():
    return f.ProjectFactory.create()


@pytest.fixture
def role(project):
    return f.RoleFactory.create(
        project=project,
        permissions=["view_tasks", "view_us", "view_issues", "view_epics"],
    )


@pytest.fixture
def changer(project, role):
    return f.MembershipFactory.create(project=project, role=role).user


@pytest.fixture
def watcher(project, role):
    return f.MembershipFactory.create(project=project, role=role).user


@pytest.fixture
def watched_task(project, changer, watcher):
    task = f.TaskFactory.create(project=project, owner=changer)
    task.add_watcher(watcher)
    take_snapshot(task, user=changer)
    return task


def _text_body(msg):
    return msg.body


def _html_body(msg):
    assert msg.alternatives, "o e-mail deveria ter alternativa HTML"
    return msg.alternatives[0][0]


def _assert_bodies_without_relation_json(msg):
    text = _text_body(msg)
    html = _html_body(msg)

    assert "{" not in text
    assert "[" not in text
    for token in RELATION_JSON_TOKENS:
        assert token not in text
        assert token not in html


def _relation_side(source, target, relation_type=RelationType.BLOCKS):
    return {
        "relation_type": relation_type,
        "source_type": CardType.TASK,
        "source_ref": source.ref,
        "target_type": CardType.TASK,
        "target_ref": target.ref,
    }


def _create_relation(project, user, source, target):
    return CardRelation.objects.create(
        project=project,
        source_type=CardType.TASK,
        source_id=source.id,
        target_type=CardType.TASK,
        target_id=target.id,
        relation_type=RelationType.BLOCKS,
        created_by=user,
        is_active=True,
    )


def _legacy_entry(project, user, key, diff):
    return HistoryEntry.objects.create(
        user={"pk": user.id, "name": user.get_full_name()},
        project_id=project.id,
        key=key,
        type=HistoryType.change,
        diff=diff,
        values={"users": {}},
        values_diff_cache=diff,
        snapshot=None,
        comment="",
        comment_html="",
        is_hidden=False,
        is_snapshot=False,
    )


def test_email_after_relation_created_shows_changed_field_without_relation_json(
        notifications_sync, mail, project, changer, watcher, watched_task):
    other = f.TaskFactory.create(project=project, owner=changer)
    relation = _create_relation(project, changer, watched_task, other)
    create_cardrelation_activity_entries(after_relation=relation, user=changer)

    new_subject = "Assunto novo depois da relacao"
    watched_task.subject = new_subject
    watched_task.save()
    entry = take_snapshot(watched_task, user=changer)

    services.send_notifications(watched_task, history=entry)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == [watcher.email]
    _assert_bodies_without_relation_json(msg)
    assert new_subject in _text_body(msg)
    assert new_subject in _html_body(msg)


def test_email_for_legacy_entry_with_relation_in_diff_has_no_relation_json(
        notifications_sync, mail, project, changer, watcher, watched_task):
    # Artefato que existia antes do cartão 12: a edição seguinte do card gravava
    # diff["card_relation"] = [dict, None] e isso chegava ao e-mail como JSON.
    other = f.TaskFactory.create(project=project, owner=changer)
    key = build_history_key(CardType.TASK, watched_task.id)
    legacy_diff = {CARDRELATION_DIFF_KEY: [_relation_side(watched_task, other), None]}
    entry = _legacy_entry(project, changer, key, legacy_diff)

    services.send_notifications(watched_task, history=entry)

    # A entrada tem values_diff não vazio, então a notificação não é descartada:
    # o e-mail sai, mas o include de campos exclui "card_relation".
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == [watcher.email]
    _assert_bodies_without_relation_json(msg)
    assert str(watched_task.ref) in _text_body(msg)


def test_email_for_relation_entry_itself_has_no_relation_json(
        notifications_sync, mail, project, changer, watcher, watched_task):
    other = f.TaskFactory.create(project=project, owner=changer)
    relation = _create_relation(project, changer, watched_task, other)
    entries = create_cardrelation_activity_entries(after_relation=relation, user=changer)
    key = build_history_key(CardType.TASK, watched_task.id)
    entry = next(e for e in entries if e.key == key)
    assert entry.values_diff == {CARDRELATION_DIFF_KEY: [None, _relation_side(watched_task, other)]}

    services.send_notifications(watched_task, history=entry)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == [watcher.email]
    _assert_bodies_without_relation_json(msg)


def test_email_for_task_edit_without_relation_is_unchanged(
        notifications_sync, mail, changer, watcher, watched_task):
    new_subject = "Edicao comum sem relacao"
    watched_task.subject = new_subject
    watched_task.save()
    entry = take_snapshot(watched_task, user=changer)

    services.send_notifications(watched_task, history=entry)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == [watcher.email]
    assert new_subject in _text_body(msg)
    assert new_subject in _html_body(msg)
    _assert_bodies_without_relation_json(msg)


def test_email_for_userstory_edit_is_unchanged(
        notifications_sync, mail, project, changer, watcher):
    us = f.UserStoryFactory.create(project=project, owner=changer)
    us.add_watcher(watcher)
    take_snapshot(us, user=changer)

    new_subject = "Historia editada normalmente"
    us.subject = new_subject
    us.save()
    entry = take_snapshot(us, user=changer)

    services.send_notifications(us, history=entry)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == [watcher.email]
    assert "subject" in entry.values_diff
    assert new_subject in _text_body(msg)
    assert new_subject in _html_body(msg)
    _assert_bodies_without_relation_json(msg)
