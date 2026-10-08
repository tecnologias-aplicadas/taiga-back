# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.core.exceptions import ObjectDoesNotExist

from taiga.events import events
from taiga.events import middleware as mw


def emit_epic_change_when_related_userstory_changes(sender, instance, **kwargs):
    """A ligação história–épica não tem project_id, então o canal de eventos
    a ignora; avisa como mudança da épica dona, na chave de épicas do projeto."""
    if getattr(instance, "_importing", False):
        return

    try:
        epic = instance.epic
    except ObjectDoesNotExist:
        return

    events.emit_event_for_model(epic, sessionid=mw.get_current_session_id(), type="change")
