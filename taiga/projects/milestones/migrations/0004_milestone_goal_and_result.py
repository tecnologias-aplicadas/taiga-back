# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Mesmo literal de taiga.projects.milestones.models.OBJETIVO_LEGADO
# (migration não importa do modelo). Preenche as sprints já existentes (RN09ADQ)
# e a coluna fica sem default (preserve_default=False).
OBJETIVO_LEGADO = "Objetivo descrito em documento separado, existente antes da release V2"


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('milestones', '0003_auto_20200615_0811'),
    ]

    operations = [
        migrations.AddField(
            model_name='milestone',
            name='goal',
            field=models.TextField(default=OBJETIVO_LEGADO, verbose_name='goal'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='milestone',
            name='goal_achievement',
            field=models.CharField(blank=True, choices=[('achieved', 'Achieved'), ('partially_achieved', 'Partially achieved'), ('not_achieved', 'Not achieved')], max_length=20, null=True, verbose_name='goal achievement'),
        ),
        migrations.AddField(
            model_name='milestone',
            name='result',
            field=models.TextField(blank=True, null=True, verbose_name='result'),
        ),
        migrations.AddField(
            model_name='milestone',
            name='result_date',
            field=models.DateTimeField(blank=True, null=True, verbose_name='result date'),
        ),
        migrations.AddField(
            model_name='milestone',
            name='result_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='milestone_results', to=settings.AUTH_USER_MODEL, verbose_name='result registered by'),
        ),
        migrations.AddConstraint(
            model_name='milestone',
            constraint=models.CheckConstraint(check=models.Q(('goal_achievement__isnull', True), ('result__isnull', False), _connector='OR'), name='milestone_achievement_requires_result'),
        ),
    ]
