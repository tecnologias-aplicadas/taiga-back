# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from settings.common import *  # noqa, pylint: disable=unused-wildcard-import

LANGUAGE_CODE = "en-us"

USE_I18N = True
USE_L10N = True

DEBUG = True

ENABLE_TELEMETRY = False

SECRET_KEY = "not very secret in tests"
CAPCHA_USE = False

TEMPLATES[0]["OPTIONS"]['context_processors'] += "django.template.context_processors.debug"

CELERY_ENABLED = False

MEDIA_ROOT = "/tmp"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
INSTALLED_APPS = INSTALLED_APPS + [
    "tests",
]

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon-write": None,
    "anon-read": None,
    "user-write": None,
    "user-read": None,
    "import-mode": None,
    "import-dump-mode": None,
    "create-memberships": None,
    "login-fail": None,
    "register-success": None,
    "user-detail": None,
    "user-update": None,
}


IMPORTERS['github']['active'] = True
IMPORTERS['jira']['active'] = True
IMPORTERS['asana']['active'] = True
IMPORTERS['trello']['active'] = True

FRONT_SITEMAP_ENABLED = True
FRONT_SITEMAP_CACHE_TIMEOUT = 1  # In second
FRONT_SITEMAP_PAGE_SIZE = 100

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'taiga',
#         'USER': 'taiga',
#         'PASSWORD': 'postgres',
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }

# DB correto com as nossas env's
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT','5437'),
        'OPTIONS': {'sslmode': os.getenv('POSTGRES_SSLMODE','disable')},
        'DISABLE_SERVER_SIDE_CURSORS': os.getenv('POSTGRES_DISABLE_SERVER_SIDE_CURSORS', 'False') == 'True',
    }
}

# This is only for GitHubActions
if os.getenv('GITHUB_WORKFLOW'):
    DATABASES = {
        'default': {
            "ENGINE": "django.db.backends.postgresql",
            'NAME': 'taiga',
            'USER': 'postgres',
            'PASSWORD': 'postgres',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }

#########################################
## EVENTS BACKEND FOR TESTS
#########################################
# EVENTS_PUSH_BACKEND = "taiga.events.backends.rabbitmq.EventsPushBackend"
# Usa backend dummy durante testes para não exigir RabbitMQ disponível.
# Em execução normal o valor vem do .env via settings/common.py.
_running_under_pytest = bool(os.getenv('PYTEST_CURRENT_TEST') or any('pytest' in arg for arg in sys.argv))
EVENTS_PUSH_BACKEND = (
    "taiga.events.backends.dummy.EventsPushBackend"
    if _running_under_pytest
    else os.getenv('EVENTS_PUSH_BACKEND', "taiga.events.backends.rabbitmq.EventsPushBackend")
)

EVENTS_PUSH_BACKEND_OPTIONS = {
    "url": os.getenv('EVENTS_PUSH_BACKEND_URL', "amqp://guest:guest@localhost:5672/taiga")
}

TAIGA_ADMIN_TEAM = os.getenv('TAIGA_ADMIN_TEAM', 'Server Admins')