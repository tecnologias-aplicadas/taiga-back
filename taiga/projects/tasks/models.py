# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from decimal import Decimal  # <-- novo
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from taiga.base.utils.time import timestamp_ms
from taiga.projects.due_dates.models import DueDateMixin
from taiga.projects.occ import OCCModelMixin
from taiga.projects.notifications.mixins import WatchedModelMixin
from taiga.projects.mixins.blocked import BlockedMixin
from taiga.projects.tagging.models import TaggedMixin


class Task(OCCModelMixin, WatchedModelMixin, BlockedMixin, TaggedMixin, DueDateMixin, models.Model):
    user_story = models.ForeignKey(
        "userstories.UserStory",
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name=_("user story"),
        on_delete=models.CASCADE,
    )
    ref = models.BigIntegerField(db_index=True, null=True, blank=True, default=None,
                                 verbose_name=_("ref"))
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        default=None,
        related_name="owned_tasks",
        verbose_name=_("owner"),
        on_delete=models.SET_NULL,
    )
    status = models.ForeignKey(
        "projects.TaskStatus",
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name=_("status"),
        on_delete=models.SET_NULL,
    )
    project = models.ForeignKey(
        "projects.Project",
        null=False,
        blank=False,
        related_name="tasks",
        verbose_name=_("project"),
        on_delete=models.CASCADE,
    )
    milestone = models.ForeignKey(
        "milestones.Milestone",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        default=None,
        related_name="tasks",
        verbose_name=_("milestone")
    )
    created_date = models.DateTimeField(null=False, blank=False,
                                        verbose_name=_("created date"),
                                        default=timezone.now)
    modified_date = models.DateTimeField(null=False, blank=False,
                                         verbose_name=_("modified date"))
    finished_date = models.DateTimeField(null=True, blank=True,
                                         verbose_name=_("finished date"))
    subject = models.TextField(null=False, blank=False,
                               verbose_name=_("subject"))

    us_order = models.BigIntegerField(null=False, blank=False, default=timestamp_ms,
                                      verbose_name=_("us order"))
    taskboard_order = models.BigIntegerField(null=False, blank=False, default=timestamp_ms,
                                             verbose_name=_("taskboard order"))

    description = models.TextField(null=False, blank=True, verbose_name=_("description"))
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        default=None,
        related_name="tasks_assigned_to_me",
        verbose_name=_("assigned to"),
        on_delete=models.SET_NULL,
    )
    attachments = GenericRelation("attachments.Attachment")
    is_iocaine = models.BooleanField(default=False, null=False, blank=True,
                                     verbose_name=_("is iocaine"))
    external_reference = ArrayField(models.TextField(null=False, blank=False),
                                    null=True, blank=True, default=None, verbose_name=_("external reference"))

    # ---- ALTERADOS: agora decimais com 2 casas (0.00 a 100.00)
    completion_percent_progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Completion percentage of the task (0.00 to 100.00)",
        verbose_name=_("completion percent progress"),
    )
    completion_percent_done = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Completion percentage marked as done (0.00 to 100.00)",
        verbose_name=_("completion percent done"),
    )
    # ----

    _importing = None

    class Meta:
        verbose_name = "task"
        verbose_name_plural = "tasks"
        ordering = ["project", "created_date", "ref"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(completion_percent_progress__gte=0) & models.Q(completion_percent_progress__lte=100),
                name="task_percent_progress_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(completion_percent_done__gte=0) & models.Q(completion_percent_done__lte=100),
                name="task_percent_done_0_100",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._importing or not self.modified_date:
            self.modified_date = timezone.now()

        # Garantir que a task tenha um status, pois os status contém o percentual de avanço que reflete na task.
        if not self.status:
            self.status = self.project.default_task_status

        # Se a tarefa está fechada, garantir que done seja 100% e progress seja 0%, e definir a data de conclusão se ainda não estiver definida.
        if self.status and self.status.is_closed:
            self.completion_percent_progress = Decimal("0.00")
            self.completion_percent_done = Decimal("100.00")
            self.finished_date = self.finished_date or timezone.now()
        else: # se a tarefa não está fechada
            # Se o status tem um percentual de progresso definido, usar esse valor para progresso e resetar done e data de conclusão.
            if self.status and self.status.completion_percent is not None:
                self.completion_percent_progress = Decimal(self.status.completion_percent).quantize(Decimal("0.01"))
                self.completion_percent_done = Decimal("0.00")
                self.finished_date = None
            else: # Se o status não tem um percentual de progresso definido
                # Tratar o caso em que a tarefa estava fechada (done 100%) e agora tem um status sem percentual definido: resetar done e data de conclusão, mantendo o progresso em 99%
                if self.completion_percent_done == Decimal("100.00"):
                    self.completion_percent_done = Decimal("0.00")
                    self.finished_date = None
                    self.completion_percent_progress = Decimal("99.00")
                elif self.completion_percent_progress > Decimal("0.00"):
                    # Se a tarefa tem progresso, mas não estava fechada, manter o progresso e resetar done e data de conclusão.
                    self.completion_percent_done = Decimal("0.00")
                    self.finished_date = None
                else: # Se a tarefa não estava fechada, manter os valores de progresso 
                    #mantém o valor que veio
                    pass
                    
        # Para as tasks, o done será 0 ou 100, o progress pode variar entre 0 e 100.
        # Quando progress possuir valor diferente de 0 o done deve ser 0
        # Já quando o done for 100, o progress deve ser 0, e a data de conclusão deve estar definida.
        # Uma tarefa que sai do concluído para um status sem precentual definido, terá o done resetado para 0, a data de conclusão resetada para None, e o progresso setado para 99% (para indicar que a tarefa está quase concluída, mas não totalmente).
        return super().save(*args, **kwargs)

    def __str__(self):
        return "({1}) {0}".format(self.ref, self.subject)

    @property
    def is_closed(self):
        return self.status is not None and self.status.is_closed
