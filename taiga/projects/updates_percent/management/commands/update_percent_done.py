# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from taiga.projects.tasks.models import Task
from taiga.projects.userstories.models import UserStory
from taiga.projects.epics.models import Epic
from taiga.projects.models import TaskStatus

# Este comando precisa ser rodado apenas 1x. Caso sua versão ainda não tinha a migração 0069, então
# é a hora certa de rodar, pois a migração 0069 é a que introduz os campos completion_percent_done e completion_percent_progress
# Este comando regulariza os campos conforme as tasks com status is_closed, atribuindo 100% do done
# e refletindo nas histórias e épicos relacionados.
class Command(BaseCommand):
    help = 'Regulariza completion_percent_done e completion_percent_progress no banco'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            '\n⚠️  ATENÇÃO: Este comando deve ser executado UMA ÚNICA VEZ, '
            'imediatamente após o deploy da migration 0069.\n'
            'Se essa migration foi aplicada há algum tempo e o sistema já está em uso, '
            'a execução pode sobrescrever dados de progresso registrados pelos usuários, '
            'resultando em perda de informações.\n'
        ))
        confirmacao = input('Deseja realmente continuar? Digite "y" para confirmar: ').strip().lower()
        if confirmacao != 'y':
            self.stdout.write(self.style.ERROR('Operação cancelada.'))
            return

        task_count = 0
        affected_us_ids = set()
        affected_epic_ids = set()

        # 0. Atualizar completion_percent dos TaskStatus pelo slug
        self.stdout.write("Atualizando TaskStatus...")
        slug_percent_map = {
            'revisao': 90,
            'in-progress': 5,
            'a-iniciar': 0,
            'em-teste': 50,
        }
        for slug, percent in slug_percent_map.items():
            updated = TaskStatus.objects.filter(slug=slug).update(completion_percent=percent)
            self.stdout.write(f'  slug={slug}: {updated} registro(s) atualizado(s)')

        # 1. Atualizar Tasks baseado no status
        # Os signals do post_save já propagam para USs e Épicas automaticamente.
        self.stdout.write("Atualizando Tasks...")
        for task in Task.objects.all():
            old_done = task.completion_percent_done
            old_progress = task.completion_percent_progress

            # Recalcular completion_percent_done baseado no status
            if task.status and task.status.is_closed:
                task.completion_percent_done = 100
            else:
                task.completion_percent_done = 0

            # Manter completion_percent_progress sincronizado com TaskStatus (None vira 0)
            if task.status and hasattr(task.status, 'completion_percent'):
                task.completion_percent_progress = task.status.completion_percent if task.status.completion_percent is not None else 0

            if old_done != task.completion_percent_done or old_progress != task.completion_percent_progress:
                task.save(update_fields=['completion_percent_done', 'completion_percent_progress'])
                task_count += 1
                if task.user_story_id:
                    affected_us_ids.add(task.user_story_id)

        # 2. Atualizar UserStories — signals do passo 1 já propagaram,
        # mas garantimos cobertura de USs sem tasks e contamos as afetadas.
        self.stdout.write("Atualizando UserStories...")
        us_propagated_count = 0
        us_direct_count = 0
        for us in UserStory.objects.all():
            updated = us.update_completion_percent()
            if us.id in affected_us_ids:
                us_propagated_count += 1
                for epic in us.epics.all():
                    affected_epic_ids.add(epic.id)
            elif updated:
                us_direct_count += 1
                for epic in us.epics.all():
                    affected_epic_ids.add(epic.id)

        # 3. Atualizar Epics — garante cobertura de Épicas sem USs.
        self.stdout.write("Atualizando Epics...")
        epic_propagated_count = 0
        epic_direct_count = 0
        for epic in Epic.objects.all():
            updated = epic.update_completion_percent()
            if epic.id in affected_epic_ids:
                epic_propagated_count += 1
            elif updated:
                epic_direct_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Regularização concluída!\n'
                f'- Tasks: {task_count} atualizadas\n'
                f'- UserStories propagadas de task: {us_propagated_count} | atualizadas diretamente: {us_direct_count}\n'
                f'- Epics propagados de task: {epic_propagated_count} | atualizados diretamente: {epic_direct_count}'
            )
        )