# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from datetime import timedelta
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

from taiga.base.utils.colors import generate_random_predefined_hex_color
from taiga.base import exceptions as exc
from taiga.base.utils.time import timestamp_ms
from taiga.projects.tagging.models import TaggedMixin
from taiga.projects.occ import OCCModelMixin
from taiga.projects.notifications.mixins import WatchedModelMixin
from taiga.projects.mixins.blocked import BlockedMixin
from datetime import date


class Epic(OCCModelMixin, WatchedModelMixin, BlockedMixin, TaggedMixin, models.Model):
    ref = models.BigIntegerField(db_index=True, null=True, blank=True, default=None,
                                 verbose_name=_("ref"))
    project = models.ForeignKey(
        "projects.Project",
        null=False,
        blank=False,
        related_name="epics",
        verbose_name=_("project"),
        on_delete=models.CASCADE,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="owned_epics",
        verbose_name=_("owner"),
        on_delete=models.SET_NULL
    )
    status = models.ForeignKey("projects.EpicStatus", null=True, blank=True, related_name="epics", verbose_name=_("status"), on_delete=models.SET_NULL)
    
    epics_order = models.BigIntegerField(null=False, blank=False, default=timestamp_ms, verbose_name=_("epics order"))

    created_date = models.DateTimeField(null=False, blank=False, verbose_name=_("created date"), default=timezone.now)
    
    start_date = models.DateField(null=False, blank=False, default=date(2020, 1, 1), verbose_name=_("start date"))

    expected_completion_date = models.DateField(null=False, blank=False, default=date(2020, 1, 2), verbose_name=_("expected completion date"))

    completion_date = models.DateField(null=True, blank=True, verbose_name=_("completion date"))

    modified_date = models.DateTimeField(null=False, blank=False, verbose_name=_("modified date"))

    subject = models.TextField(null=False, blank=False, verbose_name=_("subject"))
    
    description = models.TextField(null=False, blank=True, verbose_name=_("description"))
    
    color = models.CharField(max_length=32, null=False, blank=True, default=generate_random_predefined_hex_color, verbose_name=_("color"))
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        default=None,
        related_name="epics_assigned_to_me",
        verbose_name=_("assigned to"),
        on_delete=models.SET_NULL,
    )
    client_requirement = models.BooleanField(default=False, null=False, blank=True,
                                             verbose_name=_("is client requirement"))
    team_requirement = models.BooleanField(default=False, null=False, blank=True,
                                           verbose_name=_("is team requirement"))
    schedulable = models.BooleanField(null=True, blank=True, default=None,
                                      verbose_name=_("is schedulable"))
    percentage_impact = models.IntegerField(
        null=False, blank=False, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("percentage impact"),
    )

    user_stories = models.ManyToManyField("userstories.UserStory", related_name="epics",
                                          through='RelatedUserStory',
                                          verbose_name=_("user stories"))
    external_reference = ArrayField(models.TextField(null=False, blank=False),
                                    null=True, blank=True, default=None, verbose_name=_("external reference"))

    attachments = GenericRelation("attachments.Attachment")
    
    completion_percent_progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Percentual de conclusão baseado nas user stories (0.00 a 100.00)",
        verbose_name=_("completion percent progress"),
    )
    completion_percent_done = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Percentual concluído (0.00 a 100.00)",
        verbose_name=_("completion percent done"),
    )

    _importing = None

    class Meta:
        verbose_name = "epic"
        verbose_name_plural = "epics"
        ordering = ["project", "epics_order", "ref"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(completion_percent_progress__gte=0) & models.Q(completion_percent_progress__lte=100),
                name="epic_percent_progress_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(completion_percent_done__gte=0) & models.Q(completion_percent_done__lte=100),
                name="epic_percent_done_0_100",
            ),
        ]

    def __str__(self):
        return "#{0} {1}".format(self.ref, self.subject)

    def __repr__(self):
        return "<Epic %s>" % (self.id)

    def clean(self):
        if self.expected_completion_date < self.start_date:
            raise ValidationError({"code": "completion_date_before_start_date"})
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status_id = self.status_id

    def save(self, *args, **kwargs):
        if not self._importing or not self.modified_date:
            self.modified_date = timezone.now()

        if not self.status:
            self.status = self.project.default_epic_status

        self.epic_is_closed()

        super().save(*args, **kwargs)

        # Executar após o save pois o update_completion_percent já tem save, evitar duplo save
        # Por enquanto é necessário pois ele atualiza o quadro das épicas qnd o status da épica é fechado/aberto, para epicas q n tem histórias
        if self.pk is not None:
            self.update_completion_percent()


    # -------- Helpers para percentuais (2 casas, meio-para-cima)
    def _q2(self, value) -> Decimal:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    #O backend que controla o completion_date baseado no status da épica, por não receber do front, precisa dessa validação
    def epic_is_closed(self) -> bool:
        if not self.status:
            return False
                
        if self.pk and hasattr(self, "_original_status_id") and self._original_status_id != self.status_id:
            if self.status.is_closed:
                self.completion_date = date.today()
            else:
                self.completion_date = None
            return True
        
        return False

    def calculate_completion_percent_progress(self) -> Decimal:
        """
        Percentual de progresso do épico:
        média de (US.progress - US.done) em todas as user stories.
        Se não houver US, retorna 100.00 se o épico estiver fechado, senão 0.00.
        """
        # Se não houver US, o percentual é dado pelo status.is_closed do épico
        qs = self.user_stories.all()
        total_count = qs.count()
        if total_count == 0:
            return self._q2(Decimal("100.00") if (self.status and self.status.is_closed) else Decimal("0.00"))

        # Realizar o somatório das US em progresso
        total = Decimal("0.00")
        for v in qs.values_list("completion_percent_progress", flat=True):
            total += (v if isinstance(v, Decimal) else Decimal(str(v)))

        avg = total / Decimal(total_count)
        if avg < 0:
            avg = Decimal("0.00")
        elif avg > 100:
            avg = Decimal("100.00")
        return self._q2(avg)

    def calculate_completion_percent_done(self) -> Decimal:
        """
        Percentual 'done' do épico:
        média simples do completion_percent_done das US.
        Se não houver US, retorna 100.00 se o épico estiver fechado, senão 0.00.
        """
        # Se não houver US, o percentual é dado pelo status.is_closed do épico
        qs = self.user_stories.all()
        total_count = qs.count()
        if total_count == 0:
            return self._q2(Decimal("100.00") if (self.status and self.status.is_closed) else Decimal("0.00"))

        total = Decimal("0.00")
        for v in qs.values_list("completion_percent_done", flat=True):
            total += (v if isinstance(v, Decimal) else Decimal(str(v)))

        avg = total / Decimal(total_count)
        if avg < 0:
            avg = Decimal("0.00")
        elif avg > 100:
            avg = Decimal("100.00")
        return self._q2(avg)

    def update_completion_percent(self) -> bool:
        """Atualiza ambos os percentuais e salva se houver alteração."""
        new_progress = self.calculate_completion_percent_progress()
        new_done = self.calculate_completion_percent_done()

        fields = []
        if new_progress == 100 or new_done == 100:
            new_progress = Decimal("0.00")
            new_done = Decimal("100.00")
        elif new_progress == 0 and new_done == 0:
            new_progress = Decimal("0.00")
            new_done = Decimal("0.00")
        
        if self.completion_percent_progress != new_progress:
            self.completion_percent_progress = new_progress
            fields.append("completion_percent_progress")
        if self.completion_percent_done != new_done:
            self.completion_percent_done = new_done
            fields.append("completion_percent_done")
        if len(fields) > 0:
            super(Epic, self).save(update_fields=fields)
            return True
        return False
    
    


