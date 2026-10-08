# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import csv
import io
from collections import OrderedDict
from datetime import date
from operator import itemgetter
from contextlib import closing

from dateutil.relativedelta import relativedelta

from django.db import connection
from django.utils.translation import gettext as _

from taiga.base.utils import db, text
from taiga.projects.epics.apps import connect_epics_signals
from taiga.projects.epics.apps import disconnect_epics_signals
from taiga.projects.epics.apps import connect_related_userstories_signals
from taiga.projects.epics.apps import disconnect_related_userstories_signals
from taiga.projects.services import apply_order_updates
from taiga.projects.userstories.apps import connect_userstories_signals
from taiga.projects.userstories.apps import disconnect_userstories_signals
from taiga.projects.userstories.services import get_userstories_from_bulk
from taiga.events import events
from taiga.projects.votes.utils import attach_total_voters_to_queryset
from taiga.projects.notifications.utils import attach_watchers_to_queryset

from . import models


#####################################################
# Bulk actions
#####################################################

def get_epics_from_bulk(bulk_data, **additional_fields):
    """Convert `bulk_data` into a list of epics.

    :param bulk_data: List of epics in bulk format.
    :param additional_fields: Additional fields when instantiating each epic.

    :return: List of `Epic` instances.
    """
    return [models.Epic(subject=line, **additional_fields)
            for line in text.split_in_lines(bulk_data)]


def create_epics_in_bulk(bulk_data, callback=None, precall=None, **additional_fields):
    """Create epics from `bulk_data`.

    :param bulk_data: List of epics in bulk format.
    :param callback: Callback to execute after each epic save.
    :param additional_fields: Additional fields when instantiating each epic.

    :return: List of created `Epic` instances.
    """
    epics = get_epics_from_bulk(bulk_data, **additional_fields)

    disconnect_epics_signals()

    try:
        db.save_in_bulk(epics, callback, precall)
    finally:
        connect_epics_signals()

    return epics


def update_epics_order_in_bulk(bulk_data: list, field: str, project: object):
    """
    Update the order of some epics.
    `bulk_data` should be a list of tuples with the following format:

    [{'epic_id': <value>, 'order': <value>}, ...]
    """
    epics = project.epics.all()

    epic_orders = {e.id: getattr(e, field) for e in epics}
    new_epic_orders = {d["epic_id"]: d["order"] for d in bulk_data}
    apply_order_updates(epic_orders, new_epic_orders)

    epic_ids = epic_orders.keys()
    events.emit_event_for_ids(ids=epic_ids,
                              content_type="epics.epic",
                              projectid=project.pk)

    db.update_attr_in_bulk_for_ids(epic_orders, field, models.Epic)
    return epic_orders


def create_related_userstories_in_bulk(bulk_data, epic, **additional_fields):
    """Create user stories from `bulk_data`.

    :param epic: Element where all the user stories will be contained
    :param bulk_data: List of user stories in bulk format.
    :param additional_fields: Additional fields when instantiating each user story.

    :return: List of created `Task` instances.
    """
    userstories = get_userstories_from_bulk(bulk_data, **additional_fields)
    project = additional_fields.get("project")

    # Set default swimlane if kanban module is enabled
    if project.is_kanban_activated:
        for user_story in userstories:
            user_story.swimlane = project.default_swimlane

    disconnect_userstories_signals()
    # Em lote, um só evento da épica no fim, em vez de um por ligação
    disconnect_related_userstories_signals()

    try:
        db.save_in_bulk(userstories)
        related_userstories = []
        for userstory in userstories:
            related_userstories.append(
                models.RelatedUserStory(
                    user_story=userstory,
                    epic=epic
                )
            )
        db.save_in_bulk(related_userstories)
        project.update_role_points(user_stories=userstories)
    finally:
        connect_userstories_signals()
        connect_related_userstories_signals()

    if related_userstories:
        events.emit_event_for_model(epic, type="change")

    return related_userstories


