# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC
#

import uuid
from typing import Callable

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import IntegrityError
from django.db import transaction as tx

from taiga.base import exceptions as exc
from taiga.base.mails import mail_builder
from taiga.projects.services.invitations import get_unaccepted_membership_by_token
from taiga.projects.services.invitations import validate_invitation_email
from taiga.users.models import User
from taiga.users.serializers import UserAdminSerializer
from taiga.users.services import (
    get_and_validate_user, get_user_by_username_or_email,
    get_user_ldap_by_username_or_email_and_validate)

from .exceptions import AuthenticationFailed, InvalidToken, TokenError
from .functions import user_is_itaipuparquetec
from .ldap import LDAPConnectionService
from .settings import api_settings
from .signals import user_registered as user_registered_signal
from .tokens import CancelToken, RefreshToken, UntypedToken

#####################
## AUTH PLUGINS
#####################

auth_plugins = {}


def register_auth_plugin(name: str, login_func: Callable):
    auth_plugins[name] = {
        "login_func": login_func,
    }


def get_auth_plugins():
    return auth_plugins


def verify_recaptcha(recaptcha_response):
    """Verifica a resposta do reCAPTCHA usando a API do Google."""
    data = {
        'secret': settings.CAPCHA_SECRET_KEY,
        'response': recaptcha_response,
    }
    r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
    result = r.json()
    return result.get('success', False)

#####################
## AUTH SERVICES
#####################

def make_auth_response_data(user):
    serializer = UserAdminSerializer(user)
    data = dict(serializer.data)

    refresh = RefreshToken.for_user(user)

    data['refresh'] = str(refresh)
    data['auth_token'] = str(refresh.access_token)

    if api_settings.UPDATE_LAST_LOGIN:
        update_last_login(None, user)

    return data


#00LOGIN
# def login(username: str, password: str):
#     try:
#         user = get_user_by_username_or_email(username)
#         if user is None:
#             raise AuthenticationFailed('invalid_credentials',)
#         if user_is_itaipuparquetec(user.email):
#             # SE ITAIPUPARQUETEC
#             with LDAPConnectionService() as conn:
#                 _search = conn.search_user(username)
#                 if len(_search) == 0:
#                     raise AuthenticationFailed('invalid_credentials',)
#                 _login = conn.authenticate(_search[0].entry_dn, password)
#                 # VALIDAR SE O LOGIN LDAP FOI BEM SUCEDIDO
#                 if _login.bound:
#                     #VERIFICAR SE O USUÁRIO EXISTE NO BANCO
#                     _user = get_user_ldap_by_username_or_email_and_validate(username)
#                     if _user is None:
#                         raise AuthenticationFailed('undefined_credentials',)
#                     return make_auth_response_data(_user)
#                 else:
#                     # SE O LDAP NÃO VALIDOU O LOGIN
#                     raise AuthenticationFailed('undefined_credentials',)
#         else:
#             # SE DIFERENTE DE ITAIPUPARQUETEC
#             user = get_and_validate_user(username=username, password=password)
#             return make_auth_response_data(user)
#     except exc.WrongArguments:
#         raise AuthenticationFailed('undefined_credentials')


def login_ldap(username: str, password: str):
    """Login exclusivo via LDAP (acesso corporativo)."""
    try:
        with LDAPConnectionService() as conn:
            _search = conn.search_user(username)
            if len(_search) == 0:
                raise AuthenticationFailed({'code': 'invalid_credentials'})
            _login = conn.authenticate(_search[0].entry_dn, password)
            if not _login.bound:
                raise AuthenticationFailed({'code': 'invalid_credentials'})
            _user = get_user_ldap_by_username_or_email_and_validate(username)
            if _user is None:
                raise AuthenticationFailed({'code': 'undefined_credentials'})
            return make_auth_response_data(_user)
    except exc.WrongArguments:
        raise AuthenticationFailed({'code': 'undefined_credentials'})


