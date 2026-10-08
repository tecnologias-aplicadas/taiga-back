# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.db import migrations


# Mesmo literal de taiga.projects.milestones.models.RESULTADO_LEGADO
# (migration não importa do modelo).
RESULTADO_LEGADO = "Resultado descrito em documento separado, existente antes da release V2"


def preencher_resultado_legado(apps, schema_editor):
    """Sprints já fechadas antes da V2 recebem o texto fixo como resultado (RN09ADQ).
    Alcance, data e autor do resultado ficam nulos."""
    Milestone = apps.get_model("milestones", "Milestone")
    Milestone.objects.filter(closed=True, result__isnull=True).update(result=RESULTADO_LEGADO)


def limpar_resultado_legado(apps, schema_editor):
    Milestone = apps.get_model("milestones", "Milestone")
    Milestone.objects.filter(result=RESULTADO_LEGADO).update(result=None)


class Migration(migrations.Migration):

    dependencies = [
        ('milestones', '0004_milestone_goal_and_result'),
    ]

    operations = [
        migrations.RunPython(preencher_resultado_legado, limpar_resultado_legado),
    ]