def update_epic_related_userstories_order_in_bulk(bulk_data: list, epic: object):
    """
    Updates the order of the related userstories of an specific epic.
    `bulk_data` should be a list of dicts with the following format:
    `epic` is the epic with related stories.

    [{'us_id': <value>, 'order': <value>}, ...]
    """
    related_user_stories = epic.relateduserstory_set.all()
    # select_related
    rus_orders = {rus.id: rus.order for rus in related_user_stories}

    rus_conversion = {rus.user_story_id: rus.id for rus in related_user_stories}
    new_rus_orders = {rus_conversion[e["us_id"]]: e["order"] for e in bulk_data
                      if e["us_id"] in rus_conversion}

    apply_order_updates(rus_orders, new_rus_orders)

    if rus_orders:
        related_user_story_ids = rus_orders.keys()
        events.emit_event_for_ids(ids=related_user_story_ids,
                                  content_type="epics.relateduserstory",
                                  projectid=epic.project_id)

        db.update_attr_in_bulk_for_ids(rus_orders, "order", models.RelatedUserStory)

    return rus_orders


#####################################################
# CSV
#####################################################

def epics_to_csv(project, queryset):
    csv_data = io.StringIO()
    fieldnames = ["id", "ref", "subject", "description", "owner", "owner_full_name",
                  "assigned_to", "assigned_to_full_name", "status", "epics_order",
                  "client_requirement", "team_requirement", "attachments", "tags",
                  "watchers", "voters", "created_date", "modified_date",
                  "related_user_stories"]

    custom_attrs = project.epiccustomattributes.all()
    for custom_attr in custom_attrs:
        fieldnames.append(custom_attr.name)

    queryset = queryset.prefetch_related("attachments",
                                         "custom_attributes_values",
                                         "user_stories__project")
    queryset = queryset.select_related("owner",
                                       "assigned_to",
                                       "status",
                                       "project")

    queryset = attach_total_voters_to_queryset(queryset)
    queryset = attach_watchers_to_queryset(queryset)

    writer = csv.DictWriter(csv_data, fieldnames=fieldnames)
    writer.writeheader()
    for epic in queryset:
        epic_data = {
            "id": epic.id,
            "ref": epic.ref,
            "subject": epic.subject,
            "description": epic.description,
            "owner": epic.owner.username if epic.owner else None,
            "owner_full_name": epic.owner.get_full_name() if epic.owner else None,
            "assigned_to": epic.assigned_to.username if epic.assigned_to else None,
            "assigned_to_full_name": epic.assigned_to.get_full_name() if epic.assigned_to else None,
            "status": epic.status.name if epic.status else None,
            "epics_order": epic.epics_order,
            "client_requirement": epic.client_requirement,
            "team_requirement": epic.team_requirement,
            "attachments": epic.attachments.count(),
            "tags": ",".join(epic.tags or []),
            "watchers": epic.watchers,
            "voters": epic.total_voters,
            "created_date": epic.created_date,
            "modified_date": epic.modified_date,
            "related_user_stories": ",".join([
                "{}#{}".format(us.project.slug, us.ref) for us in epic.user_stories.all()
            ]),
        }

        for custom_attr in custom_attrs:
            if not hasattr(epic, "custom_attributes_values"):
                continue
            value = epic.custom_attributes_values.attributes_values.get(str(custom_attr.id), None)
            epic_data[custom_attr.name] = value

        writer.writerow(epic_data)

    return csv_data


#####################################################
# Api filter data
#####################################################

def _get_epics_statuses(project, queryset):
    compiler = connection.ops.compiler(queryset.query.compiler)(queryset.query, connection, None)
    queryset_where_tuple = queryset.query.where.as_sql(compiler, connection)
    where = queryset_where_tuple[0]
    where_params = queryset_where_tuple[1]

    extra_sql = """
      SELECT "projects_epicstatus"."id",
             "projects_epicstatus"."name",
             "projects_epicstatus"."color",
             "projects_epicstatus"."order",
             (SELECT count(*)
                FROM "epics_epic"
                     INNER JOIN "projects_project" ON
                                ("epics_epic"."project_id" = "projects_project"."id")
               WHERE {where} AND "epics_epic"."status_id" = "projects_epicstatus"."id")
        FROM "projects_epicstatus"
       WHERE "projects_epicstatus"."project_id" = %s
    ORDER BY "projects_epicstatus"."order";
    """.format(where=where)

    with closing(connection.cursor()) as cursor:
        cursor.execute(extra_sql, where_params + [project.id])
        rows = cursor.fetchall()

    result = []
    for id, name, color, order, count in rows:
        result.append({
            "id": id,
            "name": _(name),
            "color": color,
            "order": order,
            "count": count,
        })
    return sorted(result, key=itemgetter("order"))


