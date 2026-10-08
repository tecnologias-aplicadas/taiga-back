# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.db import transaction

from . import models


@transaction.atomic
def update_slides_order_in_bulk(bulk_data):
    """
    Grava a ordem de vários slides numa transação.
    `bulk_data` é uma lista de dicts: [{"slide_id": <id>, "order": <int>}, ...]
    Devolve a lista de ids que não existem (a transação só se completa se vazia).
    """
    wanted_ids = {item["slide_id"] for item in bulk_data}
    existing_ids = set(models.Slide.objects.filter(id__in=wanted_ids)
                                           .values_list("id", flat=True))
    missing_ids = sorted(wanted_ids - existing_ids)
    if missing_ids:
        return missing_ids

    for item in bulk_data:
        models.Slide.objects.filter(id=item["slide_id"]).update(order=item["order"])

    return []
