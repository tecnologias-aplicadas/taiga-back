# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.utils.translation import gettext as _

from taiga.base.exceptions import ValidationError
from taiga.base.api import serializers
from taiga.base.api import validators
from taiga.projects.notifications.validators import WatchersValidator
from taiga.projects.userstories.models import UserStory
from taiga.projects.validators import DuplicatedNameInProjectValidator
from taiga.projects.validators import ProjectExistsValidator
from . import models


class MilestoneExistsValidator:
    def validate_milestone_id(self, attrs, source):
        value = attrs[source]
        if not models.Milestone.objects.filter(pk=value).exists():
            msg = _("There's no milestone with that id")
            raise ValidationError(msg)
        return attrs


class MilestoneValidator(WatchersValidator, DuplicatedNameInProjectValidator, validators.ModelValidator):
    class Meta:
        model = models.Milestone
        # Resultado da sprint só é gravado pela ação própria do servidor (RN06ADQ).
        read_only_fields = ("id", "created_date", "modified_date",
                            "goal_achievement", "result", "result_date", "result_by")

    def validate_goal(self, attrs, source):
        # Objetivo obrigatório na criação e imutável depois (RN02ADQ, RN03ADQ).
        goal = attrs.get(source)
        if goal is None or not goal.strip():
            raise ValidationError(_("The sprint goal is required"))

        if self.object is not None and goal != self.object.goal:
            raise ValidationError(_("The sprint goal cannot be changed after the sprint is created"))

        return attrs


class CloseWithResultValidator(validators.Validator):
    """
    Payload da ação que registra o resultado do objetivo e fecha a sprint
    (RN04ADQ, RN05ADQ). Recebe a sprint atual em `context["milestone"]`.
    """
    goal_achievement = serializers.ChoiceField(choices=models.GoalAchievement.choices)
    result = serializers.CharField()
    milestone_id = serializers.IntegerField(required=False)

    def validate_result(self, attrs, source):
        result = attrs.get(source)
        if result is None or not result.strip():
            raise ValidationError(_("The sprint result is required"))
        return attrs

    def validate_milestone_id(self, attrs, source):
        destination_id = attrs.get(source)
        if destination_id is None:
            return attrs

        milestone = self.context["milestone"]
        if destination_id == milestone.pk:
            raise ValidationError(_("The destination sprint must be different from the current one"))

        destination = models.Milestone.objects.filter(pk=destination_id,
                                                      project_id=milestone.project_id).first()
        if destination is None:
            raise ValidationError(_("The milestone isn't valid for the project"))
        if destination.closed:
            raise ValidationError(_("The destination sprint must be open"))

        return attrs


# bulk validators
class _UserStoryMilestoneBulkValidator(validators.Validator):
    us_id = serializers.IntegerField()
    order = serializers.IntegerField()


class UpdateMilestoneBulkValidator(MilestoneExistsValidator,
                                   ProjectExistsValidator,
                                   validators.Validator):
    project_id = serializers.IntegerField()
    milestone_id = serializers.IntegerField()
    bulk_stories = _UserStoryMilestoneBulkValidator(many=True)

    def validate_bulk_stories(self, attrs, source):
        filters = {
            "project__id": attrs["project_id"],
            "id__in": [us["us_id"] for us in attrs[source]]
        }

        if UserStory.objects.filter(**filters).count() != len(filters["id__in"]):
            raise ValidationError(_("All the user stories must be from the same project"))

        return attrs
