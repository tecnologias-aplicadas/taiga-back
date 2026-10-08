# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import re

from django.core.exceptions import ImproperlyConfigured


LOGIN_FAIL_RATE_DEFAULT = "5/minute"

# Formato aceito pelo SimpleRateThrottle do DRF: "<n>/<período>", em que só a primeira
# letra do período importa (s, m, h, d), ex.: "5/minute", "10/hour", "1/min", "3/s".
_LOGIN_FAIL_RATE_FORMAT = re.compile(r"^(\d+)/([smhd][a-z]*)$")


def login_fail_rate_from_env(valor):
    """
    Interpreta a variável de ambiente LOGIN_FAIL_RATE, que limita tentativas
    falhas de login por origem nas rotas de autenticação.

    - ausente (None)   -> LOGIN_FAIL_RATE_DEFAULT (limite ligado por padrão)
    - vazia ("")       -> None (limite desligado)
    - "<n>/<período>"  -> a própria taxa, no formato do DRF
    - qualquer outro   -> ImproperlyConfigured, para o processo não subir com
                          uma taxa que faria todo login responder 500
    """
    if valor is None:
        return LOGIN_FAIL_RATE_DEFAULT

    valor = valor.strip()
    if valor == "":
        return None

    match = _LOGIN_FAIL_RATE_FORMAT.match(valor)
    if match is None or int(match.group(1)) < 1:
        raise ImproperlyConfigured(
            "LOGIN_FAIL_RATE inválida: %r. Use \"<n>/<período>\" no formato do DRF "
            "(ex.: \"5/minute\", \"10/hour\") ou deixe vazia para desligar o limite." % valor
        )

    return valor
