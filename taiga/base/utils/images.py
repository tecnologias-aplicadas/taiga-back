# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.utils.translation import gettext as _
from easy_thumbnails.source_generators import pil_image

from taiga.base import exceptions as exc


def validate_image_file(file_obj):
    """
    Garante que o arquivo enviado é uma imagem que o Pillow abre (a mesma
    validação da logo de projeto e do avatar). Levanta `WrongArguments`
    quando não é imagem e devolve o ponteiro do arquivo ao início.
    """
    try:
        pil_image(file_obj)
    except Exception:
        raise exc.WrongArguments(_("Invalid image format"))

    file_obj.seek(0)
