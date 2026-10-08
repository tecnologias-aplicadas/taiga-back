# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from .base import BaseEventsPushBackend


class EventsPushBackend(BaseEventsPushBackend):
    """No-op backend for use in tests — discards all events silently."""

    def __init__(self, **kwargs):
        pass

    def emit_event(self, message: str, *, routing_key: str, channel: str = "events"):
        pass