"""
Compatibility layer for running the signatures app standalone (Manifest)
or within the full Harbor project.

Detection is based on ``django.apps.apps.is_installed('core')``.
When the ``core`` app is present we re-export its permission mixins, audit
logging and notification helpers.  Otherwise lightweight fallbacks are used
so that the signatures app works as an independent Django package.
"""

import logging
import os

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models.expressions import BaseExpression

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------

def is_harbor():
    """Return ``True`` when running inside the full Harbor project."""
    return apps.is_installed('core')


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

class _StandaloneAuditAction:
    """Stub matching the ``core.models.AuditLog.Action`` constants."""
    CREATE = 'create'
    UPDATE = 'update'
    DELETE = 'delete'
    STATUS_CHANGE = 'status_change'
    SUBMIT = 'submit'
    APPROVE = 'approve'
    REJECT = 'reject'


def get_audit_action():
    """Return the audit-action enum (Harbor) or the standalone stub."""
    if is_harbor():
        from core.models import AuditLog
        return AuditLog.Action
    return _StandaloneAuditAction


def log_audit(user, action, entity_type, entity_id,
              description='', changes=None, ip_address=None):
    """Create an audit record — delegates to ``core.audit`` or logs."""
    if is_harbor():
        from core.audit import log_audit as _core_log
        return _core_log(user, action, entity_type, entity_id,
                         description, changes, ip_address)
    from .models import AuditLog
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            description=description,
            changes=changes or {},
            ip_address=ip_address,
        )
    except Exception:
        logger.exception('Failed to create audit log entry')


def get_audit_log_model():
    """Return the AuditLog model for the current deployment mode."""
    if is_harbor():
        from core.models import AuditLog
        return AuditLog
    from .models import AuditLog
    return AuditLog


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def build_absolute_url(path):
    """Return a fully-qualified URL for *path*."""
    if is_harbor():
        from keel.core.notifications import build_absolute_url as _build_url
        return _build_url(path)
    domain = getattr(settings, 'MANIFEST_SITE_URL', None)
    if not domain:
        domain = os.environ.get('SITE_URL', 'http://localhost:8000')
    return f'{domain.rstrip("/")}{path}'


def create_notification(recipient, title, message, link='', priority='medium'):
    """Create an in-app notification (Harbor) or standalone Notification record."""
    if is_harbor():
        from keel.core.notifications import create_notification as _create_notif
        return _create_notif(recipient, title, message, link, priority)
    # Standalone mode: create a Notification record in the signatures app
    try:
        from .models import Notification
        Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            link=link,
            priority=priority,
        )
    except Exception:
        logger.exception('Failed to create notification for %s', recipient)