def _get_epics_assigned_to(project, queryset):
    compiler = connection.ops.compiler(queryset.query.compiler)(queryset.query, connection, None)
    queryset_where_tuple = queryset.query.where.as_sql(compiler, connection)
    where = queryset_where_tuple[0]
    where_params = queryset_where_tuple[1]

    extra_sql = """
        WITH counters AS (
                SELECT assigned_to_id,  count(assigned_to_id) count
                  FROM "epics_epic"
            INNER JOIN "projects_project" ON ("epics_epic"."project_id" = "projects_project"."id")
                 WHERE {where} AND "epics_epic"."assigned_to_id" IS NOT NULL
              GROUP BY assigned_to_id
        )

                 SELECT "projects_membership"."user_id" user_id,
                        "users_user"."full_name",
                        "users_user"."username",
                        COALESCE("counters".count, 0) count
                   FROM projects_membership
        LEFT OUTER JOIN counters ON ("projects_membership"."user_id" = "counters"."assigned_to_id")
             INNER JOIN "users_user" ON ("projects_membership"."user_id" = "users_user"."id")
                  WHERE "projects_membership"."project_id" = %s
                    AND "projects_membership"."user_id" IS NOT NULL

        -- unassigned epics
        UNION

                 SELECT NULL user_id, NULL, NULL, count(coalesce(assigned_to_id, -1)) count
                   FROM "epics_epic"
             INNER JOIN "projects_project" ON ("epics_epic"."project_id" = "projects_project"."id")
                  WHERE {where} AND "epics_epic"."assigned_to_id" IS NULL
               GROUP BY assigned_to_id
    """.format(where=where)

    with closing(connection.cursor()) as cursor:
        cursor.execute(extra_sql, where_params + [project.id] + where_params)
        rows = cursor.fetchall()

    result = []
    none_valued_added = False
    for id, full_name, username, count in rows:
        result.append({
            "id": id,
            "full_name": full_name or username or "",
            "count": count,
        })

        if id is None:
            none_valued_added = True

    # If there was no epic with null assigned_to we manually add it
    if not none_valued_added:
        result.append({
            "id": None,
            "full_name": "",
            "count": 0,
        })

    return sorted(result, key=itemgetter("full_name"))


def _get_epics_owners(project, queryset):
    compiler = connection.ops.compiler(queryset.query.compiler)(queryset.query, connection, None)
    queryset_where_tuple = queryset.query.where.as_sql(compiler, connection)
    where = queryset_where_tuple[0]
    where_params = queryset_where_tuple[1]

    extra_sql = """
        WITH counters AS (
                SELECT "epics_epic"."owner_id" owner_id,
                       count(coalesce("epics_epic"."owner_id", -1)) count
                  FROM "epics_epic"
            INNER JOIN "projects_project" ON ("epics_epic"."project_id" = "projects_project"."id")
                 WHERE {where}
              GROUP BY "epics_epic"."owner_id"
        )

                 SELECT "projects_membership"."user_id" id,
                        "users_user"."full_name",
                        "users_user"."username",
                        COALESCE("counters".count, 0) count
                   FROM projects_membership
        LEFT OUTER JOIN counters ON ("projects_membership"."user_id" = "counters"."owner_id")
             INNER JOIN "users_user" ON ("projects_membership"."user_id" = "users_user"."id")
                  WHERE "projects_membership"."project_id" = %s
                    AND "projects_membership"."user_id" IS NOT NULL

        -- System users
        UNION

                 SELECT "users_user"."id" user_id,
                        "users_user"."full_name" full_name,
                        "users_user"."username" username,
                        COALESCE("counters".count, 0) count
                   FROM users_user
        LEFT OUTER JOIN counters ON ("users_user"."id" = "counters"."owner_id")
                  WHERE ("users_user"."is_system" IS TRUE)
    """.format(where=where)

    with closing(connection.cursor()) as cursor:
        cursor.execute(extra_sql, where_params + [project.id])
        rows = cursor.fetchall()

    result = []
    for id, full_name, username, count in rows:
        if count > 0:
            result.append({
                "id": id,
                "full_name": full_name or username or "",
                "count": count,
            })
    return sorted(result, key=itemgetter("full_name"))


