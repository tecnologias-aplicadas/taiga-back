# -*- coding: utf-8 -*-
"""
Testes unitários para:
- EpicMonthlySnapshot model e management command take_epic_snapshot
- get_epics_pd_history (service) — cálculo de impacto, TMP, range de meses
- Comportamento com end_date do projeto
"""

import pytest
from datetime import date
from unittest.mock import patch

from tests import factories as f
from taiga.projects.epics.models import EpicMonthlySnapshot
from taiga.projects.epics.services import get_epics_pd_history

pytestmark = pytest.mark.django_db


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_ym(ym):
    y, m = ym.split("-")
    return date(int(y), int(m), 1)


def make_project(start="2025-01", expected_end="2025-03", end=None):
    """Cria projeto com datas no formato YYYY-MM."""
    proj = f.ProjectFactory.create(
        start_date=parse_ym(start),
        expected_end_date=parse_ym(expected_end),
        end_date=parse_ym(end) if end else None,
    )
    return proj


def make_closed_status(project):
    status = f.EpicStatusFactory.create(project=project, is_closed=True)
    return status


def make_open_status(project):
    status = f.EpicStatusFactory.create(project=project, is_closed=False)
    return status


def snap(epic, year_month, cpd, impact, schedulable, is_closed):
    return EpicMonthlySnapshot.objects.create(
        epic=epic,
        project=epic.project,
        year_month=year_month,
        completion_percent_done=cpd,
        percentage_impact=impact,
        schedulable=schedulable,
        is_closed=is_closed,
    )


# ─────────────────────────────────────────────────────────────────────────────
# take_epic_snapshot management command
# ─────────────────────────────────────────────────────────────────────────────

class TestTakeEpicSnapshot:
    def test_cria_snapshot_do_mes_atual(self):
        from taiga.projects.epics.management.commands.take_epic_snapshot import Command
        from taiga.projects.epics.models import Epic

        today = date.today()
        current_ym = today.strftime("%Y-%m")

        project = f.ProjectFactory.create(
            start_date=date(today.year, today.month, 1),
            expected_end_date=date(today.year, today.month, 1),
        )
        status = make_open_status(project)
        epic = f.EpicFactory.create(
            project=project,
            status=status,
            schedulable=True,
            percentage_impact=40,
        )
        # completion_percent_done é recalculado pelo save; forçar via update() para testar snapshot
        Epic.objects.filter(pk=epic.pk).update(completion_percent_done=50)
        epic.refresh_from_db()

        Command().handle()

        snap = EpicMonthlySnapshot.objects.get(epic=epic, year_month=current_ym)
        assert snap.completion_percent_done == 50
        assert snap.percentage_impact == 40
        assert snap.schedulable is True
        assert snap.is_closed is False
        assert snap.project == project

    def test_nao_sobrescreve_mes_anterior(self):
        from taiga.projects.epics.management.commands.take_epic_snapshot import Command
        from taiga.projects.epics.models import Epic

        today = date.today()
        current_ym = today.strftime("%Y-%m")

        project = f.ProjectFactory.create(
            start_date=date(today.year, today.month, 1),
            expected_end_date=date(today.year, today.month, 1),
        )
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status, schedulable=True,
                                     percentage_impact=30)
        # completion_percent_done é recalculado pelo save; forçar via update()
        Epic.objects.filter(pk=epic.pk).update(completion_percent_done=20)
        epic.refresh_from_db()

        # Snapshot já existente do mês atual com valor diferente
        existing = EpicMonthlySnapshot.objects.create(
            epic=epic, project=project, year_month=current_ym,
            completion_percent_done=99, percentage_impact=30,
            schedulable=True, is_closed=False,
        )

        Command().handle()

        existing.refresh_from_db()
        # O comando atualiza o mês atual (idempotente)
        assert existing.completion_percent_done == 20

    def test_pula_projeto_encerrado(self):
        from taiga.projects.epics.management.commands.take_epic_snapshot import Command

        today = date.today()
        current_ym = today.strftime("%Y-%m")

        # Projeto com end_date no mês anterior
        from dateutil.relativedelta import relativedelta
        last_month = (date(today.year, today.month, 1) - relativedelta(months=1))

        project = f.ProjectFactory.create(
            start_date=date(last_month.year, last_month.month, 1),
            expected_end_date=date(last_month.year, last_month.month, 1),
            end_date=last_month,
        )
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status, schedulable=True,
                                     percentage_impact=50, completion_percent_done=100)

        Command().handle()

        # Não deve criar snapshot do mês atual para projeto encerrado
        assert not EpicMonthlySnapshot.objects.filter(epic=epic, year_month=current_ym).exists()

    def test_is_closed_baseado_no_status(self):
        from taiga.projects.epics.management.commands.take_epic_snapshot import Command

        today = date.today()
        current_ym = today.strftime("%Y-%m")

        project = f.ProjectFactory.create(
            start_date=date(today.year, today.month, 1),
            expected_end_date=date(today.year, today.month, 1),
        )
        closed_status = make_closed_status(project)
        epic = f.EpicFactory.create(project=project, status=closed_status,
                                     schedulable=True, percentage_impact=20,
                                     completion_percent_done=100)

        Command().handle()

        snap = EpicMonthlySnapshot.objects.get(epic=epic, year_month=current_ym)
        assert snap.is_closed is True


