# -*- coding: utf-8 -*-
# Cartão 12 · Notificação por e-mail e histórico do card sem o JSON da relação
#
# A entrada de histórico de relação (chave "card_relation") é gravada direto na
# key do card. Ela não pode entrar no snapshot reconstruído do card, senão a
# edição seguinte gera um diff "card_relation: [dict, None]" que vaza para o
# e-mail e que o front lê como relação resolvida.

import pytest

from .. import factories as f

from taiga.projects.card_relations.models import CardRelation
from taiga.projects.card_relations.choices import CardType, RelationType
from taiga.projects.history import services
from taiga.projects.history.models import HistoryEntry
from taiga.projects.history.choices import HistoryType
from taiga.projects.history.cardrelation_history_helpers import (
    CARDRELATION_DIFF_KEY,
    build_history_key,
    create_cardrelation_activity_entries,
)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def project():
    return f.ProjectFactory.create()


@pytest.fixture
def user(project):
    user = f.UserFactory.create()
    role = f.RoleFactory.create(project=project)
    f.MembershipFactory.create(project=project, user=user, role=role)
    return user


@pytest.fixture
def tasks(project, user):
    source = f.TaskFactory.create(project=project, owner=user)
    target = f.TaskFactory.create(project=project, owner=user)
    services.take_snapshot(source, user=user)
    services.take_snapshot(target, user=user)
    return source, target


def _create_relation(project, user, source, target, relation_type=RelationType.BLOCKS):
    return CardRelation.objects.create(
        project=project,
        source_type=CardType.TASK,
        source_id=source.id,
        target_type=CardType.TASK,
        target_id=target.id,
        relation_type=relation_type,
        created_by=user,
        is_active=True,
    )


def _edit_and_snapshot(task, user, subject):
    task.subject = subject
    task.save()
    return services.take_snapshot(task, user=user)


def _assert_edit_entry_without_relation(entry):
    assert entry is not None
    assert "subject" in entry.diff
    assert CARDRELATION_DIFF_KEY not in entry.diff
    assert CARDRELATION_DIFF_KEY not in entry.values_diff


def test_edit_after_relation_created_has_no_card_relation_in_diff(project, user, tasks):
    source, target = tasks
    relation = _create_relation(project, user, source, target)
    create_cardrelation_activity_entries(after_relation=relation, user=user)

    entry = _edit_and_snapshot(source, user, "editada depois de criar relação")

    _assert_edit_entry_without_relation(entry)


def test_edit_after_relation_changed_has_no_card_relation_in_diff(project, user, tasks):
    source, target = tasks
    relation = _create_relation(project, user, source, target)
    create_cardrelation_activity_entries(after_relation=relation, user=user)

    before = {
        "project_id": project.id,
        "source_type": relation.source_type,
        "source_id": relation.source_id,
        "target_type": relation.target_type,
        "target_id": relation.target_id,
        "relation_type": relation.relation_type,
    }
    relation.relation_type = RelationType.RELATED_TO
    relation.save()
    create_cardrelation_activity_entries(before_relation=before, after_relation=relation, user=user)

    entry = _edit_and_snapshot(source, user, "editada depois de alterar relação")

    _assert_edit_entry_without_relation(entry)


def test_edit_after_relation_resolved_has_no_card_relation_in_diff(project, user, tasks):
    source, target = tasks
    relation = _create_relation(project, user, source, target)
    create_cardrelation_activity_entries(after_relation=relation, user=user)

    relation.is_active = False
    relation.save()
    create_cardrelation_activity_entries(
        before_relation=relation, after_relation=None, user=user, action="resolved"
    )

    entry = _edit_and_snapshot(target, user, "editada depois de resolver relação")

    _assert_edit_entry_without_relation(entry)


def test_edit_after_relation_removed_has_no_card_relation_in_diff(project, user, tasks):
    source, target = tasks
    relation = _create_relation(project, user, source, target)
    create_cardrelation_activity_entries(after_relation=relation, user=user)

    create_cardrelation_activity_entries(
        before_relation=relation, after_relation=None, user=user, action="removed"
    )
    relation.delete()

    entry = _edit_and_snapshot(source, user, "editada depois de excluir relação")

    _assert_edit_entry_without_relation(entry)


def test_rebuilt_snapshot_ignores_card_relation_entries_already_stored(project, user, tasks):
    # Entrada gravada no formato que já existe no banco, sem passar pelo helper.
    source, target = tasks
    key = build_history_key(CardType.TASK, source.id)
    old_relation_diff = {
        CARDRELATION_DIFF_KEY: [
            None,
            {
                "relation_type": RelationType.BLOCKS,
                "source_type": CardType.TASK,
                "source_ref": source.ref,
                "target_type": CardType.TASK,
                "target_ref": target.ref,
            },
        ]
    }
    HistoryEntry.objects.create(
        user={"pk": user.id, "name": user.get_full_name()},
        project_id=project.id,
        key=key,
        type=HistoryType.change,
        diff=old_relation_diff,
        values={"users": {}},
        values_diff_cache=old_relation_diff,
        snapshot=None,
        comment="",
        comment_html="",
        is_hidden=False,
        is_snapshot=False,
    )

    frozen, _ = services.get_last_snapshot_for_key(key)

    assert frozen is not None
    assert CARDRELATION_DIFF_KEY not in frozen.snapshot
    assert frozen.snapshot["subject"] == source.subject

    entry = _edit_and_snapshot(source, user, "editada com entrada antiga no banco")

    _assert_edit_entry_without_relation(entry)


def test_relation_entries_keep_values_diff_format_on_both_cards(project, user, tasks):
    source, target = tasks
    relation = _create_relation(project, user, source, target)

    entries = create_cardrelation_activity_entries(after_relation=relation, user=user)

    assert len(entries) == 2
    expected_after = {
        "relation_type": RelationType.BLOCKS,
        "source_type": CardType.TASK,
        "source_ref": source.ref,
        "target_type": CardType.TASK,
        "target_ref": target.ref,
    }
    keys = {entry.key for entry in entries}
    assert keys == {
        build_history_key(CardType.TASK, source.id),
        build_history_key(CardType.TASK, target.id),
    }
    for entry in entries:
        assert entry.values_diff == {CARDRELATION_DIFF_KEY: [None, expected_after]}

    # Resolução mantém o mesmo formato, com "action" no lado anterior.
    relation.is_active = False
    relation.save()
    resolved = create_cardrelation_activity_entries(
        before_relation=relation, after_relation=None, user=user, action="resolved"
    )
    expected_before = dict(expected_after, action="resolved")
    for entry in resolved:
        assert entry.values_diff == {CARDRELATION_DIFF_KEY: [expected_before, None]}


def test_edit_without_relation_still_generates_normal_diff(user, tasks):
    source, _ = tasks

    entry = _edit_and_snapshot(source, user, "editada sem nenhuma relação")

    assert entry is not None
    assert entry.type == HistoryType.change
    assert entry.diff["subject"][1] == "editada sem nenhuma relação"
    assert CARDRELATION_DIFF_KEY not in entry.diff
