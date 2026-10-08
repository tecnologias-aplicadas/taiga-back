# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from taiga.projects.userstories.models import UserStory


class Command(BaseCommand):
    help = 'Atualiza completion_percent das UserStories baseado nas tasks'

    def handle(self, *args, **options):
        updated_count = 0
        
        for us in UserStory.objects.all():
            new_percent = us.calculate_completion_percent()
            if us.completion_percent != new_percent:
                us.completion_percent = new_percent
                us.save(update_fields=['completion_percent'])
                updated_count += 1
                self.stdout.write(f"{us.project.name} - {us.subject}: {new_percent}%")
        
        self.stdout.write(
            self.style.SUCCESS(f'Atualizadas {updated_count} UserStories')
        )