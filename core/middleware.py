import logging

from django.contrib.auth.signals import user_logged_in

from core.models import AuditLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    """Extract the client IP address from the request.

    Checks the ``X-Forwarded-For`` header first (for proxied setups such as
    Railway or load balancers), then falls back to ``REMOTE_ADDR``.
    """
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        # X-Forwarded-For may contain a chain: client, proxy1, proxy2, ...
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _handle_user_logged_in(sender, request, user, **kwargs):
    """Signal handler for ``user_logged_in`` — creates a LOGIN audit entry."""
    ip_address = getattr(request, 'audit_ip', None) if request else None
    try:
        AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.LOGIN,
            entity_type='User',
            entity_id=str(user.pk),
            description=f'User {user} logged in.',
            changes={},
            ip_address=ip_address,
        )
    except Exception:
        logger.exception('Failed to create login audit log entry')


class AuditMiddleware:
    """Middleware that captures per-request audit metadata.

    * Resolves the client IP address (respecting ``X-Forwarded-For``) and
      attaches it to the request as ``request.audit_ip`` so downstream code
      (views, utilities) can reference it.
    * Connects the ``user_logged_in`` signal so that login events are
      automatically recorded in the audit log.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Connect the login signal once when the middleware is initialised.
        user_logged_in.connect(_handle_user_logged_in)

    def __call__(self, request):
        # Attach the client IP to the request for downstream audit logging.
        request.audit_ip = _get_client_ip(request)

        response = self.get_response(request)
        return response