def _get_epics_tags(project, queryset):
    compiler = connection.ops.compiler(queryset.query.compiler)(queryset.query, connection, None)
    queryset_where_tuple = queryset.query.where.as_sql(compiler, connection)
    where = queryset_where_tuple[0]
    where_params = queryset_where_tuple[1]

    extra_sql = """
        WITH epics_tags AS (
                    SELECT tag,
                           COUNT(tag) counter FROM (
                                SELECT UNNEST(epics_epic.tags) tag
                                  FROM epics_epic
                            INNER JOIN projects_project
                                        ON (epics_epic.project_id = projects_project.id)
                                 WHERE {where}) tags
                  GROUP BY tag),
             project_tags AS (
                    SELECT reduce_dim(tags_colors) tag_color
                      FROM projects_project
                     WHERE id=%s)

      SELECT tag_color[1] tag,
             tag_color[2] color,
             COALESCE(epics_tags.counter, 0) counter
        FROM project_tags
   LEFT JOIN epics_tags ON project_tags.tag_color[1] = epics_tags.tag
    ORDER BY tag
    """.format(where=where)

    with closing(connection.cursor()) as cursor:
        cursor.execute(extra_sql, where_params + [project.id])
        rows = cursor.fetchall()

    result = []
    for name, color, count in rows:
        result.append({
            "name": name,
            "color": color,
            "count": count,
        })
    return sorted(result, key=itemgetter("name"))


