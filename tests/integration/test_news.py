# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import pytest

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

pytestmark = pytest.mark.django_db


##############################
## Migration
##############################

@pytest.mark.django_db(transaction=True)
def test_news_migration_reverses_and_reapplies():
    executor = MigrationExecutor(connection)
    executor.migrate([("news", None)])
    assert "news_slide" not in connection.introspection.table_names()

    executor = MigrationExecutor(connection)
    executor.migrate([("news", "0001_initial")])
    assert "news_slide" in connection.introspection.table_names()


def test_news_has_a_single_migration_that_only_creates_the_slide_table():
    loader = MigrationLoader(connection)
    news_migrations = [key for key in loader.disk_migrations if key[0] == "news"]
    assert news_migrations == [("news", "0001_initial")]

    migration = loader.disk_migrations[("news", "0001_initial")]
    assert [type(op).__name__ for op in migration.operations] == ["CreateModel"]
    assert migration.operations[0].name == "Slide"
    assert ("users", "0034_alter_role_permissions") in migration.dependencies


##############################
## API do carrossel
##############################

import os

from django.urls import reverse
from django.test.client import MULTIPART_CONTENT, encode_multipart, BOUNDARY

from .. import factories as f
from ..utils import DUMMY_BMP_DATA, helper_test_http_method
from taiga.base.utils import json
from taiga.news.validators import NEWS_SLIDE_MAX_IMAGE_SIZE


def _image(name="slide.bmp", data=DUMMY_BMP_DATA):
    from django.core.files.uploadedfile import SimpleUploadedFile
    return SimpleUploadedFile(name, data)


@pytest.fixture
def superuser():
    return f.UserFactory.create(is_superuser=True)


@pytest.fixture
def common_user():
    return f.UserFactory.create()


@pytest.fixture
def project_admin():
    project = f.ProjectFactory.create()
    f.MembershipFactory.create(project=project, user=project.owner, is_admin=True)
    return project.owner


@pytest.fixture
def project_member():
    project = f.ProjectFactory.create()
    user = f.UserFactory.create()
    f.MembershipFactory.create(project=project, user=user, is_admin=False)
    return user


# -- positivo ---------------------------------------------------------------

def test_superuser_creates_a_slide_in_one_multipart_request(client, superuser):
    url = reverse("news-list")
    client.login(superuser)

    response = client.post(url, {"image": _image(), "title": "Novo slide",
                                 "description": "Descrição", "order": 3})

    assert response.status_code == 201, response.data
    assert response.data["title"] == "Novo slide"
    assert response.data["description"] == "Descrição"
    assert response.data["order"] == 3
    assert response.data["is_active"] is False
    assert response.data["created_by"] == superuser.id
    assert response.data["image_url"].startswith("http")
    assert response.data["image_url"].endswith(".bmp")


def test_superuser_creates_a_slide_without_order_and_it_gets_the_default(client, superuser):
    url = reverse("news-list")
    client.login(superuser)

    response = client.post(url, {"image": _image(), "title": "Novo slide"})

    assert response.status_code == 201, response.data
    assert response.data["order"] == 10
    assert response.data["description"] == ""


def test_superuser_edits_title_activates_and_deactivates(client, superuser):
    slide = f.SlideFactory.create(is_active=False)
    url = reverse("news-detail", args=[slide.id])
    client.login(superuser)

    response = client.patch(url, json.dumps({"title": "Editado", "is_active": True}),
                            content_type="application/json")
    assert response.status_code == 200, response.data
    assert response.data["title"] == "Editado"
    assert response.data["is_active"] is True
    assert response.data["modified_by"] == superuser.id
    assert response.data["modified_date"] is not None

    response = client.patch(url, json.dumps({"is_active": False}), content_type="application/json")
    assert response.status_code == 200
    assert response.data["is_active"] is False
    slide.refresh_from_db()
    assert slide.image  # a imagem não foi tocada


def test_superuser_edits_without_image_keeps_the_current_one_on_put(client, superuser):
    slide = f.SlideFactory.create()
    original_image = slide.image.name
    url = reverse("news-detail", args=[slide.id])
    client.login(superuser)

    response = client.put(url, json.dumps({"title": "Só o título", "description": "", "order": 1}),
                          content_type="application/json")

    assert response.status_code == 200, response.data
    slide.refresh_from_db()
    assert slide.image.name == original_image


