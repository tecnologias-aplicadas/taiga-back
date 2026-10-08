# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.utils import timezone

from taiga.base import exceptions as exc
from taiga.base import response
from taiga.base.api import ModelCrudViewSet
from taiga.base.decorators import list_route

from . import models
from . import permissions
from . import serializers
from . import services
from . import validators


class SlideViewSet(ModelCrudViewSet):
    """
    Carrossel de novidades da home pública. Leitura aberta (só slides
    ativos para quem não é superusuário); escrita só de superusuário.
    """
    model = models.Slide
    validator_class = validators.SlideValidator
    permission_classes = (permissions.SlidePermission,)
    ordering = ("order", "id")

    def get_queryset(self):
        qs = models.Slide.objects.all()
        user = self.request.user
        if not (user.is_authenticated and user.is_superuser):
            qs = qs.filter(is_active=True)
        return qs.order_by(*self.ordering)

    def get_serializer_class(self):
        user = self.request.user
        if user.is_authenticated and user.is_superuser:
            return serializers.SlideAdminSerializer
        return serializers.SlideSerializer

    def list(self, request, *args, **kwargs):
        self.check_permissions(request, "list", None)
        return super().list(request, *args, **kwargs)

    def pre_save(self, obj):
        if obj.id is None:
            obj.created_by = self.request.user
        else:
            obj.modified_by = self.request.user
            obj.modified_date = timezone.now()
        super().pre_save(obj)

    @list_route(methods=["POST"])
    def bulk_update_order(self, request, **kwargs):
        self.check_permissions(request, "bulk_update_order", None)

        validator = validators.UpdateSlideOrderBulkValidator(data=request.DATA, many=True)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        if not validator.data:
            raise exc.BadRequest({"code": "empty_bulk"})

        missing_ids = services.update_slides_order_in_bulk(validator.data)
        if missing_ids:
            raise exc.BadRequest({"code": "slide_not_found", "ids": missing_ids})

        return response.NoContent()