def login_normal(username: str, password: str):
    """Login convencional por usuário/senha (acesso externo)."""
    try:
        user = get_user_by_username_or_email(username)
        if user_is_itaipuparquetec(user.email):
            raise AuthenticationFailed({'code': 'invalid_credentials'})
        if not user.check_password(password) or not user.is_active or user.is_system:
            raise AuthenticationFailed({'code': 'undefined_credentials'})
        return make_auth_response_data(user)
    except exc.WrongArguments:
        raise AuthenticationFailed({'code': 'undefined_credentials'})



def refresh_token(refresh_token: str):
    try:
        refresh = RefreshToken(refresh_token)
    except TokenError:
        raise InvalidToken()

    data = {'auth_token': str(refresh.access_token)}

    if api_settings.ROTATE_REFRESH_TOKENS:
        if api_settings.DENYLIST_AFTER_ROTATION:
            try:
                # Attempt to denylist the given refresh token
                refresh.denylist()
            except AttributeError:
                # If denylist app not installed, `denylist` method will
                # not be present
                pass

        refresh.set_jti()
        refresh.set_exp()

        data['refresh'] = str(refresh)

    return data


def verify_token(token: str):
    UntypedToken(token)
    return {}


#####################
## REGISTER SERVICES
#####################

def send_register_email(user) -> bool:
    """
    Given a user, send register welcome email
    message to specified user.
    """
    cancel_token = CancelToken.for_user(user)
    context = {"user": user, "cancel_token": str(cancel_token)}
    email = mail_builder.registered_user(user, context)
    return bool(email.send())


def is_user_already_registered(*, username:str, email:str) -> (bool, str):
    """
    Checks if a specified user is already registred.

    Returns a tuple containing a boolean value that indicates if the user exists
    and in case he does the code of the duplicated attribute. The code, not a
    message: the text shown to the user is the front-end's job.
    """
    user_model = get_user_model()
    if user_model.objects.filter(username__iexact=username).exists():
        return (True, "username_already_in_use")

    if user_model.objects.filter(email__iexact=email).exists():
        return (True, "email_already_in_use")

    return (False, None)


@tx.atomic
def public_register(username:str, password:str, email:str, full_name:str):
    """
    Given a parsed parameters, try register a new user
    knowing that it follows a public register flow.

    This can raise `exc.IntegrityError` exceptions in
    case of conflics found.

    :returns: User
    """

    is_registered, code = is_user_already_registered(username=username, email=email)
    if is_registered:
        raise exc.WrongArguments({"code": code})

    user_model = get_user_model()
    user = user_model(username=username,
                      email=email,
                      email_token=str(uuid.uuid4()),
                      new_email=email,
                      verified_email=False,
                      full_name=full_name,
                      read_new_terms=True)
    user.set_password(password)
    try:
        user.save()
    except IntegrityError:
        # mesmo evento do registro por convite: o servidor não conseguiu gravar o usuário
        raise exc.WrongArguments({"code": "user_creation_failed"})

    send_register_email(user)
    user_registered_signal.send(sender=user.__class__, user=user)
    return user


@tx.atomic
def private_register_for_new_user(token:str, username:str, email:str,
                                  full_name:str, password:str):
    """
    Given a inviation token, try register new user matching
    the invitation token.
    """
    is_registered, code = is_user_already_registered(username=username, email=email)
    if is_registered:
        raise exc.WrongArguments({"code": code})

    # O convite vale só para o e-mail convidado, e a checagem vem antes de criar
    # o usuário para que nada seja gravado quando o e-mail não confere.
    membership = get_unaccepted_membership_by_token(token)
    validate_invitation_email(membership, email)

    user_model = get_user_model()
    user = user_model(username=username,
                      email=email,
                      full_name=full_name,
                      email_token=str(uuid.uuid4()),
                      new_email=email,
                      verified_email=False,
                      read_new_terms=True)

    user.set_password(password)
    try:
        user.save()
    except IntegrityError:
        raise exc.WrongArguments({"code": "user_creation_failed"})

    membership.user = user
    membership.save(update_fields=["user"])
    send_register_email(user)
    user_registered_signal.send(sender=user.__class__, user=user)

    return user