def test_superuser_deletes_a_slide(client, superuser):
    slide = f.SlideFactory.create()
    url = reverse("news-detail", args=[slide.id])
    client.login(superuser)

    response = client.delete(url)

    assert response.status_code == 204
    from taiga.news.models import Slide
    assert not Slide.objects.filter(id=slide.id).exists()


def test_superuser_reorders_slides_in_bulk(client, superuser):
    s1 = f.SlideFactory.create(order=1)
    s2 = f.SlideFactory.create(order=2)
    s3 = f.SlideFactory.create(order=3)
    url = reverse("news-bulk-update-order")
    client.login(superuser)

    data = json.dumps([{"slide_id": s1.id, "order": 30},
                       {"slide_id": s2.id, "order": 10},
                       {"slide_id": s3.id, "order": 20}])
    response = client.post(url, data, content_type="application/json")

    assert response.status_code == 204
    response = client.get(reverse("news-list"))
    assert [s["id"] for s in response.data] == [s2.id, s3.id, s1.id]


def test_anonymous_lists_only_active_slides_in_order_with_public_fields(client):
    inactive = f.SlideFactory.create(order=0, is_active=False)
    second = f.SlideFactory.create(order=5, is_active=True)
    first = f.SlideFactory.create(order=1, is_active=True)
    url = reverse("news-list")

    response = client.get(url)

    assert response.status_code == 200
    assert [s["id"] for s in response.data] == [first.id, second.id]
    assert inactive.id not in [s["id"] for s in response.data]
    assert set(response.data[0].keys()) == {"id", "image_url", "title", "description", "order"}
    assert response.data[0]["image_url"].startswith("http")


def test_anonymous_cannot_retrieve_an_inactive_slide_but_superuser_can(client, superuser):
    slide = f.SlideFactory.create(is_active=False)
    url = reverse("news-detail", args=[slide.id])

    response = client.get(url)
    assert response.status_code == 404

    client.login(superuser)
    response = client.get(url)
    assert response.status_code == 200
    assert "is_active" in response.data and "created_by" in response.data


def test_common_user_lists_only_active_slides_without_authorship(client, common_user):
    f.SlideFactory.create(is_active=False)
    active = f.SlideFactory.create(is_active=True)
    client.login(common_user)

    response = client.get(reverse("news-list"))

    assert response.status_code == 200
    assert [s["id"] for s in response.data] == [active.id]
    assert "created_by" not in response.data[0]
    assert "is_active" not in response.data[0]


# -- negativo ---------------------------------------------------------------

def test_create_without_image_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"), {"title": "Sem imagem"})
    assert response.status_code == 400
    assert response.data["image"] == ["image_required"]


def test_create_without_title_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"), {"image": _image()})
    assert response.status_code == 400
    assert response.data["title"] == ["title_required"]


def test_create_with_blank_title_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"), {"image": _image(), "title": ""})
    assert response.status_code == 400
    assert response.data["title"] == ["title_required"]


def test_create_with_invalid_image_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"),
                           {"image": _image("x.png", b"isto nao e imagem"), "title": "T"})
    assert response.status_code == 400
    assert response.data["image"] == ["invalid_image"]


def test_create_with_svg_is_refused_with_code(client, superuser):
    client.login(superuser)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'
    response = client.post(reverse("news-list"), {"image": _image("x.svg", svg), "title": "T"})
    assert response.status_code == 400
    assert response.data["image"] == ["invalid_image"]


def test_create_with_image_over_2mb_is_refused_with_code(client, superuser):
    client.login(superuser)
    big = DUMMY_BMP_DATA + b"\x00" * (NEWS_SLIDE_MAX_IMAGE_SIZE + 1 - len(DUMMY_BMP_DATA))
    response = client.post(reverse("news-list"), {"image": _image("big.bmp", big), "title": "T"})
    assert response.status_code == 400
    assert response.data["image"] == ["image_too_large"]


def test_create_with_negative_order_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"), {"image": _image(), "title": "T", "order": -1})
    assert response.status_code == 400
    assert response.data["order"] == ["order_negative"]


def test_create_with_title_over_255_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"), {"image": _image(), "title": "x" * 256})
    assert response.status_code == 400
    assert response.data["title"] == ["title_too_long"]


