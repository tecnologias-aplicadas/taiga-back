# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from taiga.base.api.permissions import TaigaResourcePermission
from taiga.base.api.permissions import AllowAny
from taiga.base.api.permissions import IsSuperUser


class SlidePermission(TaigaResourcePermission):
    """
    Qualquer visitante lê; só superusuário grava (administrador de
    projeto e membro são usuários comuns aqui).
    """
    list_perms = AllowAny()
    retrieve_perms = AllowAny()
    create_perms = IsSuperUser()
    update_perms = IsSuperUser()
    partial_update_perms = IsSuperUser()
    destroy_perms = IsSuperUser()
    bulk_update_order_perms = IsSuperUser()
