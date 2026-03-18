"""
Notification utilities for the Beacon platform.

Provides functions that both create in-app Notification records AND send
HTML email notifications.  All email sending is wrapped in try/except so
failures are logged but never break the caller's workflow.
"""

import logging
import os

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext as _

from core.models import Notification, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_absolute_url(path):
    """Build a fully-qualified URL from a path.

    Uses RAILWAY_PUBLIC_DOMAIN in production, falls back to localhost.
    """
    domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8000')
    scheme = 'https' if 'localhost' not in domain else 'http'
    return f'{scheme}://{domain}{path}'


def _send_notification_email(recipient_email, subject, template_name, context):
    """Render an HTML email template and send it.  Fails silently with logging.

    Automatically looks for a matching .txt template (same base name) to use as
    the plain-text body.  This multipart approach (text + HTML) improves
    deliverability and prevents emails from being flagged as spam.
    """
    try:
        html_body = render_to_string(template_name, context)
        # Derive the plain-text template path from the HTML template name
        txt_template = template_name.rsplit('.', 1)[0] + '.txt'
        try:
            text_body = render_to_string(txt_template, context)
        except Exception:
            text_body = ''  # Graceful fallback if .txt template is missing
        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            'Failed to send notification email to %s (subject: %s)',
            recipient_email,
            subject,
        )


def _create_notification(recipient, title, message, link='', priority='medium'):
    """Create an in-app Notification record."""
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        message=message,
        link=link,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Public notification functions (called from views)
# ---------------------------------------------------------------------------

def notify_application_submitted(application):
    """Notify agency staff that a new application was submitted."""
    program = application.grant_program
    applicant = application.applicant
    org_name = (
        application.organization.name if application.organization else 'Unknown'
    )
    detail_path = reverse('applications:detail', kwargs={'pk': application.pk})
    detail_url = _build_absolute_url(detail_path)

    # Find staff to notify: users linked to this program's agency
    staff_qs = User.objects.filter(
        role__in=[
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.SYSTEM_ADMIN,
        ],
        is_active=True,
    )
    if program.agency_id:
        # Include agency-specific staff + system admins (who may not have an agency)
        staff_qs = staff_qs.filter(
            agency=program.agency,
        ) | User.objects.filter(
            role=User.Role.SYSTEM_ADMIN,
            is_active=True,
        )

    subject = _('New Application Submitted: %(title)s') % {'title': application.project_title}
    message = _(
        '%(name)s from %(org)s submitted an application '
        'for "%(program)s".'
    ) % {'name': applicant.get_full_name(), 'org': org_name, 'program': program.title}

    for staff_user in staff_qs.distinct():
        _create_notification(
            recipient=staff_user,
            title=_('New Application Submitted'),
            message=message,
            link=detail_path,
            priority='medium',
        )
        if staff_user.email:
            _send_notification_email(
                recipient_email=staff_user.email,
                subject=subject,
                template_name='emails/application_submitted.html',
                context={
                    'staff_user': staff_user,
                    'application': application,
                    'applicant': applicant,
                    'program': program,
                    'org_name': org_name,
                    'detail_url': detail_url,
                },
            )


def notify_application_status_changed(application, old_status, new_status, comment=''):
    """Notify the applicant that their application status changed."""
    applicant = application.applicant
    status_display = dict(application.Status.choices).get(new_status, new_status)
    old_status_display = dict(application.Status.choices).get(old_status, old_status)
    detail_path = reverse('applications:detail', kwargs={'pk': application.pk})
    detail_url = _build_absolute_url(detail_path)

    priority_map = {
        'approved': 'high',
        'denied': 'high',
        'revision_requested': 'high',
        'under_review': 'medium',
    }
    priority = priority_map.get(new_status, 'medium')

    subject = _('Application Update: %(title)s — %(status)s') % {'title': application.project_title, 'status': status_display}
    message = _(
        'Your application "%(title)s" has been updated '
        'to "%(status)s".'
    ) % {'title': application.project_title, 'status': status_display}
    if comment:
        message += _(' Comment: %(comment)s') % {'comment': comment}

    _create_notification(
        recipient=applicant,
        title=_('Application %(status)s') % {'status': status_display},
        message=message,
        link=detail_path,
        priority=priority,
    )

    if applicant.email:
        _send_notification_email(
            recipient_email=applicant.email,
            subject=subject,
            template_name='emails/application_status_changed.html',
            context={
                'applicant': applicant,
                'application': application,
                'old_status': old_status_display,
                'new_status': status_display,
                'comment': comment,
                'detail_url': detail_url,
            },
        )