def test_create_with_description_over_500_is_refused_with_code(client, superuser):
    client.login(superuser)
    response = client.post(reverse("news-list"),
                           {"image": _image(), "title": "T", "description": "x" * 501})
    assert response.status_code == 400
    assert response.data["description"] == ["description_too_long"]


def test_edit_with_invalid_image_is_refused_with_code(client, superuser):
    slide = f.SlideFactory.create()
    client.login(superuser)
    data = encode_multipart(BOUNDARY, {"image": _image("x.png", b"nao e imagem")})
    response = client.patch(reverse("news-detail", args=[slide.id]), data, content_type=MULTIPART_CONTENT)
    assert response.status_code == 400
    assert response.data["image"] == ["invalid_image"]


def test_bulk_update_order_refuses_unknown_slide_and_changes_nothing(client, superuser):
    slide = f.SlideFactory.create(order=1)
    client.login(superuser)
    data = json.dumps([{"slide_id": slide.id, "order": 50}, {"slide_id": 999999, "order": 1}])

    response = client.post(reverse("news-bulk-update-order"), data, content_type="application/json")

    assert response.status_code == 400
    assert response.data["code"] == "slide_not_found"
    slide.refresh_from_db()
    assert slide.order == 1


def test_bulk_update_order_refuses_negative_order(client, superuser):
    slide = f.SlideFactory.create(order=1)
    client.login(superuser)
    data = json.dumps([{"slide_id": slide.id, "order": -5}])
    response = client.post(reverse("news-bulk-update-order"), data, content_type="application/json")
    assert response.status_code == 400


# -- autorização ------------------------------------------------------------

def test_write_actions_are_refused_for_everyone_but_superuser(client, superuser, common_user,
                                                                project_admin, project_member):
    slide = f.SlideFactory.create()
    users = [None, common_user, project_member, project_admin, superuser]

    results = []
    for user in users:
        client.logout()
        if user:
            client.login(user)
        response = client.post(reverse("news-list"), {"image": _image(), "title": "T"})
        results.append(response.status_code)
    assert results == [401, 403, 403, 403, 201]

    patch_data = json.dumps({"title": "Outro"})
    results = helper_test_http_method(client, "patch", reverse("news-detail", args=[slide.id]),
                                      patch_data, users)
    assert results == [401, 403, 403, 403, 200]

    put_data = json.dumps({"title": "Outro", "description": "", "order": 2})
    results = helper_test_http_method(client, "put", reverse("news-detail", args=[slide.id]),
                                      put_data, users)
    assert results == [401, 403, 403, 403, 200]

    order_data = json.dumps([{"slide_id": slide.id, "order": 7}])
    results = helper_test_http_method(client, "post", reverse("news-bulk-update-order"),
                                      order_data, users)
    assert results == [401, 403, 403, 403, 204]

    results = helper_test_http_method(client, "delete", reverse("news-detail", args=[slide.id]),
                                      None, users)
    assert results == [401, 403, 403, 403, 204]


def test_inactive_slides_are_hidden_from_everyone_but_superuser(client, superuser, common_user,
                                                                 project_admin):
    f.SlideFactory.create(is_active=False)
    f.SlideFactory.create(is_active=True)
    url = reverse("news-list")

    for user in [None, common_user, project_admin]:
        client.logout()
        if user:
            client.login(user)
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert "created_by" not in response.data[0]

    client.login(superuser)
    response = client.get(url)
    assert len(response.data) == 2


# -- arquivos ---------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
def test_changing_the_image_deletes_the_old_file_after_commit(client, superuser):
    slide = f.SlideFactory.create()
    old_path = slide.image.path
    assert os.path.exists(old_path)
    client.login(superuser)

    data = encode_multipart(BOUNDARY, {"image": _image("nova.bmp")})
    response = client.patch(reverse("news-detail", args=[slide.id]), data, content_type=MULTIPART_CONTENT)

    assert response.status_code == 200, response.data
    slide.refresh_from_db()
    assert slide.image.path != old_path
    assert os.path.exists(slide.image.path)
    assert not os.path.exists(old_path)


@pytest.mark.django_db(transaction=True)
def test_deleting_a_slide_deletes_its_file_after_commit(client, superuser):
    slide = f.SlideFactory.create()
    path = slide.image.path
    assert os.path.exists(path)
    client.login(superuser)

    response = client.delete(reverse("news-detail", args=[slide.id]))

    assert response.status_code == 204
    assert not os.path.exists(path)
