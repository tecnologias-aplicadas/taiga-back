# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from taiga.base.utils.files import get_file_path


def get_slide_image_file_path(instance, filename):
    return get_file_path(instance, filename, "news")


class Slide(models.Model):
    """
    Slide do carrossel de novidades da home pública. Não pertence a projeto;
    só superusuário grava, qualquer visitante lê os ativos.
    """
    image = models.FileField(upload_to=get_slide_image_file_path, max_length=500,
                             null=False, blank=False, verbose_name=_("image"))
    title = models.CharField(max_length=255, null=False, blank=False,
                             verbose_name=_("title"))
    description = models.TextField(null=False, blank=True, default="",
                                   verbose_name=_("description"))
    order = models.IntegerField(null=False, blank=True, default=10,
                                verbose_name=_("order"))
    is_active = models.BooleanField(null=False, blank=True, default=False,
                                    verbose_name=_("is active"))
    created_date = models.DateTimeField(null=False, blank=False, auto_now_add=True,
                                        verbose_name=_("created date"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL,
                                   related_name="news_slides_created",
                                   verbose_name=_("created by"))
    modified_date = models.DateTimeField(null=True, blank=True,
                                         verbose_name=_("modified date"))
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name="news_slides_modified",
                                    verbose_name=_("modified by"))

    class Meta:
        verbose_name = "slide"
        verbose_name_plural = "slides"
        ordering = ("order", "id")

    def __str__(self):
        return self.title
