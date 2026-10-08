# -*- coding: utf-8 -*-
# Cartão 02 · Formato das respostas de erro da API de relações entre cards.
#
# Estes testes fixam o corpo exato que a API devolve em cada erro, porque o campo
# que embrulha o código varia conforme o caminho: "detail" no get_all_by_ref,
# "code" na validação do create e "_error_code" na guarda de campos read-only do
# PATCH. As suítes de API do QA se apoiam neste formato.

import json

import pytest

from django.urls import reverse

from taiga.projects.card_relations.models import CardRelation

from .. import factories as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def scene():
    user = f.UserFactory.create()
    project = f.ProjectFactory.create(owner=user)
    f.MembershipFactory.create(project=project, user=user, is_admin=True)
    source = f.TaskFactory.create(project=project, owner=user)
    target = f.TaskFactory.create(project=project, owner=user)
    return user, project, source, target


def _get_all_by_ref(client, project, card_type, card_ref):
    url = "/api/v1/card-relations/get_all_by_ref?project={}&card_type={}&card_ref={}".format(
        project, card_type, card_ref)
    return client.get(url)


def _create_relation(client, project_id, source, target, relation_type="BK"):
    data = json.dumps({
        "project_id": project_id,
        "source_type": "task",
        "source_id": source.id,
        "target_type": "task",
        "target_id": target.id,
        "relation_type": relation_type,
    })
    return client.post(reverse("card-relations-list"), data, content_type="application/json")


#################
# get_all_by_ref: o código do erro vem em "detail", numa lista
#################

def test_get_all_by_ref_with_invalid_card_type(client, scene):
    user, project, source, target = scene
    client.login(user)

    response = _get_all_by_ref(client, project.id, "VALOR INVÁLIDO", source.ref)

    assert response.status_code == 400
    assert response.data == {"detail": ["invalid_card_type"]}


def test_get_all_by_ref_with_non_numeric_card_ref(client, scene):
    user, project, source, target = scene
    client.login(user)

    response = _get_all_by_ref(client, project.id, "task", "VALOR INVÁLIDO")

    assert response.status_code == 400
    assert response.data == {"detail": ["invalid_card_ref_param"]}


def test_get_all_by_ref_with_non_numeric_project(client, scene):
    user, project, source, target = scene
    client.login(user)

    response = _get_all_by_ref(client, "VALOR INVÁLIDO", "task", source.ref)

    assert response.status_code == 400
    assert response.data == {"detail": ["invalid_project_param"]}


#################
# create: o código do erro vem em "code", numa lista
#################

def test_create_relation_of_a_card_with_itself(client, scene):
    user, project, source, target = scene
    client.login(user)

    response = _create_relation(client, project.id, source, source)

    assert response.status_code == 400
    assert response.data == {"code": ["self_relation_not_allowed"]}
    assert CardRelation.objects.count() == 0


def test_create_duplicated_relation(client, scene):
    user, project, source, target = scene
    client.login(user)

    first = _create_relation(client, project.id, source, target)
    assert first.status_code == 200, first.data

    response = _create_relation(client, project.id, source, target)

    assert response.status_code == 400
    assert response.data == {"code": ["cards_already_related"]}
    assert CardRelation.objects.count() == 1


def test_create_reverse_relation_between_related_cards(client, scene):
    user, project, source, target = scene
    client.login(user)

    first = _create_relation(client, project.id, source, target)
    assert first.status_code == 200, first.data

    # a relação inversa entre os mesmos cards cai no mesmo código
    response = _create_relation(client, project.id, target, source)

    assert response.status_code == 400
    assert response.data == {"code": ["cards_already_related"]}
    assert CardRelation.objects.count() == 1


#################
# PATCH: campos read-only são recusados antes de qualquer validação de conteúdo
#################

def test_patch_relation_with_readonly_fields(client, scene):
    user, project, source, target = scene
    client.login(user)

    created = _create_relation(client, project.id, source, target)
    assert created.status_code == 200, created.data
    relation_id = created.data["id"]

    data = json.dumps({
        "project_id": project.id,
        "source_type": "CINTHIA",
        "relation_type": "RT",
    })
    response = client.patch("/api/v1/card-relations/%s" % relation_id, data,
                            content_type="application/json")

    assert response.status_code == 400
    assert response.data["_error_code"] == "PATCH_READONLY_FIELDS"
    # a ordem de "fields" vem de um set e não é estável
    assert set(response.data["fields"]) == {"source_type", "project_id"}


def test_patch_relation_with_project_id_is_refused(client, scene):
    user, project, source, target = scene
    client.login(user)

    created = _create_relation(client, project.id, source, target)
    assert created.status_code == 200, created.data
    relation_id = created.data["id"]

    data = json.dumps({"project_id": project.id, "relation_type": "RT"})
    response = client.patch("/api/v1/card-relations/%s" % relation_id, data,
                            content_type="application/json")

    assert response.status_code == 400
    assert response.data["_error_code"] == "PATCH_READONLY_FIELDS"
    assert set(response.data["fields"]) == {"project_id"}


def test_patch_relation_type_alone_is_accepted(client, scene):
    user, project, source, target = scene
    client.login(user)

    created = _create_relation(client, project.id, source, target)
    assert created.status_code == 200, created.data
    relation_id = created.data["id"]

    data = json.dumps({"relation_type": "RT"})
    response = client.patch("/api/v1/card-relations/%s" % relation_id, data,
                            content_type="application/json")

    assert response.status_code == 200, response.data
    assert response.data["relation_type"] == "RT"