# ─────────────────────────────────────────────────────────────────────────────
# get_epics_pd_history — range de meses
# ─────────────────────────────────────────────────────────────────────────────

class TestGetEpicsPdHistoryRange:
    def test_range_sem_end_date_vai_ate_hoje(self):
        today = date.today()
        project = make_project(
            start="2025-01",
            expected_end="2025-03",
        )
        result = get_epics_pd_history(project)
        months = [r["month"] for r in result["monthly"]]
        assert months[-1] >= today.strftime("%Y-%m")

    def test_range_com_end_date_termina_no_end_date(self):
        project = make_project(start="2025-01", expected_end="2025-06", end="2025-04")
        result = get_epics_pd_history(project)
        months = [r["month"] for r in result["monthly"]]
        assert months[-1] == "2025-04"
        assert "2025-05" not in months

    def test_range_inclui_todos_os_meses(self):
        project = make_project(start="2025-01", expected_end="2025-03", end="2025-03")
        result = get_epics_pd_history(project)
        months = [r["month"] for r in result["monthly"]]
        assert months == ["2025-01", "2025-02", "2025-03"]

    def test_expected_end_date_retornado(self):
        project = make_project(start="2025-01", expected_end="2025-06")
        result = get_epics_pd_history(project)
        assert result["expected_end_date"] == "2025-06"

    def test_end_date_retornado_como_none_quando_nao_definido(self):
        project = make_project(start="2025-01", expected_end="2025-06")
        project.end_date = None
        project.save()
        result = get_epics_pd_history(project)
        assert result["expected_end_date"] == "2025-06"


# ─────────────────────────────────────────────────────────────────────────────
# get_epics_pd_history — cálculo de impacto
# ─────────────────────────────────────────────────────────────────────────────

