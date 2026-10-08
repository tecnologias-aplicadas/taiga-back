# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.utils import timezone

from taiga.base import response
from taiga.base.decorators import detail_route
from taiga.base.api import ReadOnlyListViewSet
from taiga.mdrender.service import render as mdrender
from taiga.projects.notifications import services as notifications_services
from taiga.projects.notifications.apps import signal_mentions

from . import permissions
from . import serializers
from . import services


class HistoryViewSet(ReadOnlyListViewSet):
    serializer_class = serializers.HistoryEntrySerializer

    content_type = None

    def get_content_type(self):
        app_name, model = self.content_type.split(".", 1)
        return ContentType.objects.get_by_natural_key(app_name, model)

    def get_queryset(self):
        ct = self.get_content_type()
        model_cls = ct.model_class()

        qs = model_cls.objects.all()
        filtered_qs = self.filter_queryset(qs)
        return filtered_qs

    def response_for_queryset(self, queryset):
        # Switch between paginated or standard style responses
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(queryset, many=True)

        return response.Ok(serializer.data)

    def _get_new_mentions(self, obj: object, old_comment: str, new_comment: str):
        old_mentions = notifications_services.get_mentions(obj.project, old_comment)
        submitted_mentions = notifications_services.get_mentions(obj, new_comment)
        return list(set(submitted_mentions) - set(old_mentions))

    @detail_route(methods=['get'])
    def comment_versions(self, request, pk):
        obj = self.get_object()
        history_entry_id = request.QUERY_PARAMS.get('id', None)
        history_entry = services.get_history_queryset_by_model_instance(obj).filter(id=history_entry_id).first()
        if history_entry is None:
            return response.NotFound()

        self.check_permissions(request, 'comment_versions', history_entry)

        if history_entry is None:
            return response.NotFound()

        history_entry.attach_user_info_to_comment_versions()
        return response.Ok(history_entry.comment_versions)

    @detail_route(methods=['post'])
    def edit_comment(self, request, pk):
        obj = self.get_object()
        history_entry_id = request.QUERY_PARAMS.get('id', None)
        history_entry = services.get_history_queryset_by_model_instance(obj).filter(id=history_entry_id).first()
        if history_entry is None:
            return response.NotFound()

        obj = services.get_instance_from_key(history_entry.key)
        comment = request.DATA.get("comment", None)

        self.check_permissions(request, 'edit_comment', history_entry)

        if history_entry is None:
            return response.NotFound()

        if comment is None:
            return response.BadRequest({"error": _("comment is required")})

        if history_entry.delete_comment_date or history_entry.delete_comment_user:
            return response.BadRequest({"error": _("deleted comments can't be edited")})

        # comment_versions can be None if there are no historic versions of the comment
        comment_versions = history_entry.comment_versions or []
        comment_versions.append({
            "date": history_entry.created_at,
            "comment": history_entry.comment,
            "comment_html": history_entry.comment_html,
            "user": {
                "id": request.user.pk,
            }
        })

        new_mentions = self._get_new_mentions(obj, history_entry.comment, comment)

        history_entry.edit_comment_date = timezone.now()
        history_entry.comment = comment
        history_entry.comment_html = mdrender(obj.project, comment)
        history_entry.comment_versions = comment_versions
        history_entry.save()

        if new_mentions:
            signal_mentions.send(sender=self.__class__,
                                 user=self.request.user,
                                 obj=obj,
                                 mentions=new_mentions)

        return response.Ok()

    @detail_route(methods=['post'])
    def delete_comment(self, request, pk):
        obj = self.get_object()
        history_entry_id = request.QUERY_PARAMS.get('id', None)
        history_entry = services.get_history_queryset_by_model_instance(obj).filter(id=history_entry_id).first()
        if history_entry is None:
            return response.NotFound()

        self.check_permissions(request, 'delete_comment', history_entry)

        if history_entry is None:
            return response.NotFound()

        if history_entry.delete_comment_date or history_entry.delete_comment_user:
            return response.BadRequest({"error": _("Comment already deleted")})

        history_entry.delete_comment_date = timezone.now()
        history_entry.delete_comment_user = {"pk": request.user.pk, "name": request.user.get_full_name()}
        history_entry.save()
        return response.Ok()

    @detail_route(methods=['post'])
    def undelete_comment(self, request, pk):
        obj = self.get_object()
        history_entry_id = request.QUERY_PARAMS.get('id', None)
        history_entry = services.get_history_queryset_by_model_instance(obj).filter(id=history_entry_id).first()
        if history_entry is None:
            return response.NotFound()

        self.check_permissions(request, 'undelete_comment', history_entry)

        if history_entry is None:
            return response.NotFound()

        if not history_entry.delete_comment_date and not history_entry.delete_comment_user:
            return response.BadRequest({"error": _("Comment not deleted")})

        history_entry.delete_comment_date = None
        history_entry.delete_comment_user = None
        history_entry.save()
        return response.Ok()

    # Just for restframework! Because it raises
    # 404 on main api root if this method not exists.
    def list(self, request):
        return response.NotFound()

    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_permissions(request, "retrieve", obj)
        qs = services.get_history_queryset_by_model_instance(obj)

        history_type = self.request.GET.get('type')
        if history_type == 'activity':
            qs = qs.filter(diff__isnull=False, comment__exact='').exclude(diff__exact='')

        if history_type == 'comment':
            qs = qs.exclude(comment__exact='')

        qs = qs.order_by("-created_at")
        qs = services.prefetch_owners_in_history_queryset(qs)

        if self.request.GET.get(self.page_kwarg):
            page = self.paginate_queryset(qs)
            serializer = self.get_pagination_serializer(page)
            return response.Ok(serializer.data)

        return self.response_for_queryset(qs)


