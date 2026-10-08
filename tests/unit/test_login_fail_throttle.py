# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from types import SimpleNamespace

import pytest

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.models import AnonymousUser

from settings import login_fail_rate_from_env, LOGIN_FAIL_RATE_DEFAULT
from taiga.auth.throttling import LoginFailRateThrottle


#################
# ações cobertas pelo limite
#################

def test_login_fail_throttle_covers_current_login_routes():
    assert "corporate" in LoginFailRateThrottle.throttled_actions
    assert "external" in LoginFailRateThrottle.throttled_actions


def test_login_fail_throttle_keeps_legacy_actions():
    for action in ("create", "refresh", "verify"):
        assert action in LoginFailRateThrottle.throttled_actions


def _login_view(action):
    return SimpleNamespace(action=action)


def _anonymous_post(rf, path):
    request = rf.post(path)
    request.user = AnonymousUser()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    return request


def _assert_action_blocked_after_one_failure(settings, rf, action):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = "1/minute"
    request = _anonymous_post(rf, "/api/v1/auth/%s" % action)
    view = _login_view(action)

    throttle = LoginFailRateThrottle()
    assert throttle.allow_request(request, view)
    throttle.finalize(request, SimpleNamespace(status_code=401), view)

    assert LoginFailRateThrottle().allow_request(request, view) is False

    cache.clear()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = None


def test_login_fail_throttle_blocks_corporate_after_failure(settings, rf):
    # Não há simulação de LDAP nos testes; a ação "corporate" é provada no próprio throttle.
    _assert_action_blocked_after_one_failure(settings, rf, "corporate")


def test_login_fail_throttle_blocks_external_after_failure(settings, rf):
    _assert_action_blocked_after_one_failure(settings, rf, "external")


def test_login_fail_throttle_ignores_other_actions(settings, rf):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = "1/minute"
    request = _anonymous_post(rf, "/api/v1/auth/config")
    view = _login_view("config")

    throttle = LoginFailRateThrottle()
    for x in range(10):
        assert throttle.allow_request(request, view)

    cache.clear()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = None


def test_login_fail_throttle_does_not_count_successful_login(settings, rf):
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = "1/minute"
    request = _anonymous_post(rf, "/api/v1/auth/external")
    view = _login_view("external")

    throttle = LoginFailRateThrottle()
    assert throttle.allow_request(request, view)
    throttle.finalize(request, SimpleNamespace(status_code=200), view)

    assert LoginFailRateThrottle().allow_request(request, view)

    cache.clear()
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login-fail"] = None


#################
# variável de ambiente LOGIN_FAIL_RATE
#################

def test_login_fail_rate_default_when_env_missing():
    assert login_fail_rate_from_env(None) == LOGIN_FAIL_RATE_DEFAULT
    assert LOGIN_FAIL_RATE_DEFAULT == "5/minute"


def test_login_fail_rate_disabled_when_env_empty():
    assert login_fail_rate_from_env("") is None
    assert login_fail_rate_from_env("   ") is None


@pytest.mark.parametrize("valor", ["5/minute", "10/hour", "1/min", "3/s", "20/day"])
def test_login_fail_rate_keeps_valid_value(valor):
    assert login_fail_rate_from_env(valor) == valor


def test_login_fail_rate_strips_surrounding_spaces():
    assert login_fail_rate_from_env(" 5/minute ") == "5/minute"


@pytest.mark.parametrize("valor", ["5 por minuto", "abc", "5/", "/minute", "5/years", "0/minute", "5/Minute", "cinco/minute"])
def test_login_fail_rate_rejects_invalid_format(valor):
    with pytest.raises(ImproperlyConfigured) as excinfo:
        login_fail_rate_from_env(valor)
    assert "LOGIN_FAIL_RATE" in str(excinfo.value)
