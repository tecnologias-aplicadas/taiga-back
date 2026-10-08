# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import pytest

from django.core.files.uploadedfile import SimpleUploadedFile

from taiga.base import exceptions as exc
from taiga.base.utils.images import validate_image_file

from ..utils import DUMMY_BMP_DATA


def test_validate_image_file_accepts_an_image_and_rewinds_it():
    image = SimpleUploadedFile("logo.bmp", DUMMY_BMP_DATA)

    validate_image_file(image)

    assert image.tell() == 0
    assert image.read() == DUMMY_BMP_DATA


def test_validate_image_file_rejects_a_file_that_is_not_an_image():
    not_an_image = SimpleUploadedFile("logo.png", b"isto nao e uma imagem")

    with pytest.raises(exc.WrongArguments) as excinfo:
        validate_image_file(not_an_image)

    assert str(excinfo.value.detail) == "Invalid image format"


def test_validate_image_file_rejects_svg():
    svg = SimpleUploadedFile("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')

    with pytest.raises(exc.WrongArguments):
        validate_image_file(svg)