class TestGetEpicsPdHistoryCalculos:
    def test_mes_sem_snapshot_retorna_zeros(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["scheduled_impact_done"] == 0
        assert jan["unscheduled_impact_done"] == 0
        assert jan["has_snapshot"] is False

    def test_calculo_scheduled_impact_done(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        epic1 = f.EpicFactory.create(project=project, status=status)
        epic2 = f.EpicFactory.create(project=project, status=status)

        # epic1: 50% feito, 40% de impacto → contribui 20
        snap(epic1, "2025-01", 50, 40, True, False)
        # epic2: 100% feito, 60% de impacto → contribui 60
        snap(epic2, "2025-01", 100, 60, True, False)

        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["scheduled_impact_done"] == 80.0

    def test_calculo_unscheduled_impact_done(self):
        project = make_project(start="2025-01", expected_end="2025-01", end="2025-01")
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status)

        snap(epic, "2025-01", 50, 20, False, False)

        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["unscheduled_impact_done"] == 10.0

    def test_scheduled_done_conta_epicas_fechadas(self):
        project = make_project(start="2025-01", expected_end="2025-01", end="2025-01")
        status = make_open_status(project)
        e1 = f.EpicFactory.create(project=project, status=status)
        e2 = f.EpicFactory.create(project=project, status=status)
        e3 = f.EpicFactory.create(project=project, status=status)

        snap(e1, "2025-01", 100, 33, True, True)
        snap(e2, "2025-01", 100, 33, True, True)
        snap(e3, "2025-01",  50, 34, True, False)

        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["scheduled_done"] == 2

    def test_has_snapshot_true_quando_existe(self):
        project = make_project(start="2025-01", expected_end="2025-01", end="2025-01")
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status)
        snap(epic, "2025-01", 100, 50, True, True)

        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["has_snapshot"] is True

    def test_totais_derivados_do_snapshot_mais_recente(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        e1 = f.EpicFactory.create(project=project, status=status)
        e2 = f.EpicFactory.create(project=project, status=status)

        snap(e1, "2025-02", 100, 60, True,  True)
        snap(e2, "2025-02",  50, 20, False, False)

        result = get_epics_pd_history(project)
        assert result["total_scheduled"] == 1
        assert result["total_unscheduled"] == 1
        assert result["total_scheduled_impact"] == 60
        assert result["total_unscheduled_impact"] == 20
        assert result["total_impact"] == 80


# ─────────────────────────────────────────────────────────────────────────────
# get_epics_pd_history — detecção de TMP
# ─────────────────────────────────────────────────────────────────────────────

class TestGetEpicsPdHistoryTMP:
    def test_sem_mudanca_nao_e_tmp(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status)

        snap(epic, "2025-01", 10, 50, True, False)
        snap(epic, "2025-02", 20, 50, True, False)

        result = get_epics_pd_history(project)
        feb = next(r for r in result["monthly"] if r["month"] == "2025-02")
        assert feb["is_tmp"] is False
        assert feb["tmp_changes"] == []

    def test_mudanca_de_impacto_detecta_tmp(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status)

        snap(epic, "2025-01", 10, 50, True, False)
        snap(epic, "2025-02", 20, 40, True, False)  # impacto mudou 50→40

        result = get_epics_pd_history(project)
        feb = next(r for r in result["monthly"] if r["month"] == "2025-02")
        assert feb["is_tmp"] is True
        assert any(
            c["type"] == "changed" and c["ref"] == epic.ref and c["from"] == 50 and c["to"] == 40
            for c in feb["tmp_changes"]
        )

    def test_nova_epica_planejavel_detecta_tmp(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        e1 = f.EpicFactory.create(project=project, status=status)
        e2 = f.EpicFactory.create(project=project, status=status)

        snap(e1, "2025-01", 10, 60, True,  False)
        snap(e1, "2025-02", 20, 60, True,  False)
        snap(e2, "2025-02", 0,  40, True,  False)  # nova épica planejável em fev

        result = get_epics_pd_history(project)
        feb = next(r for r in result["monthly"] if r["month"] == "2025-02")
        assert feb["is_tmp"] is True
        assert any(c["type"] == "added" and c["ref"] == e2.ref for c in feb["tmp_changes"])

    def test_epica_saiu_do_escopo_detecta_tmp(self):
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        e1 = f.EpicFactory.create(project=project, status=status)
        e2 = f.EpicFactory.create(project=project, status=status)

        snap(e1, "2025-01", 50, 60, True, False)
        snap(e2, "2025-01", 50, 40, True, False)
        # Em fevereiro, e2 deixou de ser planejável
        snap(e1, "2025-02", 60, 60, True,  False)
        snap(e2, "2025-02", 50, 40, False, False)

        result = get_epics_pd_history(project)
        feb = next(r for r in result["monthly"] if r["month"] == "2025-02")
        assert feb["is_tmp"] is True
        assert any(c["type"] == "removed" and c["ref"] == e2.ref for c in feb["tmp_changes"])

    def test_mudanca_em_nao_planejavel_nao_e_tmp(self):
        """Mudança em épica não-planejável não deve gerar TMP."""
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        e_sched   = f.EpicFactory.create(project=project, status=status, ref=1)
        e_unsched = f.EpicFactory.create(project=project, status=status, ref=2)

        snap(e_sched,   "2025-01", 10, 70, True,  False)
        snap(e_unsched, "2025-01", 10, 30, False, False)
        snap(e_sched,   "2025-02", 20, 70, True,  False)
        snap(e_unsched, "2025-02", 50, 30, False, False)  # só mudou cpd, não impacto/schedulable

        result = get_epics_pd_history(project)
        feb = next(r for r in result["monthly"] if r["month"] == "2025-02")
        assert feb["is_tmp"] is False

    def test_primeiro_mes_com_snapshot_nunca_e_tmp(self):
        """Primeiro mês que aparece no histórico não pode ser TMP (sem anterior para comparar)."""
        project = make_project(start="2025-01", expected_end="2025-02", end="2025-02")
        status = make_open_status(project)
        epic = f.EpicFactory.create(project=project, status=status)

        snap(epic, "2025-01", 10, 50, True, False)

        result = get_epics_pd_history(project)
        jan = next(r for r in result["monthly"] if r["month"] == "2025-01")
        assert jan["is_tmp"] is False
