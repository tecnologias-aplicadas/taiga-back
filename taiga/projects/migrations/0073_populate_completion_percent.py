# 0073_populate_completion_percent.py
from django.db import migrations

def set_initial_completion_percent(apps, schema_editor):
    TaskStatus = apps.get_model('projects', 'TaskStatus')
    for status in TaskStatus.objects.all():
        status.completion_percent = 100 if getattr(status, 'is_closed', False) else None
        status.save(update_fields=['completion_percent'])

def unset_completion_percent(apps, schema_editor):
    TaskStatus = apps.get_model('projects', 'TaskStatus')
    TaskStatus.objects.update(completion_percent=None)

class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0072_alter_taskstatus_completion_percent'),
    ]

    operations = [
        migrations.RunPython(set_initial_completion_percent, reverse_code=unset_completion_percent)
    ]
