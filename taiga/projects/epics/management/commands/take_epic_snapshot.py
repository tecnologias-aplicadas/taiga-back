# -*- coding: utf-8 -*-
#
# take_epic_snapshot
# ──────────────────
# Management command responsável por registrar mensalmente o estado de cada
# épica de todos os projetos ativos no sistema.
#
# COMO FUNCIONA
#   Para cada projeto ativo (sem end_date anterior ao mês atual), percorre
#   todas as épicas e grava ou atualiza um registro em EpicMonthlySnapshot
#   referente ao mês corrente (YYYY-MM). Os campos capturados são:
#     - completion_percent_done  : percentual de conclusão no momento da execução
#     - percentage_impact        : peso da épica no escopo (0–100)
#     - schedulable              : se é planejável ou não
#     - is_closed                : se o status da épica é do tipo encerrado
#     - snapshot_date            : preenchido automaticamente pelo banco (auto_now_add)
#
#   Registros de meses anteriores nunca são sobrescritos — apenas o mês atual
#   pode ser criado ou atualizado. Isso garante a imutabilidade do histórico.
#
# QUANDO EXECUTAR
#   Recomenda-se agendar via cron para rodar no último dia de cada mês:
#     0 23 28-31 * * [ "$(date +\%d)" = "$(cal | awk '/^[ 0-9]/{last=$NF} END{print last}')" ] \
#       && python manage.py take_epic_snapshot
#
#   Ou de forma simplificada, no dia 1 do mês seguinte às 00:05 (captura o
#   estado final do mês anterior ainda vigente no banco):
#     5 0 1 * * python manage.py take_epic_snapshot
#
# COMO TESTAR MANUALMENTE
#   1. Certifique-se de que existem épicas cadastradas em pelo menos um projeto.
#   2. Execute:
#        python manage.py take_epic_snapshot
#   3. Verifique o resultado no banco:
#        SELECT year_month, epic_id, completion_percent_done, schedulable, is_closed, snapshot_date
#        FROM epics_epicmonthlysnapshot
#        ORDER BY snapshot_date DESC
#        LIMIT 20;
#   4. Execute novamente e confirme que os registros do mês atual foram
#      atualizados (não duplicados).
#   5. Para testar o bloqueio de projetos encerrados, defina end_date de um
#      projeto para um mês anterior ao atual e confirme que nenhum snapshot
#      foi criado para as épicas daquele projeto.
#
# TESTES AUTOMATIZADOS
#   tests/integration/test_epic_monthly_snapshot.py → classe TestTakeEpicSnapshot
#

from datetime import date

from django.core.management.base import BaseCommand

from taiga.projects.models import Project
from taiga.projects.epics.models import EpicMonthlySnapshot


class Command(BaseCommand):
    help = (
        "Cria/atualiza o snapshot mensal de todas as épicas de projetos ativos. "
        "Deve ser executado mensalmente. Snapshots de meses anteriores não são sobrescritos."
    )

    def handle(self, *args, **options):
        today = date.today()
        current_ym = today.strftime("%Y-%m")

        projects = Project.objects.all()
        created = 0
        skipped = 0
        self.stdout.write(
            self.style.WARNING(
                "(snapshot) Iniciando snapshot mensal de épicas em projetos ativos para o mês: %s" % current_ym+"\n"+
                "(snapshot) Projetos com end_date anterior a %s serão ignorados." % current_ym
            )
        )

        for project in projects:
            # Não gera snapshot para projetos já encerrados (end_date no passado)
            if project.end_date and project.end_date.strftime("%Y-%m") < current_ym:
                skipped += project.epics.count()
                continue

            epics = project.epics.select_related("status").all()
            for epic in epics:
                # Epicas sem valor definido para schedulable são ignoradas
                if epic.schedulable is None:
                    continue

                existing = EpicMonthlySnapshot.objects.filter(
                    epic=epic, year_month=current_ym
                ).first()

                cpd = int(epic.completion_percent_done)
                is_closed = epic.status is not None and epic.status.is_closed

                if existing is None:
                    EpicMonthlySnapshot.objects.create(
                        epic=epic,
                        project=project,
                        year_month=current_ym,
                        completion_percent_done=cpd,
                        percentage_impact=epic.percentage_impact,
                        schedulable=epic.schedulable,
                        is_closed=is_closed,
                    )
                    created += 1
                else:
                    existing.completion_percent_done = cpd
                    existing.percentage_impact = epic.percentage_impact
                    existing.schedulable = epic.schedulable
                    existing.is_closed = is_closed
                    existing.save(update_fields=["completion_percent_done", "percentage_impact", "schedulable", "is_closed"])
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS("(snapshot) Registros criados: %s" % created)+"\n"+
            self.style.SUCCESS("(snapshot) Registros atualizados: %s" % skipped)
        )
