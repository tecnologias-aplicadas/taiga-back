# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import inspect
from types import SimpleNamespace
from unittest import mock

import pytest

from django.db import IntegrityError

from django.urls import reverse
from django.core import mail

from taiga.auth.api import AuthViewSet
from taiga.base import exceptions as exc
from taiga.projects.models import Membership
from taiga.users.models import User

from .. import factories

pytestmark = pytest.mark.django_db


@pytest.fixture
def register_form():
    return {"username": "username",
            "password": "password",
            "full_name": "fname",
            "email": "user@email.com",
            "accepted_terms": True,
            "type": "public"}

#################
# registration
#################

def test_respond_201_when_public_registration_is_enabled(client, settings, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201


def test_respond_400_when_public_registration_is_disabled(client, register_form, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400
    # o servidor devolve código, não texto: quem traduz é o front
    assert response.data["code"] == "public_register_disabled"
    assert "_error_message" not in response.data


def test_respond_400_when_the_terms_are_not_accepted(client, register_form, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    del register_form["accepted_terms"]

    response = client.post(reverse("auth-register"), register_form)

    assert response.status_code == 400
    assert response.data["code"] == "terms_not_accepted"
    assert "_error_message" not in response.data
    assert not User.objects.filter(username="username").exists()


def test_respond_400_when_the_registration_type_is_unknown(client, register_form, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    register_form["type"] = "unknown"

    response = client.post(reverse("auth-register"), register_form)

    assert response.status_code == 400
    assert response.data["code"] == "invalid_registration_type"
    assert "_error_message" not in response.data
    assert not User.objects.filter(username="username").exists()


def test_public_register_when_the_user_cannot_be_created(client, register_form, settings):
    settings.PUBLIC_REGISTER_ENABLED = True

    with mock.patch("taiga.users.models.User.save", side_effect=IntegrityError):
        response = client.post(reverse("auth-register"), register_form)

    assert response.status_code == 400
    assert response.data["code"] == "user_creation_failed"
    assert "_error_message" not in response.data


def test_respond_400_when_the_email_domain_isnt_in_allowed_domains(client, register_form, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    settings.USER_EMAIL_ALLOWED_DOMAINS = ['other-domain.com']
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400


def test_respond_201_when_the_email_domain_is_in_allowed_domains(client, settings, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True
    settings.USER_EMAIL_ALLOWED_DOMAINS = ['email.com']
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201


def test_response_200_in_public_registration(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    form = {
        "type": "public",
        "username": "mmcfly",
        "full_name": "martin seamus mcfly",
        "email": "mmcfly@bttf.com",
        "password": "password",
        "accepted_terms": True,
    }

    response = client.post(reverse("auth-register"), form)
    assert response.status_code == 201
    assert response.data["username"] == "mmcfly"
    assert response.data["email"] == "mmcfly@bttf.com"
    assert response.data["full_name"] == "martin seamus mcfly"
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "You've been Taigatized!"


def test_respond_400_if_username_is_invalid(client, settings, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True

    register_form.update({"username": "User Examp:/e"})
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

    register_form.update({"username": 300*"a"})
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400


def test_respond_400_if_username_or_email_is_duplicate(client, settings, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True

    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201

    register_form["username"] = "username"
    register_form["email"] = "ff@dd.com"
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400
    # o servidor devolve código, não texto: quem traduz é o front
    assert response.data["code"] == "username_already_in_use"
    assert "_error_message" not in response.data


def test_public_register_with_duplicated_email_answers_with_a_code(client, settings, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True

    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201

    register_form["username"] = "another_username"
    response = client.post(reverse("auth-register"), register_form)

    assert response.status_code == 400
    assert response.data["code"] == "email_already_in_use"
    assert "_error_message" not in response.data


def test_register_success_throttling(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["register-success"] = "1/minute"

    register_form = {"username": "valid_username_register_success",
                     "password": "valid_password",
                     "full_name": "fullname",
                     "email": "",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

    register_form = {"username": "valid_username_register_success",
                     "password": "valid_password",
                     "full_name": "fullname",
                     "email": "valid_username_register_success@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201

    register_form = {"username": "valid_username_register_success2",
                     "password": "valid_password2",
                     "full_name": "fullname",
                     "email": "valid_username_register_success2@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 429

    register_form = {"username": "valid_username_register_success2",
                     "password": "valid_password2",
                     "full_name": "fullname",
                     "email": "",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 429

    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["register-success"] = None


INVALID_NAMES = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod",
    "an <script>evil()</script> example",
    "http://testdomain.com",
    "https://testdomain.com",
    "Visit http://testdomain.com",
]

@pytest.mark.parametrize("full_name", INVALID_NAMES)
def test_register_sanitize_invalid_user_full_name(client, settings, full_name, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True
    register_form["full_name"] = full_name
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

VALID_NAMES = [
    "martin seamus mcfly"
]

@pytest.mark.parametrize("full_name", VALID_NAMES)
def test_register_sanitize_valid_user_full_name(client, settings, full_name, register_form):
    settings.PUBLIC_REGISTER_ENABLED = True
    register_form["full_name"] = full_name
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201


def test_registration_case_insensitive_for_username_and_password(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = True

    register_form = {"username": "Username",
                     "password": "password",
                     "full_name": "fname",
                     "email": "User@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201

    # Email is case insensitive in the register process
    register_form = {"username": "username2",
                     "password": "password",
                     "full_name": "fname",
                     "email": "user@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

    # Username is case insensitive in the register process too
    register_form = {"username": "username",
                     "password": "password",
                     "full_name": "fname",
                     "email": "user2@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400


def _private_register_form(token, username="private_user"):
    return {"type": "private",
            "token": token,
            "username": username,
            "password": "password",
            "full_name": "private user",
            "email": "%s@email.com" % username,
            "accepted_terms": True}


def test_private_register_with_project_invitation(client):
    membership = factories.MembershipFactory(user=None, email="private_user@email.com")

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 201, response.data
    assert membership.user is not None
    assert membership.user.username == "private_user"


def test_private_register_with_project_invitation_case_insensitive_email(client):
    membership = factories.MembershipFactory(user=None, email="Private_User@Email.com")

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 201, response.data
    assert membership.user.username == "private_user"


def test_private_register_with_another_email_than_the_invited_one(client):
    membership = factories.MembershipFactory(user=None, email="invited@email.com")

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    # o servidor devolve código, não texto: quem traduz é o front
    assert response.data["code"] == "invitation_email_mismatch"
    assert "_error_message" not in response.data
    # a função é atômica e a checagem vem antes: nenhum usuário é criado
    assert not User.objects.filter(username="private_user").exists()
    assert membership.user is None
    # o e-mail convidado não aparece na resposta
    assert "invited@email.com" not in str(response.data)


def test_private_register_with_invitation_without_email(client):
    membership = factories.MembershipFactory(user=None, email=None)

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    # mesmo código e mesmo status do e-mail diferente: os dois casos são
    # indistinguíveis de fora
    assert response.data["code"] == "invitation_email_mismatch"
    assert "_error_message" not in response.data
    assert not User.objects.filter(username="private_user").exists()
    assert membership.user is None


def test_private_register_with_already_accepted_project_invitation(client):
    other_user = factories.UserFactory()
    membership = factories.MembershipFactory(user=other_user)

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 404, response.data
    assert response.data["code"] == "invitation_not_valid"
    assert "_error_message" not in response.data
    assert membership.user == other_user
    # a função é atômica: o usuário criado antes da verificação é desfeito
    assert not User.objects.filter(username="private_user").exists()


def test_private_register_with_unknown_project_invitation(client):
    membership = factories.MembershipFactory(user=None)

    response = client.post(reverse("auth-register"), _private_register_form("token-that-does-not-exist"))
    membership.refresh_from_db()

    assert response.status_code == 404, response.data
    # convite desconhecido e convite já aceito respondem igual
    assert response.data["code"] == "invitation_not_valid"
    assert "_error_message" not in response.data
    assert membership.user is None
    assert not User.objects.filter(username="private_user").exists()


def test_private_register_with_a_username_already_in_use(client):
    factories.UserFactory(username="private_user")
    membership = factories.MembershipFactory(user=None, email="private_user@email.com")

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    assert response.data["code"] == "username_already_in_use"
    assert "_error_message" not in response.data
    assert membership.user is None


def test_private_register_with_an_email_already_in_use(client):
    factories.UserFactory(email="private_user@email.com")
    membership = factories.MembershipFactory(user=None, email="private_user@email.com")

    response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    assert response.data["code"] == "email_already_in_use"
    assert "_error_message" not in response.data
    assert membership.user is None


def test_private_register_when_the_user_cannot_be_created(client):
    membership = factories.MembershipFactory(user=None, email="private_user@email.com")

    with mock.patch("taiga.users.models.User.save", side_effect=IntegrityError):
        response = client.post(reverse("auth-register"), _private_register_form(membership.token))
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    assert response.data["code"] == "user_creation_failed"
    assert "_error_message" not in response.data
    assert membership.user is None


#################
# autehtication
#################

def test_get_auth_token_with_username(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": user.username,
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 200, response.data
    assert "auth_token" in response.data and response.data["auth_token"]
    assert "refresh" in response.data and response.data["refresh"]


def test_get_auth_token_with_username_case_insensitive(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": user.username.upper(),
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 200, response.data
    assert "auth_token" in response.data and response.data["auth_token"]
    assert "refresh" in response.data and response.data["refresh"]


def test_get_auth_token_with_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": user.email,
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 200, response.data
    assert "auth_token" in response.data and response.data["auth_token"]
    assert "refresh" in response.data and response.data["refresh"]


def test_get_auth_token_with_email_case_insensitive(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": user.email.upper(),
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 200, response.data
    assert "auth_token" in response.data and response.data["auth_token"]
    assert "refresh" in response.data and response.data["refresh"]


def test_get_auth_token_with_project_invitation(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None, email=user.email)

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": membership.token,
    }

    assert membership.user == None

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 200, response.data
    assert "auth_token" in response.data and response.data["auth_token"]
    assert "refresh" in response.data and response.data["refresh"]
    assert membership.user == user


def test_get_auth_token_with_project_invitation_case_insensitive_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None, email=user.email.upper())

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": membership.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 200, response.data
    assert membership.user == user


def test_get_auth_token_with_project_invitation_sent_to_another_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None, email="invited@email.com")

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": membership.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    assert response.data["code"] == "invitation_email_mismatch"
    assert "_error_message" not in response.data
    assert "auth_token" not in response.data
    assert membership.user is None
    # o e-mail convidado não aparece na resposta
    assert "invited@email.com" not in str(response.data)


def test_get_auth_token_with_project_invitation_without_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None, email=None)

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": membership.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 400, response.data
    # mesma resposta do e-mail diferente: os dois casos são indistinguíveis
    assert response.data["code"] == "invitation_email_mismatch"
    assert "_error_message" not in response.data
    assert "auth_token" not in response.data
    assert membership.user is None


def test_get_auth_token_with_unknown_project_invitation(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None)

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": "token-that-does-not-exist",
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 404, response.data
    assert response.data["code"] == "invitation_not_valid"
    assert "_error_message" not in response.data
    assert "auth_token" not in response.data
    assert membership.user is None


def test_get_auth_token_with_already_accepted_project_invitation(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    other_user = factories.UserFactory()
    membership = factories.MembershipFactory(user=other_user)

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": membership.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 404, response.data
    # convite já aceito responde igual ao token desconhecido
    assert response.data["code"] == "invitation_not_valid"
    assert "_error_message" not in response.data
    assert "auth_token" not in response.data
    assert membership.user == other_user


def test_get_auth_token_with_project_invitation_for_current_member(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    current_membership = factories.MembershipFactory(user=user)
    invitation = factories.MembershipFactory(user=None, project=current_membership.project,
                                             email=user.email)

    auth_data = {
        "username": user.username,
        "password": user.username,
        "invitation_token": invitation.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    invitation.refresh_from_db()

    assert response.status_code == 400, response.data
    assert response.data["code"] == "already_project_member"
    assert "_error_message" not in response.data
    assert "auth_token" not in response.data
    assert invitation.user is None
    assert Membership.objects.filter(user=user, project=current_membership.project).count() == 1


def test_get_auth_token_with_project_invitation_and_invalid_credentials(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None)

    auth_data = {
        "username": user.username,
        "password": "invalid password",
        "invitation_token": membership.token,
    }

    response = client.post(reverse("auth-external"), auth_data)
    membership.refresh_from_db()

    assert response.status_code == 401, response.data
    assert membership.user is None


def test_accept_invitation_helper_accepts_the_invitation(client):
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None, email=user.email)
    request = SimpleNamespace(DATA={"invitation_token": membership.token})

    AuthViewSet()._accept_invitation_if_any(request, {"id": user.id})
    membership.refresh_from_db()

    assert membership.user == user


def test_accept_invitation_helper_does_nothing_without_token(client):
    user = factories.UserFactory()
    membership = factories.MembershipFactory(user=None)
    request = SimpleNamespace(DATA={"username": user.username})

    AuthViewSet()._accept_invitation_if_any(request, {"id": user.id})
    membership.refresh_from_db()

    assert membership.user is None


def test_accept_invitation_helper_rejects_unknown_token(client):
    user = factories.UserFactory()
    request = SimpleNamespace(DATA={"invitation_token": "token-that-does-not-exist"})

    with pytest.raises(exc.NotFound) as excinfo:
        AuthViewSet()._accept_invitation_if_any(request, {"id": user.id})

    assert excinfo.value.detail == {"code": "invitation_not_valid"}


def test_accept_invitation_helper_rejects_an_unknown_user(client):
    membership = factories.MembershipFactory(user=None)
    request = SimpleNamespace(DATA={"invitation_token": membership.token})

    with pytest.raises(exc.NotFound) as excinfo:
        AuthViewSet()._accept_invitation_if_any(request, {"id": 0})

    assert excinfo.value.detail == {"code": "user_does_not_exist"}


def test_login_rejects_a_missing_recaptcha_with_a_code(client, settings):
    # a verificação continua a mesma: só a resposta deixa de ser texto
    settings.CAPCHA_USE = True
    user = factories.UserFactory()

    for route in ("auth-external", "auth-corporate"):
        response = client.post(reverse(route), {"username": user.username,
                                                "password": user.username})

        assert response.status_code == 400, response.data
        assert response.data["code"] == "invalid_recaptcha"
        assert "_error_message" not in response.data
        assert "auth_token" not in response.data


def test_both_login_routes_accept_project_invitation():
    # A rota corporativa depende do LDAP e não é exercitada de ponta a ponta nos testes:
    # o que se garante aqui é que as duas rotas passam pelo mesmo tratamento de convite.
    for action in (AuthViewSet.corporate, AuthViewSet.external):
        assert "_accept_invitation_if_any" in inspect.getsource(action)


def test_get_auth_token_error_invalid_credentials(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": "bad username",
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 401, response.data

    auth_data = {
        "username": user.username,
        "password": "invalid password",
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 401, response.data


def test_get_auth_token_error_inactive_user(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory(is_active=False)

    auth_data = {
        "username": user.username,
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 401, response.data


def test_get_auth_token_error_inactive_user(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory(is_active=False)

    auth_data = {
        "username": user.username,
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 401, response.data

def test_get_auth_token_error_system_user(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory(is_system=True)

    auth_data = {
        "username": user.username,
        "password": user.username,
    }

    response = client.post(reverse("auth-external"), auth_data)

    assert response.status_code == 401, response.data


def test_legacy_auth_route_does_not_authenticate(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    user = factories.UserFactory()

    auth_data = {
        "username": user.username,
        "password": user.username,
        "type": "normal",
    }

    # A rota herdada /api/v1/auth foi substituída por /auth/corporate e /auth/external
    response = client.post("/api/v1/auth", auth_data)

    assert response.status_code == 404, response.data


def test_auth_uppercase_ignore(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = True

    register_form = {"username": "Username",
                     "password": "password",
                     "full_name": "fname",
                     "email": "User@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 201

    #Only exists one user with the same lowercase version of username/password
    login_form = {"username": "Username",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 200

    login_form = {"username": "User@email.com",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 200

    # Email is case insensitive in the register process
    register_form = {"username": "username2",
                     "password": "password",
                     "full_name": "fname",
                     "email": "user@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

    # Username is case insensitive in the register process too
    register_form = {"username": "username",
                     "password": "password",
                     "full_name": "fname",
                     "email": "user2@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)
    assert response.status_code == 400

    #Now we create a legacy user so we have two users with the same lowercase version of username/email
    legacy_user = factories.UserFactory(
            username="username",
            full_name="fname",
            email="user@email.com")
    legacy_user.set_password("password")


    login_form = {"username": "Username",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 200

    login_form = {"username": "User@email.com",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 200

    # 2.- If we capitalize a new version it doesn't work with username
    login_form = {"username": "uSername",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 401

    # neither with the email
    login_form = {"username": "uSer@email.com",
                  "password": "password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 401


def test_login_fail_throttling(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = True
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = "1/minute"

    register_form = {"username": "valid_username_login_fail",
                     "password": "valid_password",
                     "full_name": "fullname",
                     "email": "valid_username_login_fail@email.com",
                     "accepted_terms": True,
                     "type": "public"}
    response = client.post(reverse("auth-register"), register_form)

    login_form = {"username": "valid_username_login_fail",
                  "password": "valid_password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 200, response.data

    login_form = {"username": "invalid_username_login_fail",
                  "password": "invalid_password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 401, response.data

    login_form = {"username": "invalid_username_login_fail",
                  "password": "invalid_password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 429, response.data

    login_form = {"username": "valid_username_login_fail",
                  "password": "valid_password"}

    response = client.post(reverse("auth-external"), login_form)
    assert response.status_code == 429, response.data

    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = None

