# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from taiga.base.api import serializers
from taiga.base.api import validators
from taiga.base.exceptions import ValidationError
from taiga.base import exceptions as exc
from taiga.base.utils.images import validate_image_file

from . import models

# Limites validados no servidor (cartão 20)
NEWS_SLIDE_MAX_IMAGE_SIZE = 2 * 1024 * 1024   # 2 MB
NEWS_SLIDE_MAX_TITLE_LENGTH = 255
NEWS_SLIDE_MAX_DESCRIPTION_LENGTH = 500


class SlideValidator(validators.ModelValidator):
    title = serializers.CharField(max_length=NEWS_SLIDE_MAX_TITLE_LENGTH,
                                  error_messages={"required": "title_required",
                                                  "max_length": "title_too_long"})
    description = serializers.CharField(required=False, default="",
                                        max_length=NEWS_SLIDE_MAX_DESCRIPTION_LENGTH,
                                        error_messages={"max_length": "description_too_long"})
    order = serializers.IntegerField(required=False,
                                     error_messages={"invalid": "order_invalid"})
    image = serializers.FileField(required=False,
                                  error_messages={"invalid": "invalid_image",
                                                  "empty": "invalid_image"})

    class Meta:
        model = models.Slide
        read_only_fields = ("id", "created_date", "created_by", "modified_date", "modified_by")

    def validate_order(self, attrs, source):
        order = attrs.get(source, None)
        if order is not None and order < 0:
            raise ValidationError("order_negative")
        return attrs

    def validate_image(self, attrs, source):
        image = attrs.get(source, None)

        if image is None:
            # Obrigatória ao criar; ao editar, ausente significa manter a atual
            if self.object is None:
                raise ValidationError("image_required")
            attrs.pop(source, None)
            return attrs

        if image.size > NEWS_SLIDE_MAX_IMAGE_SIZE:
            raise ValidationError("image_too_large")

        try:
            validate_image_file(image)
        except exc.WrongArguments:
            raise ValidationError("invalid_image")

        return attrs


class UpdateSlideOrderBulkValidator(validators.Validator):
    slide_id = serializers.IntegerField(error_messages={"required": "slide_id_required",
                                                        "invalid": "slide_id_invalid"})
    order = serializers.IntegerField(error_messages={"required": "order_required",
                                                     "invalid": "order_invalid"})

    def validate_order(self, attrs, source):
        if attrs.get(source, 0) < 0:
            raise ValidationError("order_negative")
        return attrs