class EpicHistory(HistoryViewSet):
    content_type = "epics.epic"
    permission_classes = (permissions.EpicHistoryPermission,)


class UserStoryHistory(HistoryViewSet):
    content_type = "userstories.userstory"
    permission_classes = (permissions.UserStoryHistoryPermission,)


class TaskHistory(HistoryViewSet):
    content_type = "tasks.task"
    permission_classes = (permissions.TaskHistoryPermission,)


class IssueHistory(HistoryViewSet):
    content_type = "issues.issue"
    permission_classes = (permissions.IssueHistoryPermission,)


class WikiHistory(HistoryViewSet):
    content_type = "wiki.wikipage"
    permission_classes = (permissions.WikiHistoryPermission,)

from .models import CommentReaction
from collections import OrderedDict
import emoji

class CommentReactionViewSet(ReadOnlyListViewSet):
    serializer_class = serializers.CommentReactionSerializer

    def get_queryset(self):
        comment_id = self.kwargs.get("comment_pk")
        return CommentReaction.objects.filter(comment_id=comment_id)

    @detail_route(methods=["post"])
    def add_reaction(self, request, comment_pk):

        if not request.user or not request.user.is_authenticated:
            return response.Unauthorized({"error": _("Authentication required")})

        emoji_value = request.DATA.get("emoji")
        if not emoji_value:
            return response.BadRequest({"error": _("emoji is required")})

        if emoji_value not in emoji.EMOJI_DATA:
            return response.BadRequest({"error": _("invalid emoji")})

        reaction, created = CommentReaction.objects.get_or_create(
            comment_id=comment_pk,
            user=request.user,
            emoji=emoji_value,
        )
        serializer = self.serializer_class(reaction)
        return response.Ok(serializer.data)

    @detail_route(methods=["delete"])
    def remove_reaction(self, request, comment_pk):
        emoji_value = request.DATA.get("emoji")

        if not emoji:
            return response.BadRequest({"error": _("emoji is required")})

        if emoji_value not in emoji.EMOJI_DATA:
            return response.BadRequest({"error": _("invalid emoji")})

        CommentReaction.objects.filter(
            comment_id=comment_pk,
            user=request.user,
            emoji=emoji_value,
        ).delete()
        return response.Ok({"detail": _("Reaction removed successfully")})


    @detail_route(methods=["get"])
    def list_reactions(self, request, comment_pk):
        reactions = self.get_queryset().order_by("created_at")
        grouped = OrderedDict()

        for reaction in reactions:
            emoji = reaction.emoji
            if emoji not in grouped:
                grouped[emoji] = {"count": 0, "users": []}
            grouped[emoji]["count"] += 1
            grouped[emoji]["users"].append(reaction.user_id)
        return response.Ok(grouped)