def get_epics_pd_history(project):
    """
    Returns weighted monthly progress of epics for a project.

    For each month:
    - If a snapshot exists (EpicMonthlySnapshot), use its frozen values.
    - Otherwise (current/future months or before snapshots were set up), use live values.

    Scheduled epics (schedulable=True) are weighted by percentage_impact.
    Unscheduled epics use a simple average.

    Response structure:
      - total_scheduled_impact: sum of percentage_impact for schedulable=True epics
      - total_unscheduled: count of schedulable=False epics
      - monthly: list of {month, scheduled_weighted_pct, unscheduled_avg_pct}
    """
    from taiga.projects.epics.models import EpicMonthlySnapshot
    from collections import defaultdict

    scheduled_epics = list(
        project.epics.filter(schedulable=True).select_related("status")
        .values("id", "completion_percent_done", "percentage_impact", "status__is_closed")
    )
    unscheduled_epics = list(
        project.epics.filter(schedulable=False).select_related("status")
        .values("id", "completion_percent_done", "percentage_impact", "status__is_closed")
    )

    total_scheduled_impact = sum(e["percentage_impact"] for e in scheduled_epics)
    total_unscheduled_impact = sum(e["percentage_impact"] for e in unscheduled_epics)
    total_impact = total_scheduled_impact + total_unscheduled_impact
    total_scheduled = len(scheduled_epics)
    total_unscheduled = len(unscheduled_epics)


    # Load all existing snapshots for this project
    snapshots = EpicMonthlySnapshot.objects.filter(
        epic__project=project
    ).values("epic_id", "year_month", "completion_percent_done", "percentage_impact", "schedulable", "is_closed")

    snap_by_month = defaultdict(list)
    for s in snapshots:
        snap_by_month[s["year_month"]].append(s)

    # If live epics have no schedulable set, fall back to the most recent snapshot
    if snap_by_month and (total_scheduled == 0 and total_unscheduled == 0):
        latest_snaps = snap_by_month[max(snap_by_month.keys())]
        total_scheduled = len([s for s in latest_snaps if s["schedulable"] is True])
        total_unscheduled = len([s for s in latest_snaps if s["schedulable"] is False])
        total_scheduled_impact = sum(s["percentage_impact"] for s in latest_snaps if s["schedulable"] is True)
        total_unscheduled_impact = sum(s["percentage_impact"] for s in latest_snaps if s["schedulable"] is False)
        total_impact = total_scheduled_impact + total_unscheduled_impact

    # Epic ref lookup for human-readable TMP descriptions
    epic_refs = {e["id"]: e["ref"] for e in project.epics.values("id", "ref")}

    # Build month range
    start = project.start_date
    today = date.today()
    # When project is finished, chart ends at end_date; otherwise extends to today if past expected end
    if project.end_date:
        end = project.end_date
    else:
        end = max(project.expected_end_date, today)

    months = []
    current = date(start.year, start.month, 1)
    end_month = date(end.year, end.month, 1)
    while current <= end_month:
        months.append(current)
        current += relativedelta(months=1)

    monthly = []
    # TMP detection: compare scope signature (who is schedulable and at what impact)
    # A TMP occurs when the composition changes, even if the total stays the same
    prev_scope_sig = None

    for month in months:
        ym = month.strftime("%Y-%m")

        if ym in snap_by_month:
            snaps = snap_by_month[ym]
            sched_snaps   = [s for s in snaps if s["schedulable"] is True]
            unsched_snaps = [s for s in snaps if s["schedulable"] is False]

            sched_impact_done = round(
                sum(s["completion_percent_done"] * s["percentage_impact"] / 100 for s in sched_snaps), 2
            )
            unsched_impact_done = round(
                sum(s["completion_percent_done"] * s["percentage_impact"] / 100 for s in unsched_snaps), 2
            )
            sched_done   = sum(1 for s in sched_snaps if s["is_closed"])
            unsched_done = sum(1 for s in unsched_snaps if s["is_closed"])

            # TMP detection: scope signature = only schedulable=True epics and their impacts.
            # Changes in non-schedulable epics do NOT trigger TMP.
            cur_scope_sig = frozenset(
                (s["epic_id"], s["percentage_impact"])
                for s in snaps
                if s["schedulable"] is True
            )

            if prev_scope_sig is not None and cur_scope_sig != prev_scope_sig:
                is_tmp = True

                # Build dicts {epic_id: impact} — scope_sig already contains only schedulable=True
                prev_sched_map = {s[0]: s[1] for s in prev_scope_sig}
                cur_sched_map  = {s[0]: s[1] for s in cur_scope_sig}

                tmp_changes = []
                # Epics that changed impact (stayed schedulable but impact changed)
                for epic_id, cur_impact in cur_sched_map.items():
                    if epic_id in prev_sched_map and prev_sched_map[epic_id] != cur_impact:
                        ref = epic_refs.get(epic_id, epic_id)
                        tmp_changes.append({"type": "changed", "ref": ref, "from": prev_sched_map[epic_id], "to": cur_impact})
                # New schedulable epics
                for epic_id in cur_sched_map:
                    if epic_id not in prev_sched_map:
                        ref = epic_refs.get(epic_id, epic_id)
                        tmp_changes.append({"type": "added", "ref": ref})
                # Epics that left schedulable scope
                for epic_id in prev_sched_map:
                    if epic_id not in cur_sched_map:
                        ref = epic_refs.get(epic_id, epic_id)
                        tmp_changes.append({"type": "removed", "ref": ref})
            else:
                is_tmp      = False
                tmp_changes = []
            prev_scope_sig = cur_scope_sig
        else:
            sched_impact_done   = 0
            unsched_impact_done = 0
            sched_done          = 0
            unsched_done        = 0
            is_tmp      = False
            tmp_changes = []

        monthly.append({
            "month":        ym,
            "has_snapshot": ym in snap_by_month,
            "scheduled_impact_done":   sched_impact_done,
            "unscheduled_impact_done": unsched_impact_done,
            "scheduled_done":   sched_done,
            "unscheduled_done": unsched_done,
            "is_tmp":       is_tmp,
            "tmp_changes":  tmp_changes,
        })

    return {
        "total_impact": total_impact,
        "total_scheduled_impact": total_scheduled_impact,
        "total_unscheduled_impact": total_unscheduled_impact,
        "total_scheduled": total_scheduled,
        "total_unscheduled": total_unscheduled,
        "expected_end_date": project.expected_end_date.strftime("%Y-%m") if project.expected_end_date else None,
        "monthly": monthly,
    }


def get_epics_filters_data(project, querysets):
    """
    Given a project and an epics queryset, return a simple data structure
    of all possible filters for the epics in the queryset.
    """
    data = OrderedDict([
        ("statuses", _get_epics_statuses(project, querysets["statuses"])),
        ("assigned_to", _get_epics_assigned_to(project, querysets["assigned_to"])),
        ("owners", _get_epics_owners(project, querysets["owners"])),
        ("tags", _get_epics_tags(project, querysets["tags"])),
    ])

    return data
