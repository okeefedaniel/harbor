"""Audit logging utilities for Harbor."""
import logging

from core.models import AuditLog

logger = logging.getLogger(__name__)


def log_audit(user, action, entity_type, entity_id, description='', changes=None, ip_address=None):
    """Create an AuditLog entry.

    Args:
        user: User instance or None
        action: One of AuditLog.Action choices
        entity_type: String like 'Application', 'Award', etc.
        entity_id: String ID of the entity
        description: Human-readable description
        changes: Dict of changes (old/new values)
        ip_address: Client IP address
    """
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