class EpicMonthlySnapshot(models.Model):
    """
    Fotografia mensal do completion_percent_done de cada épica.
    Uma vez criado o registro de um mês passado, ele não deve ser alterado.
    O mês atual pode ser atualizado pelo management command até o final do mês.
    """
    epic = models.ForeignKey(
        "epics.Epic",
        on_delete=models.CASCADE,
        related_name="monthly_snapshots",
        verbose_name=_("epic"),
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="epic_monthly_snapshots",
        verbose_name=_("project"),
    )
    year_month = models.CharField(max_length=7, verbose_name=_("year month"))  # "YYYY-MM"
    completion_percent_done = models.IntegerField(
        default=0,
        verbose_name=_("completion percent done"),
    )
    percentage_impact = models.IntegerField(
        default=0,
        verbose_name=_("percentage impact"),
    )
    schedulable = models.BooleanField(null=True, blank=True, verbose_name=_("schedulable"))
    is_closed = models.BooleanField(default=False, verbose_name=_("is closed"))
    snapshot_date = models.DateTimeField(auto_now_add=True, verbose_name=_("snapshot date"))

    class Meta:
        verbose_name = "epic monthly snapshot"
        verbose_name_plural = "epic monthly snapshots"
        unique_together = (("epic", "year_month"),)
        ordering = ["year_month"]
        indexes = [
            models.Index(fields=["project", "year_month"]),
        ]

    def __str__(self):
        return f"{self.epic_id} @ {self.year_month}"


class RelatedUserStory(WatchedModelMixin, models.Model):
    user_story = models.ForeignKey("userstories.UserStory", on_delete=models.CASCADE)
    epic = models.ForeignKey("epics.Epic", on_delete=models.CASCADE)

    order = models.BigIntegerField(null=False, blank=False, default=timestamp_ms,
                                verbose_name=_("order"))

    class Meta:
        verbose_name = "related user story"
        verbose_name_plural = "related user stories"
        ordering = ["user_story", "order", "id"]
        unique_together = (("user_story", "epic"), )

    def __str__(self):
        return "{0} - {1}".format(self.epic_id, self.user_story_id)

    @property
    def project(self):
        return self.epic.project

    @property
    def project_id(self):
        return self.epic.project_id

    @property
    def owner(self):
        return self.epic.owner

    @property
    def owner_id(self):
        return self.epic.owner_id

    @property
    def assigned_to_id(self):
        return self.epic.assigned_to_id
    

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.epic:
            self.epic.update_completion_percent()


    def delete(self, *args, **kwargs):
        epic = self.epic
        super().delete(*args, **kwargs)

        if epic:
            epic.update_completion_percent()
