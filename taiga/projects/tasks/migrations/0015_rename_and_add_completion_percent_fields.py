# -*- coding: utf-8 -*-
# Generated manually

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0014_task_completion_percent'),
    ]

    operations = [
        # Renomear completion_percent para completion_percent_progress
        migrations.RenameField(
            model_name='task',
            old_name='completion_percent',
            new_name='completion_percent_progress',
        ),
        
        # Adicionar novo campo completion_percent_done
        migrations.AddField(
            model_name='task',
            name='completion_percent_done',
            field=models.IntegerField(
                default=0,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(100)
                ],
                help_text='Percentual de conclusão (0 a 100)',
                verbose_name='completion percent done'
            ),
        ),
    ]