def notify_award_created(award):
    """Notify the recipient that an award has been created."""
    recipient = award.recipient
    detail_path = reverse('awards:detail', kwargs={'pk': award.pk})
    detail_url = _build_absolute_url(detail_path)

    subject = _('Award Created: %(title)s (%(number)s)') % {'title': award.title, 'number': award.award_number}
    message = _(
        'An award has been created for your application. '
        'Award number: %(number)s, '
        'Amount: $%(amount)s.'
    ) % {'number': award.award_number, 'amount': f'{award.award_amount:,.2f}'}

    _create_notification(
        recipient=recipient,
        title=_('Award Created'),
        message=message,
        link=detail_path,
        priority='high',
    )

    if recipient.email:
        _send_notification_email(
            recipient_email=recipient.email,
            subject=subject,
            template_name='emails/award_created.html',
            context={
                'recipient': recipient,
                'award': award,
                'detail_url': detail_url,
            },
        )


def notify_drawdown_status_changed(drawdown, new_status):
    """Notify the submitter that their drawdown request status changed."""
    recipient = drawdown.submitted_by
    award = drawdown.award
    status_display = drawdown.get_status_display()
    detail_path = reverse(
        'financial:drawdown-detail', kwargs={'pk': drawdown.pk}
    )
    detail_url = _build_absolute_url(detail_path)

    subject = _('Drawdown Request Update: %(award)s - %(status)s') % {'award': award.award_number, 'status': status_display}
    message = _(
        'Your drawdown request %(request)s for award '
        '%(award)s has been updated to "%(status)s".'
    ) % {'request': drawdown.request_number, 'award': award.award_number, 'status': status_display}

    try:
        _create_notification(
            recipient=recipient,
            title=_('Drawdown %(status)s') % {'status': status_display},
            message=message,
            link=detail_path,
            priority='high',
        )
        if recipient.email:
            send_mail(
                subject=subject,
                message=message + f'\n\nView details: {detail_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
    except Exception:
        logger.exception(
            'Failed to send drawdown status notification for %s',
            drawdown.pk,
        )


def notify_report_review_complete(report, action):
    """Notify the report submitter that their report was reviewed.

    ``action`` is 'approve', 'revision', or 'reject'.
    """
    award = report.award
    recipient = award.recipient
    action_labels = {
        'approve': _('Approved'),
        'revision': _('Revision Requested'),
        'reject': _('Rejected'),
    }
    action_display = action_labels.get(action, action)
    detail_path = reverse('reporting:detail', kwargs={'pk': report.pk})
    detail_url = _build_absolute_url(detail_path)

    subject = _('Report Review: %(award)s - %(action)s') % {'award': award.award_number, 'action': action_display}
    message = _(
        'Your %(type)s report for award '
        '%(award)s has been %(action)s.'
    ) % {'type': report.get_report_type_display(), 'award': award.award_number, 'action': action_display.lower()}

    try:
        _create_notification(
            recipient=recipient,
            title=_('Report %(action)s') % {'action': action_display},
            message=message,
            link=detail_path,
            priority='high',
        )
        if recipient.email:
            send_mail(
                subject=subject,
                message=message + f'\n\nView details: {detail_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
    except Exception:
        logger.exception(
            'Failed to send report review notification for %s',
            report.pk,
        )


def notify_amendment_created(amendment):
    """Notify agency staff that an amendment was requested."""
    award = amendment.award
    requester = amendment.requested_by
    detail_path = reverse(
        'awards:amendment-detail', kwargs={'pk': amendment.pk}
    )
    detail_url = _build_absolute_url(detail_path)

    subject = _('New Amendment Request: %(award)s - Amendment #%(number)s') % {
        'award': award.award_number, 'number': amendment.amendment_number,
    }
    message = _(
        '%(name)s requested an amendment '
        '(%(type)s) for award '
        '%(award)s.'
    ) % {'name': requester.get_full_name(), 'type': amendment.get_amendment_type_display(), 'award': award.award_number}

    # Notify staff in the award's agency
    staff_qs = User.objects.filter(
        role__in=[
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.SYSTEM_ADMIN,
        ],
        is_active=True,
    )
    if award.agency_id:
        staff_qs = staff_qs.filter(
            agency=award.agency,
        ) | User.objects.filter(
            role=User.Role.SYSTEM_ADMIN,
            is_active=True,
        )

    try:
        for staff_user in staff_qs.distinct():
            _create_notification(
                recipient=staff_user,
                title=_('New Amendment Request'),
                message=message,
                link=detail_path,
                priority='medium',
            )
            if staff_user.email:
                send_mail(
                    subject=subject,
                    message=message + f'\n\nView details: {detail_url}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[staff_user.email],
                    fail_silently=True,
                )
    except Exception:
        logger.exception(
            'Failed to send amendment notification for %s',
            amendment.pk,
        )


def notify_signature_requested(award, signature_request):
    """Notify the signer that an award agreement is ready for signature."""
    detail_path = reverse('awards:detail', kwargs={'pk': award.pk})
    detail_url = _build_absolute_url(detail_path)

    subject = _('Signature Requested: %(title)s (%(number)s)') % {
        'title': award.title,
        'number': award.award_number,
    }
    message = _(
        'An award agreement for "%(title)s" (%(number)s) has been sent '
        'to %(name)s for electronic signature via DocuSign.'
    ) % {
        'title': award.title,
        'number': award.award_number,
        'name': signature_request.signer_name,
    }

    # Notify the award recipient (in-app)
    recipient = award.recipient
    _create_notification(
        recipient=recipient,
        title=_('Signature Requested'),
        message=message,
        link=detail_path,
        priority='high',
    )

    # Send email notification to the signer
    if signature_request.signer_email:
        _send_notification_email(
            recipient_email=signature_request.signer_email,
            subject=subject,
            template_name='emails/signature_requested.html',
            context={
                'award': award,
                'signature_request': signature_request,
                'detail_url': detail_url,
                'signer_name': signature_request.signer_name,
            },
        )


def notify_signature_completed(award, signature_request):
    """Notify the award sender that the agreement has been signed."""
    detail_path = reverse('awards:detail', kwargs={'pk': award.pk})
    detail_url = _build_absolute_url(detail_path)

    subject = _('Agreement Signed: %(title)s (%(number)s)') % {
        'title': award.title,
        'number': award.award_number,
    }
    message = _(
        '%(name)s has signed the award agreement for '
        '"%(title)s" (%(number)s). The award is now executed.'
    ) % {
        'name': signature_request.signer_name,
        'title': award.title,
        'number': award.award_number,
    }

    # Notify the person who sent the signature request
    if signature_request.sent_by:
        _create_notification(
            recipient=signature_request.sent_by,
            title=_('Agreement Signed'),
            message=message,
            link=detail_path,
            priority='high',
        )
        if signature_request.sent_by.email:
            _send_notification_email(
                recipient_email=signature_request.sent_by.email,
                subject=subject,
                template_name='emails/signature_requested.html',
                context={
                    'award': award,
                    'signature_request': signature_request,
                    'detail_url': detail_url,
                    'signer_name': signature_request.signer_name,
                    'is_completion_notice': True,
                },
            )

    # Also notify agency staff
    staff_qs = User.objects.filter(
        role__in=[
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.SYSTEM_ADMIN,
        ],
        is_active=True,
    )
    if award.agency_id:
        staff_qs = staff_qs.filter(
            agency=award.agency,
        ) | User.objects.filter(
            role=User.Role.SYSTEM_ADMIN,
            is_active=True,
        )

    try:
        for staff_user in staff_qs.distinct():
            if signature_request.sent_by and staff_user.pk == signature_request.sent_by.pk:
                continue  # Already notified above
            _create_notification(
                recipient=staff_user,
                title=_('Agreement Signed'),
                message=message,
                link=detail_path,
                priority='medium',
            )
    except Exception:
        logger.exception(
            'Failed to send signature completion notifications for award %s',
            award.pk,
        )


def notify_closeout_initiated(closeout):
    """Notify the award recipient that closeout has been initiated."""
    award = closeout.award
    recipient = award.recipient
    detail_path = reverse('closeout:detail', kwargs={'pk': closeout.pk})
    detail_url = _build_absolute_url(detail_path)

    subject = _('Closeout Initiated: %(award)s') % {'award': award.award_number}
    message = _(
        'The closeout process has been initiated for your award '
        '%(award)s (%(title)s). Please review the '
        'closeout checklist and submit required documents.'
    ) % {'award': award.award_number, 'title': award.title}

    try:
        _create_notification(
            recipient=recipient,
            title=_('Closeout Initiated'),
            message=message,
            link=detail_path,
            priority='high',
        )
        if recipient.email:
            send_mail(
                subject=subject,
                message=message + f'\n\nView details: {detail_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
    except Exception:
        logger.exception(
            'Failed to send closeout notification for %s',
            closeout.pk,
        )


def notify_new_user_registered(user):
    """Notify system admins that a new user has registered."""
    full_name = user.get_full_name() or user.username
    role_label = user.get_role_display() if user.role else 'applicant'
    role_path = reverse('core:user-role-edit', kwargs={'pk': user.pk})

    admins = User.objects.filter(
        role=User.Role.SYSTEM_ADMIN,
        is_active=True,
    )

    message = _(
        '%(name)s (%(email)s) has registered as %(role)s. '
        'Review their account and assign a role if needed.'
    ) % {'name': full_name, 'email': user.email or 'no email', 'role': role_label}

    for admin in admins:
        _create_notification(
            recipient=admin,
            title=_('New User Registration'),
            message=message,
            link=role_path,
            priority='medium',
        )