def send_notification_email(recipient_email, subject, template_name, context):
    """Send an HTML email notification."""
    if is_harbor():
        from keel.core.notifications import send_notification_email as _send_email
        return _send_email(
            recipient_email, subject, template_name, context,
        )
    # Standalone: use Django's send_mail directly
    from django.core.mail import send_mail
    from django.template.loader import render_to_string

    try:
        html_body = render_to_string(template_name, context)
        txt_template = template_name.rsplit('.', 1)[0] + '.txt'
        try:
            text_body = render_to_string(txt_template, context)
        except Exception:
            text_body = ''
        send_mail(
            subject=subject,
            message=text_body,
            from_email=getattr(
                settings, 'DEFAULT_FROM_EMAIL', 'noreply@manifest.docklabs.ai',
            ),
            recipient_list=[recipient_email],
            html_message=html_body,
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send email to %s', recipient_email)


# ---------------------------------------------------------------------------
# Permission mixins
# ---------------------------------------------------------------------------

class _StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Standalone fallback: require superuser OR a privileged ProductAccess role.

    CSO 2026-06-03 Week 3 audit: was previously ``return user.is_staff``,
    which leaks suite-wide on demo (``seed_keel_users`` force-sets
    ``is_staff=True`` on every demo user). The proper harbor mixin
    ``AgencyStaffRequiredMixin`` from ``core.mixins`` is the canonical
    gate for harbor's signature management views; this fallback only
    fires when harbor's ``core`` package is unavailable (e.g. a future
    standalone signatures-only deployment). Tighten the fallback to
    role-based — superuser or system_admin / admin / agency_admin /
    grant_manager — instead of the leaky is_staff path.
    """

    _STAFF_ROLES = frozenset({
        'system_admin', 'admin', 'agency_admin', 'grant_manager',
    })

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        role = getattr(user, 'role', '') or ''
        return role in self._STAFF_ROLES


# Import mixins at module level.  We cannot rely on try/except ImportError
# because the core/ package exists on disk even in standalone (Manifest)
# deployments — the import succeeds but the mixin expects the custom User
# model.  Instead, check settings.INSTALLED_APPS directly (available before
# the app registry is fully populated).
_core_in_apps = any(
    app == 'core' or app.startswith('core.')
    for app in settings.INSTALLED_APPS
)

if _core_in_apps:
    from core.mixins import (  # noqa: F401
        AgencyStaffRequiredMixin,
        GrantManagerRequiredMixin,
    )
else:
    AgencyStaffRequiredMixin = _StaffRequiredMixin
    GrantManagerRequiredMixin = _StaffRequiredMixin


class SortableListMixin:
    """Server-side column sorting for any ListView.

    Self-contained copy of ``core.mixins.SortableListMixin`` so the
    signatures app works without the ``core`` app installed.
    """

    sortable_fields = {}
    default_sort = ''
    default_dir = 'asc'

    def get_sort_params(self):
        sort = self.request.GET.get('sort', self.default_sort)
        direction = self.request.GET.get('dir', self.default_dir)
        if sort not in self.sortable_fields:
            sort = self.default_sort
        if direction not in ('asc', 'desc'):
            direction = self.default_dir
        return sort, direction

    def apply_sorting(self, qs):
        sort, direction = self.get_sort_params()
        if not sort:
            return qs
        field = self.sortable_fields[sort]
        if isinstance(field, BaseExpression):
            alias = f'_sort_{sort}'
            qs = qs.annotate(**{alias: field})
            order_field = alias
        else:
            order_field = field
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.order_by(order_field)

    def get_queryset(self):
        return self.apply_sorting(super().get_queryset())

    def _build_params(self, exclude):
        parts = []
        for key in self.request.GET:
            if key not in exclude:
                for val in self.request.GET.getlist(key):
                    parts.append(f'{key}={val}')
        return '&'.join(parts)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sort, direction = self.get_sort_params()
        ctx['current_sort'] = sort
        ctx['current_dir'] = direction
        ctx['filter_params'] = self._build_params({'sort', 'dir', 'page'})
        ctx['pagination_params'] = self._build_params({'page'})
        return ctx


# ---------------------------------------------------------------------------
# User queryset helpers
# ---------------------------------------------------------------------------

def get_assignable_users():
    """Return a queryset of users who can be assigned as signers."""
    User = get_user_model()
    if is_harbor():
        from keel.accounts.models import ProductAccess
        staff_roles = [
            'system_admin', 'agency_admin', 'program_officer',
            'fiscal_officer', 'federal_coordinator', 'reviewer',
        ]
        user_ids = ProductAccess.objects.filter(
            product='harbor', role__in=staff_roles, is_active=True,
        ).values_list('user_id', flat=True)
        return User.objects.filter(pk__in=user_ids).order_by('last_name', 'first_name')
    return User.objects.filter(is_active=True).order_by('last_name', 'first_name')


# Harbor role display labels for signature step assignment
_HARBOR_ROLE_LABELS = {
    'system_admin': 'System Administrator',
    'agency_admin': 'Agency Administrator',
    'program_officer': 'Program Officer',
    'fiscal_officer': 'Fiscal Officer',
    'federal_coordinator': 'Federal Fund Coordinator',
    'reviewer': 'Reviewer',
    'applicant': 'Applicant',
    'auditor': 'Auditor',
}


def get_role_choices():
    """Return role choices suitable for step-assignment forms."""
    if is_harbor():
        staff_roles = [
            'system_admin', 'agency_admin', 'program_officer',
            'fiscal_officer', 'federal_coordinator', 'reviewer',
        ]
        return [('', '---------')] + [
            (r, _HARBOR_ROLE_LABELS.get(r, r)) for r in staff_roles
        ]
    from .models import SignatureRole
    roles = SignatureRole.objects.filter(is_active=True).order_by('label')
    return [('', '---------')] + [(r.key, r.label) for r in roles]


def get_role_label(role_key):
    """Return the display label for a role key string."""
    if not role_key:
        return ''
    if is_harbor():
        return _HARBOR_ROLE_LABELS.get(role_key, role_key)
    from .models import SignatureRole
    try:
        return SignatureRole.objects.get(key=role_key).label
    except SignatureRole.DoesNotExist:
        return role_key
