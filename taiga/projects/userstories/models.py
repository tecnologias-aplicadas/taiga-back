# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.core.validators import MinValueValidator, MaxValueValidator

from picklefield.fields import PickledObjectField

from taiga.base.utils.time import timestamp_mics
from taiga.projects.due_dates.models import DueDateMixin
from taiga.projects.tagging.models import TaggedMixin
from taiga.projects.occ import OCCModelMixin
from taiga.projects.notifications.mixins import WatchedModelMixin
from taiga.projects.mixins.blocked import BlockedMixin


class RolePoints(models.Model):
    user_story = models.ForeignKey(
        "UserStory",
        null=False,
        blank=False,
        related_name="role_points",
        verbose_name=_("user story"),
        on_delete=models.CASCADE,
    )
    role = models.ForeignKey(
        "users.Role",
        null=False,
        blank=False,
        related_name="role_points",
        verbose_name=_("role"),
        on_delete=models.CASCADE,
    )
    points = models.ForeignKey(
        "projects.Points",
        null=True,
        blank=False,
        related_name="role_points",
        verbose_name=_("points"),
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = "role points"
        verbose_name_plural = "role points"
        unique_together = ("user_story", "role")
        ordering = ["user_story", "role"]

    def __str__(self):
        return "{}: {}".format(self.role.name, self.points.name)

    @property
    def project(self):
        return self.user_story.project


class UserStory(OCCModelMixin, WatchedModelMixin, BlockedMixin, TaggedMixin, DueDateMixin, models.Model):
    NEW_BACKLOG_ORDER = timestamp_mics
    NEW_SPRINT_ORDER = timestamp_mics
    NEW_KANBAN_ORDER = timestamp_mics

    ref = models.BigIntegerField(db_index=True, null=True, blank=True, default=None,
                                 verbose_name=_("ref"))
    milestone = models.ForeignKey("milestones.Milestone", null=True, blank=True,
                                  default=None, related_name="user_stories",
                                  on_delete=models.SET_NULL, verbose_name=_("milestone"))
    project = models.ForeignKey(
        "projects.Project",
        null=False,
        blank=False,
        related_name="user_stories",
        verbose_name=_("project"),
        on_delete=models.CASCADE,
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              related_name="owned_user_stories", verbose_name=_("owner"),
                              on_delete=models.SET_NULL)
    status = models.ForeignKey("projects.UserStoryStatus", null=True, blank=True,
                               related_name="user_stories", verbose_name=_("status"),
                               on_delete=models.SET_NULL)
    is_closed = models.BooleanField(default=False)
    points = models.ManyToManyField("projects.Points", blank=False,
                                    related_name="userstories", through="RolePoints",
                                    verbose_name=_("points"))

    backlog_order = models.BigIntegerField(null=False, blank=False, default=NEW_BACKLOG_ORDER,
                                           verbose_name=_("backlog order"))
    sprint_order = models.BigIntegerField(null=False, blank=False, default=NEW_SPRINT_ORDER,
                                          verbose_name=_("sprint order"))
    kanban_order = models.BigIntegerField(null=False, blank=False, default=NEW_KANBAN_ORDER,
                                          verbose_name=_("kanban order"))

    created_date = models.DateTimeField(null=False, blank=False,
                                        verbose_name=_("created date"),
                                        default=timezone.now)
    modified_date = models.DateTimeField(null=False, blank=False,
                                         verbose_name=_("modified date"))
    finish_date = models.DateTimeField(null=True, blank=True,
                                       verbose_name=_("finish date"))
    subject = models.TextField(null=False, blank=False,
                               verbose_name=_("subject"))
    description = models.TextField(null=False, blank=True, verbose_name=_("description"))
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        default=None,
        related_name="userstories_assigned_to_me",
        verbose_name=_("assigned to"),
        on_delete=models.SET_NULL,
    )
    assigned_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True,
                                            default=None, related_name="assigned_userstories",
                                            verbose_name=_("assigned users"))
    client_requirement = models.BooleanField(default=False, null=False, blank=True,
                                             verbose_name=_("is client requirement"))
    team_requirement = models.BooleanField(default=False, null=False, blank=True,
                                           verbose_name=_("is team requirement"))
    attachments = GenericRelation("attachments.Attachment")
    generated_from_issue = models.ForeignKey("issues.Issue", null=True, blank=True,
                                             on_delete=models.SET_NULL,
                                             related_name="generated_user_stories",
                                             verbose_name=_("generated from issue"))
    generated_from_task = models.ForeignKey("tasks.Task", null=True, blank=True,
                                            on_delete=models.SET_NULL,
                                            related_name="generated_user_stories",
                                            verbose_name=_("generated from task"))
    from_task_ref = models.TextField(null=True, blank=True, verbose_name=_("reference from task"))
    external_reference = ArrayField(models.TextField(null=False, blank=False),
                                    null=True, blank=True, default=None, verbose_name=_("external reference"))

    tribe_gig = PickledObjectField(null=True, blank=True, default=None,
                                   verbose_name="taiga tribe gig")

    swimlane = models.ForeignKey("projects.Swimlane", null=True, blank=True,
                                 related_name="user_stories", verbose_name=_("swimlane"),
                                 on_delete=models.SET_NULL)
    
    completion_percent_progress = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Percentual de conclusão baseado nas tasks (0.00 a 100.00)",
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
        verbose_name = "user story"
        verbose_name_plural = "user stories"
        ordering = ["project", "backlog_order", "ref"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(completion_percent_progress__gte=0) & models.Q(completion_percent_progress__lte=100),
                name="us_percent_progress_0_100",
            ),
            models.CheckConstraint(
                check=models.Q(completion_percent_done__gte=0) & models.Q(completion_percent_done__lte=100),
                name="us_percent_done_0_100",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._importing or not self.modified_date:
            self.modified_date = timezone.now()

        if not self.status:
            self.status = self.project.default_us_status
        
        super().save(*args, **kwargs)

        if not self.role_points.all():
            for role in self.get_roles():
                RolePoints.objects.create(role=role,
                                          points=self.project.default_points,
                                          user_story=self)
        
        # A história não precisa da validação do self.pk igual ocorre na épica
        # self.update_completion_percent()



    def __str__(self):
        return "({1}) {0}".format(self.ref, self.subject)

    def __repr__(self):
        return "<UserStory %s>" % (self.id)

    def get_role_points(self):
        return self.role_points

    def get_total_points(self):
        not_null_role_points = [
            rp.points.value
            for rp in self.role_points.all()
            if rp.points.value is not None
        ]

        # If we only have None values the sum should be None
        if not not_null_role_points:
            return None

        return sum(not_null_role_points)

    def get_roles(self):
        return self.project.roles.filter(computable=True).all()
    
    def _q2(self, value) -> Decimal:
        """Quantiza para 2 casas, meio-para-cima."""
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_completion_percent_progress(self) -> Decimal:
        """
        Percentual de progresso = média do completion_percent_progress das tasks (0..100).
        Se não houver tasks, usa 100.00 se o US estiver fechado, senão 0.00.
        """
        # Se não houver tasks, o percentual é dado pelo status.is_closed do US
        qs = self.tasks.all()
        total_count = qs.count()
        if total_count == 0:
            return self._q2(Decimal("100.00") if (self.status and self.status.is_closed) else Decimal("0.00"))

        # Somatório dos percentuais (já são Decimal nas tasks)
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
        Percentual 'done' = soma dos percentuais das tasks FECHADAS dividido pelo total de tasks.
        (média ponderada das fechadas sobre o total)
        Se não houver tasks, usa 100.00 se o US estiver fechado, senão 0.00.
        """
        qs = self.tasks.all()
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
        """Atualiza ambos os percentuais e salva se houver mudança."""
        new_progress = self.calculate_completion_percent_progress()
        new_done = self.calculate_completion_percent_done()

        updated_fields = []

        if new_progress == 100 or new_done == 100:
            new_progress = Decimal("0.00")
            new_done = Decimal("100.00")
            
        
        if (new_progress != self.completion_percent_progress):
            self.completion_percent_progress = new_progress
            updated_fields.append("completion_percent_progress")
        if (new_done != self.completion_percent_done):
            self.completion_percent_done = new_done
            updated_fields.append("completion_percent_done")
        if len(updated_fields) > 0:
            super(UserStory, self).save(update_fields=updated_fields)
            return True
        return False
