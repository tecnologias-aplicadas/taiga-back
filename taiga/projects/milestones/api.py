# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.apps import apps
from django.db import transaction
from django.utils.translation import gettext as _

from taiga.base import exceptions as exc
from taiga.base import filters
from taiga.base import response
from taiga.base.decorators import detail_route
from taiga.base.api import ModelCrudViewSet
from taiga.base.api import ModelListViewSet
from taiga.base.api.mixins import BlockedByProjectMixin
from taiga.base.api.utils import get_object_or_error
from taiga.base.utils.db import get_object_or_none

from taiga.projects.models import Project
from taiga.projects.notifications.mixins import WatchedResourceMixin
from taiga.projects.notifications.mixins import WatchersViewSetMixin
from taiga.projects.history.mixins import HistoryResourceMixin
from taiga.projects.tasks.validators import UpdateMilestoneBulkValidator as \
    TasksUpdateMilestoneValidator
from taiga.projects.issues.validators import UpdateMilestoneBulkValidator as \
    IssuesUpdateMilestoneValidator

from . import serializers
from . import services
from . import validators
from . import models
from . import permissions
from . import utils as milestones_utils

from django_pglocks import advisory_lock
import datetime


class MilestoneViewSet(HistoryResourceMixin, WatchedResourceMixin,
                       BlockedByProjectMixin, ModelCrudViewSet):
    serializer_class = serializers.MilestoneSerializer
    validator_class = validators.MilestoneValidator
    permission_classes = (permissions.MilestonePermission,)
    filter_backends = (
        filters.CanViewMilestonesFilterBackend,
        filters.CreatedDateFilter,
        filters.ModifiedDateFilter,
        filters.EstimatedStartFilter,
        filters.EstimatedFinishFilter,
    )
    filter_fields = (
        "project",
        "project__slug",
        "closed"
    )
    order_by_fields = ("project",
                       "name",
                       "estimated_start",
                       "estimated_finish",
                       "closed",
                       "created_date")
    queryset = models.Milestone.objects.all()

    def create(self, request, *args, **kwargs):
        project_id = request.DATA.get("project", 0)
        with advisory_lock("milestone-creation-{}".format(project_id)):
            return super().create(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        res = super().list(request, *args, **kwargs)
        self._add_taiga_info_headers()
        return res

    def _add_taiga_info_headers(self):
        try:
            project_id = int(self.request.QUERY_PARAMS.get("project", None))
            project_model = apps.get_model("projects", "Project")
            project = get_object_or_none(project_model, id=project_id)
        except TypeError:
            project = None

        if project:
            opened_milestones = project.milestones.filter(closed=False).count()
            closed_milestones = project.milestones.filter(closed=True).count()
            closed_milestones_without_result = project.milestones.filter(
                closed=True, result__isnull=True).count()

            self.headers["Taiga-Info-Total-Opened-Milestones"] = opened_milestones
            self.headers["Taiga-Info-Total-Closed-Milestones"] = closed_milestones
            self.headers["Taiga-Info-Total-Closed-Milestones-Without-Result"] = \
                closed_milestones_without_result

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("project", "owner")
        qs = milestones_utils.attach_extra_info(qs, user=self.request.user)
        qs = qs.order_by("-estimated_start")
        return qs

    def pre_save(self, obj):
        if not obj.id:
            obj.owner = self.request.user

        super().pre_save(obj)

    @detail_route(methods=['get'])
    def stats(self, request, pk=None):
        milestone = get_object_or_error(models.Milestone, request.user, pk=pk)

        self.check_permissions(request, "stats", milestone)

        total_points = milestone.total_points
        milestone_stats = {
            'name': milestone.name,
            'estimated_start': milestone.estimated_start,
            'estimated_finish': milestone.estimated_finish,
            'total_points': total_points,
            'completed_points': milestone.closed_points.values(),
            'total_userstories': milestone.cached_user_stories.count(),
            'completed_userstories': milestone.cached_user_stories.filter(is_closed=True).count(),
            'total_tasks': milestone.tasks.count(),
            'completed_tasks': milestone.tasks.filter(status__is_closed=True).count(),
            'iocaine_doses': milestone.tasks.filter(is_iocaine=True).count(),
            'days': []
        }
        current_date = milestone.estimated_start
        sumTotalPoints = sum(total_points.values())
        optimal_points = sumTotalPoints
        milestone_days = (milestone.estimated_finish - milestone.estimated_start).days
        optimal_points_per_day = sumTotalPoints / milestone_days if milestone_days else 0

        while current_date <= milestone.estimated_finish:
            milestone_stats['days'].append({
                'day': current_date,
                'name': current_date.day,
                'open_points':  sumTotalPoints - milestone.total_closed_points_by_date(current_date),
                'optimal_points': optimal_points,
            })
            current_date = current_date + datetime.timedelta(days=1)
            optimal_points -= optimal_points_per_day

        return response.Ok(milestone_stats)

    @detail_route(methods=["POST"])
    def move_userstories_to_sprint(self, request, pk=None, **kwargs):
        milestone = get_object_or_error(models.Milestone, request.user, pk=pk)

        self.check_permissions(request, "move_related_items", milestone)

        validator = validators.UpdateMilestoneBulkValidator(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data
        project = get_object_or_error(Project, request.user, pk=data["project_id"])
        milestone_result = get_object_or_error(models.Milestone, request.user, pk=data["milestone_id"])

        if data["bulk_stories"]:
            self.check_permissions(request, "move_uss_to_sprint", project)
            services.update_userstories_milestone_in_bulk(data["bulk_stories"], milestone_result)
            services.snapshot_userstories_in_bulk(data["bulk_stories"], request.user)

        return response.NoContent()

    @detail_route(methods=["POST"])
    def move_tasks_to_sprint(self, request, pk=None, **kwargs):
        milestone = get_object_or_error(models.Milestone, request.user, pk=pk)

        self.check_permissions(request, "move_related_items", milestone)

        validator = TasksUpdateMilestoneValidator(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data
        project = get_object_or_error(Project, request.user, pk=data["project_id"])
        milestone_result = get_object_or_error(models.Milestone, request.user, pk=data["milestone_id"])

        if data["bulk_tasks"]:
            self.check_permissions(request, "move_tasks_to_sprint", project)
            services.update_tasks_milestone_in_bulk(data["bulk_tasks"], milestone_result)
            services.snapshot_tasks_in_bulk(data["bulk_tasks"], request.user)

        return response.NoContent()

    @detail_route(methods=["POST"])
    def move_issues_to_sprint(self, request, pk=None, **kwargs):
        milestone = get_object_or_error(models.Milestone, request.user, pk=pk)

        self.check_permissions(request, "move_related_items", milestone)

        validator = IssuesUpdateMilestoneValidator(data=request.DATA)
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data
        project = get_object_or_error(Project, request.user, pk=data["project_id"])
        milestone_result = get_object_or_error(models.Milestone, request.user, pk=data["milestone_id"])

        if data["bulk_issues"]:
            self.check_permissions(request, "move_issues_to_sprint", project)
            services.update_issues_milestone_in_bulk(data["bulk_issues"], milestone_result)
            services.snapshot_issues_in_bulk(data["bulk_issues"], request.user)

        return response.NoContent()

    @detail_route(methods=["POST"])
    def close_with_result(self, request, pk=None, **kwargs):
        """
        Registra o resultado do objetivo da sprint, move os itens não finalizados
        para outra sprint aberta e fecha a sprint pela regra atual, tudo ou nada
        (RN04ADQ, RN05ADQ, RN06ADQ, RN08ADQ).
        """
        milestone = get_object_or_error(models.Milestone, request.user, pk=pk)

        self.check_permissions(request, "close_with_result", milestone)

        validator = validators.CloseWithResultValidator(data=request.DATA,
                                                        context={"milestone": milestone})
        if not validator.is_valid():
            return response.BadRequest(validator.errors)

        data = validator.data

        with transaction.atomic():
            if milestone.result is not None:
                raise exc.BadRequest(_("The sprint result has already been registered"))

            if not services.milestone_has_closed_items(milestone):
                raise exc.BadRequest(_("The sprint has no finished activity, so it cannot be closed"))

            bulk_stories, bulk_tasks, bulk_issues = services.get_unfinished_milestone_items(milestone)
            if bulk_stories or bulk_tasks or bulk_issues:
                if data.get("milestone_id") is None:
                    raise exc.BadRequest({
                        "milestone_id": [_("A destination sprint is required for the unfinished items")]
                    })

                destination = get_object_or_error(models.Milestone, request.user,
                                                  pk=data["milestone_id"])

                if bulk_stories:
                    self.check_permissions(request, "move_uss_to_sprint", milestone.project)
                    services.update_userstories_milestone_in_bulk(bulk_stories, destination)
                    services.snapshot_userstories_in_bulk(bulk_stories, request.user)

                if bulk_tasks:
                    self.check_permissions(request, "move_tasks_to_sprint", milestone.project)
                    services.update_tasks_milestone_in_bulk(bulk_tasks, destination)
                    services.snapshot_tasks_in_bulk(bulk_tasks, request.user)

                if bulk_issues:
                    self.check_permissions(request, "move_issues_to_sprint", milestone.project)
                    services.update_issues_milestone_in_bulk(bulk_issues, destination)
                    services.snapshot_issues_in_bulk(bulk_issues, request.user)

            milestone = models.Milestone.objects.get(pk=milestone.pk)
            if not services.calculate_milestone_is_closed(milestone):
                raise exc.BadRequest(_("The sprint could not be closed, so the result was not registered"))
            services.close_milestone(milestone)

            if not services.register_milestone_result(milestone, data["goal_achievement"],
                                                      data["result"].strip(), request.user):
                raise exc.BadRequest(_("The sprint result has already been registered"))

        milestone = self.get_queryset().get(pk=milestone.pk)
        serializer = self.get_serializer(milestone)
        return response.Ok(serializer.data)


class MilestoneWatchersViewSet(WatchersViewSetMixin, ModelListViewSet):
    permission_classes = (permissions.MilestoneWatchersPermission,)
    resource_model = models.Milestone
