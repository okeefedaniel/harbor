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
    username = getattr(user, 'username', 'system') if user else 'system'
    logger.info(
        'AUDIT [%s] %s %s(%s): %s',
        username, action, entity_type, entity_id, description,
    )


def get_audit_log_model():
    """Return ``core.models.AuditLog`` if available, else ``None``."""
    if is_harbor():
        from core.models import AuditLog
        return AuditLog
    return None


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def build_absolute_url(path):
    """Return a fully-qualified URL for *path*."""
    if is_harbor():
        from core.notifications import _build_absolute_url
        return _build_absolute_url(path)
    domain = getattr(settings, 'SIGNSTREAMER_SITE_URL', None)
    if not domain:
        domain = os.environ.get('SITE_URL', 'http://localhost:8000')
    return f'{domain.rstrip("/")}{path}'


def create_notification(recipient, title, message, link='', priority='medium'):
    """Create an in-app notification (Harbor) or just log it."""
    if is_harbor():
        from core.notifications import _create_notification
        return _create_notification(recipient, title, message, link, priority)
    logger.info('NOTIFICATION [%s] %s: %s', recipient, title, message)


def send_notification_email(recipient_email, subject, template_name, context):
    """Send an HTML email notification."""
    if is_harbor():
        from core.notifications import _send_notification_email
        return _send_notification_email(
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
    """Standalone fallback: require ``is_staff``."""

    def test_func(self):
        return self.request.user.is_staff


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
        from core.models import User as CoreUser
        staff_roles = [
            CoreUser.Role.SYSTEM_ADMIN,
            CoreUser.Role.AGENCY_ADMIN,
            CoreUser.Role.PROGRAM_OFFICER,
            CoreUser.Role.FISCAL_OFFICER,
            CoreUser.Role.FEDERAL_COORDINATOR,
            CoreUser.Role.REVIEWER,
        ]
        return User.objects.filter(
            role__in=staff_roles,
        ).order_by('last_name', 'first_name')
    return User.objects.filter(
        is_active=True,
    ).order_by('last_name', 'first_name')


def get_role_choices():
    """Return role choices suitable for step-assignment forms."""
    if is_harbor():
        from core.models import User
        staff_roles = [
            User.Role.SYSTEM_ADMIN,
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.FISCAL_OFFICER,
            User.Role.FEDERAL_COORDINATOR,
            User.Role.REVIEWER,
        ]
        return [('', '---------')] + [
            (role.value, role.label) for role in User.Role
            if role.value in [r.value for r in staff_roles]
        ]
    # Standalone mode: pull from the SignatureRole model
    from .models import SignatureRole
    roles = SignatureRole.objects.filter(is_active=True).order_by('label')
    return [('', '---------')] + [(r.key, r.label) for r in roles]


def get_role_label(role_key):
    """Return the display label for a role key string."""
    if not role_key:
        return ''
    if is_harbor():
        from core.models import User
        try:
            return User.Role(role_key).label
        except ValueError:
            return role_key
    from .models import SignatureRole
    try:
        return SignatureRole.objects.get(key=role_key).label
    except SignatureRole.DoesNotExist:
        return role_key
