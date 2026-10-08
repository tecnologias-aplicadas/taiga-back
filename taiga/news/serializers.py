# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from taiga.base.api import serializers
from taiga.base.fields import Field, MethodField
from taiga.base.utils.urls import get_absolute_url


class SlideSerializer(serializers.LightSerializer):
    """
    Leitura pública: o que a home precisa, sem autoria nem estado.
    """
    id = Field()
    image_url = MethodField()
    title = Field()
    description = Field()
    order = Field()

    def get_image_url(self, obj):
        if not obj.image:
            return None
        return get_absolute_url(obj.image.url)


class SlideAdminSerializer(SlideSerializer):
    """
    Leitura do superusuário: inclui ativo, autoria e datas.
    """
    is_active = Field()
    created_date = Field()
    created_by = Field(attr="created_by_id")
    modified_date = Field()
    modified_by = Field(attr="modified_by_id")
