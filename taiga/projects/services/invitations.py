# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction as tx
from django.db import IntegrityError

from taiga.base import exceptions as exc

from taiga.base.mails import mail_builder


def send_invitation(invitation):
    """Send an invitation email"""
    if invitation.user:
        template = mail_builder.membership_notification
        email = template(invitation.user, {"membership": invitation})
    else:
        template = mail_builder.membership_invitation
        email = template(invitation.email, {"membership": invitation})

    email.send()


def find_invited_user(email, default=None):
    """Check if the invited user is already a registered.

    :param email: some user email
    :param default: Default object to return if user is not found.

    :return: The user if it's found, othwerwise return `default`.
    """

    User = apps.get_model(settings.AUTH_USER_MODEL)
    qs = User.objects.filter(email__iexact=email)

    if len(qs) > 1:
        qs = qs.filter(email=email)

    if len(qs) == 0:
        return default

    return qs[0]


def get_membership_by_token(token:str):
    """
    Given an invitation token, returns a membership instance
    that matches with specified token.

    If not matches with any membership NotFound exception
    is raised.

    The error carries a code, not a message: the text shown to the user is the
    front-end's job, as in the login errors.
    """
    membership_model = apps.get_model("projects", "Membership")
    qs = membership_model.objects.filter(token=token)
    if len(qs) == 0:
        raise exc.NotFound({"code": "invitation_not_valid"})
    return qs[0]


def get_unaccepted_membership_by_token(token:str):
    """
    Same as `get_membership_by_token`, but an invitation that has already been
    accepted is rejected with the very same error as an unknown token, so both
    cases are indistinguishable from the outside.
    """
    membership = get_membership_by_token(token)
    if membership.user is not None:
        raise exc.NotFound({"code": "invitation_not_valid"})
    return membership


def validate_invitation_email(membership, email:str):
    """
    An invitation is only valid for the email it was sent to, so a leaked token
    alone does not grant access to the project.

    The comparison ignores case and surrounding spaces. It fails closed: an
    invitation with no email stored is rejected with the very same error, so
    both cases are indistinguishable from the outside. The error carries a code
    and never tells which email was invited, so the token alone reveals nothing
    about its owner.
    """
    invited_email = (membership.email or "").strip().lower()
    given_email = (email or "").strip().lower()

    if not invited_email or invited_email != given_email:
        raise exc.WrongArguments({"code": "invitation_email_mismatch"})


@tx.atomic
def accept_invitation_by_existing_user(token:str, user_id:int):
    user_model = get_user_model()
    try:
        user = user_model.objects.get(id=user_id)
    except user_model.DoesNotExist:
        raise exc.NotFound({"code": "user_does_not_exist"})

    membership = get_unaccepted_membership_by_token(token)

    # --- begin: invitation email check for the login-with-token path ---
    # Kept apart on purpose: if this rule is ever relaxed for existing users
    # entering with a token, this is the only block to touch.
    validate_invitation_email(membership, user.email)
    # --- end: invitation email check for the login-with-token path ---

    try:
        membership.user = user
        membership.save(update_fields=["user"])
    except IntegrityError:
        raise exc.IntegrityError({"code": "already_project_member"})
    return user
