# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from taiga.projects.epics.models import Epic


class Command(BaseCommand):
    help = 'Atualiza completion_percent dos Epics baseado nas user stories'

    def handle(self, *args, **options):
        updated_count = 0
        
        for epic in Epic.objects.all():
            new_percent = epic.calculate_completion_percent()
            if epic.completion_percent != new_percent:
                epic.completion_percent = new_percent
                epic.save(update_fields=['completion_percent'])
                updated_count += 1
                self.stdout.write(f"✅ {epic.project.name} - {epic.subject}: {new_percent}%")
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Atualizados {updated_count} Epics')
        )