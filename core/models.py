import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------
class Organization(models.Model):
    """External entity that applies for or receives grants."""

    class OrgType(models.TextChoices):
        MUNICIPALITY = 'municipality', _('Municipality')
        NONPROFIT = 'nonprofit', _('Nonprofit')
        BUSINESS = 'business', _('Business')
        INDIVIDUAL = 'individual', _('Individual')
        TRIBAL = 'tribal', _('Tribal Nation')
        EDUCATIONAL = 'educational', _('Educational Institution')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    org_type = models.CharField(
        max_length=20,
        choices=OrgType.choices,
        default=OrgType.NONPROFIT,
        verbose_name=_('Organization Type'),
    )

    # Federal identifiers
    duns_number = models.CharField(
        max_length=13, blank=True, verbose_name=_('DUNS Number'),
    )
    uei_number = models.CharField(
        max_length=12, blank=True, verbose_name=_('UEI Number'),
    )
    ein = models.CharField(
        max_length=10, blank=True, verbose_name=_('EIN'),
    )

    # SAM registration
    sam_registered = models.BooleanField(
        default=False, verbose_name=_('SAM Registered'),
    )
    sam_expiration = models.DateField(
        null=True, blank=True, verbose_name=_('SAM Expiration Date'),
    )

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, default='CT')
    zip_code = models.CharField(max_length=10, blank=True)

    # Contact
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Organization')
        verbose_name_plural = _('Organizations')

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Agency  (state agencies)
# ---------------------------------------------------------------------------
class Agency(models.Model):
    """State agency that administers grants."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    # State ERP financial codes
    department_code = models.CharField(
        max_length=8, blank=True, verbose_name=_('State ERP Department Code'),
    )
    fund_code = models.CharField(
        max_length=5, blank=True, verbose_name=_('Fund Code'),
    )
    program_code = models.CharField(
        max_length=5, blank=True, verbose_name=_('Program Code'),
    )

    # Primary contact
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)

    address = models.TextField(blank=True)
    website = models.URLField(blank=True)

    can_be_grantee = models.BooleanField(
        default=False,
        help_text=_('Can this agency receive grants from other agencies?'),
    )
    can_be_grantor = models.BooleanField(
        default=True,
        help_text=_('Can this agency award grants?'),
    )

    is_active = models.BooleanField(default=True)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['abbreviation']
        verbose_name = _('Agency')
        verbose_name_plural = _('Agencies')

    def __str__(self):
        return f"{self.abbreviation} - {self.name}"


# ---------------------------------------------------------------------------
# User (custom, extends AbstractUser)
# ---------------------------------------------------------------------------
class User(AbstractUser):
    """Custom user model for the Grantify platform."""

    class Role(models.TextChoices):
        SYSTEM_ADMIN = 'system_admin', _('System Administrator')
        AGENCY_ADMIN = 'agency_admin', _('Agency Administrator')
        PROGRAM_OFFICER = 'program_officer', _('Program Officer')
        FISCAL_OFFICER = 'fiscal_officer', _('Fiscal Officer')
        FEDERAL_COORDINATOR = 'federal_coordinator', _('Federal Fund Coordinator')
        REVIEWER = 'reviewer', _('Reviewer')
        APPLICANT = 'applicant', _('Applicant')
        AUDITOR = 'auditor', _('Auditor')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=25,
        choices=Role.choices,
        default=Role.APPLICANT,
    )
    title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    agency = models.ForeignKey(
        Agency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )

    is_state_user = models.BooleanField(
        default=False,
        help_text=_('Designates whether this user is a state government employee.'),
    )

    accepted_terms = models.BooleanField(default=False)
    accepted_terms_at = models.DateTimeField(null=True, blank=True)

    anthropic_api_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_('Anthropic API Key'),
        help_text=_('Personal Claude API key for AI-powered grant matching.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        full = self.get_full_name()
        return full if full else self.username

    # ----- convenience properties -----

    @property
    def is_agency_staff(self):
        """True when the user holds an agency-level role (includes system admins)."""
        return self.role in {
            self.Role.SYSTEM_ADMIN,
            self.Role.AGENCY_ADMIN,
            self.Role.PROGRAM_OFFICER,
            self.Role.FISCAL_OFFICER,
            self.Role.FEDERAL_COORDINATOR,
        }

    @property
    def can_manage_grants(self):
        """True when the user may create or manage grant programs."""
        return self.role in {
            self.Role.SYSTEM_ADMIN,
            self.Role.AGENCY_ADMIN,
            self.Role.PROGRAM_OFFICER,
            self.Role.FEDERAL_COORDINATOR,
        }

    @property
    def can_manage_federal(self):
        """True when the user may manage federal funding opportunities."""
        return self.role in {
            self.Role.SYSTEM_ADMIN,
            self.Role.FEDERAL_COORDINATOR,
        }

    @property
    def can_review(self):
        """True when the user may review grant applications."""
        return self.role in {
            self.Role.SYSTEM_ADMIN,
            self.Role.AGENCY_ADMIN,
            self.Role.PROGRAM_OFFICER,
            self.Role.REVIEWER,
        }

    @property
    def has_ai_access(self):
        """True when the user has a Claude API key configured."""
        return bool(self.anthropic_api_key)


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
class AuditLog(models.Model):
    """Immutable log of user actions for compliance and auditing."""

    class Action(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        STATUS_CHANGE = 'status_change', _('Status Change')
        SUBMIT = 'submit', _('Submit')
        APPROVE = 'approve', _('Approve')
        REJECT = 'reject', _('Reject')
        LOGIN = 'login', _('Login')
        EXPORT = 'export', _('Export')
        VIEW = 'view', _('View')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
        indexes = [
            models.Index(
                fields=['entity_type', 'entity_id'],
                name='idx_audit_entity',
            ),
            models.Index(
                fields=['user', 'timestamp'],
                name='idx_audit_user_ts',
            ),
        ]

    def __str__(self):
        user_display = self.user if self.user else 'System'
        return f"{user_display} - {self.get_action_display()} - {self.entity_type} ({self.timestamp:%Y-%m-%d %H:%M})"


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
class Notification(models.Model):
    """In-app notification delivered to a user."""

    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        URGENT = 'urgent', _('Urgent')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    link = models.CharField(max_length=500, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        indexes = [
            models.Index(
                fields=['recipient', 'is_read'],
                name='idx_notif_recip_read',
            ),
        ]

    def __str__(self):
        return f"{self.title} -> {self.recipient}"


# ---------------------------------------------------------------------------
# ArchivedRecord
# ---------------------------------------------------------------------------
class ArchivedRecord(models.Model):
    """Tracks archived records for data retention compliance.

    When records are archived, metadata is preserved here while the
    original data may be anonymized or moved to cold storage.
    """

    class EntityType(models.TextChoices):
        APPLICATION = 'application', _('Application')
        AWARD = 'award', _('Award')
        DRAWDOWN = 'drawdown', _('Drawdown Request')
        REPORT = 'report', _('Report')
        AUDIT_LOG = 'audit_log', _('Audit Log')
        TRANSACTION = 'transaction', _('Transaction')

    class RetentionPolicy(models.TextChoices):
        STANDARD = 'standard', _('Standard (7 years)')
        EXTENDED = 'extended', _('Extended (10 years)')
        PERMANENT = 'permanent', _('Permanent')
        FEDERAL = 'federal', _('Federal Requirement (3 years post-closeout)')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    entity_id = models.CharField(max_length=255)
    entity_description = models.TextField(blank=True)

    retention_policy = models.CharField(
        max_length=15,
        choices=RetentionPolicy.choices,
        default=RetentionPolicy.STANDARD,
    )

    original_created_at = models.DateTimeField(
        help_text=_('When the original record was created'),
    )
    archived_at = models.DateTimeField(auto_now_add=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archived_records',
    )

    retention_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When this archived record can be permanently deleted'),
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Preserved metadata from the archived record'),
    )

    is_purged = models.BooleanField(
        default=False,
        help_text=_('Whether the original record has been purged from the system'),
    )
    purged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-archived_at']
        verbose_name = _('Archived Record')
        verbose_name_plural = _('Archived Records')
        indexes = [
            models.Index(
                fields=['entity_type', 'entity_id'],
                name='idx_archive_entity',
            ),
            models.Index(
                fields=['retention_expires_at'],
                name='idx_archive_expiry',
            ),
        ]

    def __str__(self):
        return f"Archived {self.get_entity_type_display()} - {self.entity_id}"
