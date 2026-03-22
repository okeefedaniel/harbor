import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from keel.core.models import AbstractAuditLog, AbstractNotification
from keel.notifications.models import AbstractNotificationPreference

from core.validators import validate_document_file, validate_image_file

# Detect whether the grants app is installed so we can conditionally
# define the grant_program FK.  This runs at class-definition time
# (after Django settings are loaded) and affects both the model AND
# the migration auto-detector.
_GRANTS_INSTALLED = any(
    app == 'grants' or app.startswith('grants.')
    for app in settings.INSTALLED_APPS
)


# ---------------------------------------------------------------------------
# SignatureFlow — Reusable workflow template
# ---------------------------------------------------------------------------
class SignatureFlow(models.Model):
    """Reusable signing workflow template. Optionally linked to a GrantProgram."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(_('name'), max_length=255)
    description = models.TextField(_('description'), blank=True, default='')

    is_active = models.BooleanField(_('active'), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_signature_flows',
        verbose_name=_('created by'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Signature Flow')
        verbose_name_plural = _('Signature Flows')

    def __str__(self):
        return self.name

    @property
    def step_count(self):
        return self.steps.count()


# Conditionally add the grant_program FK only when the grants app is installed.
# This ensures standalone (Manifest) deployments have no dependency on grants.
if _GRANTS_INSTALLED:
    SignatureFlow.add_to_class(
        'grant_program',
        models.ForeignKey(
            'grants.GrantProgram',
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            related_name='signature_flows',
            verbose_name=_('grant program'),
            help_text=_('Link to a grant program (leave blank for standalone use).'),
        ),
    )


# ---------------------------------------------------------------------------
# SignatureFlowStep — Steps in the workflow template
# ---------------------------------------------------------------------------
class SignatureFlowStep(models.Model):
    """A step in a signature flow. Steps are executed sequentially by order."""

    class AssignmentType(models.TextChoices):
        USER = 'user', _('Specific User')
        ROLE = 'role', _('Role')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        SignatureFlow,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('flow'),
    )
    order = models.PositiveIntegerField(
        _('order'),
        help_text=_('Execution order (1 = first signer).'),
    )
    label = models.CharField(
        _('label'),
        max_length=255,
        help_text=_('e.g. "Program Officer Approval", "Division Director Sign-off"'),
    )

    assignment_type = models.CharField(
        _('assignment type'),
        max_length=10,
        choices=AssignmentType.choices,
        default=AssignmentType.ROLE,
    )
    assigned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_flow_steps',
        verbose_name=_('assigned user'),
        help_text=_('Specific user (when assignment type is "user").'),
    )
    assigned_role = models.CharField(
        _('assigned role'),
        max_length=25,
        blank=True,
        default='',
        help_text=_('Role key from User.Role (when assignment type is "role").'),
    )

    is_required = models.BooleanField(_('required'), default=True)

    class Meta:
        ordering = ['flow', 'order']
        unique_together = ['flow', 'order']
        verbose_name = _('Signature Flow Step')
        verbose_name_plural = _('Signature Flow Steps')

    def __str__(self):
        return f"Step {self.order}: {self.label}"

    def get_role_display(self):
        """Return the human-readable label for assigned_role."""
        from .compat import get_role_label
        return get_role_label(self.assigned_role)


# ---------------------------------------------------------------------------
# SignatureDocument — PDF template attached to a flow
# ---------------------------------------------------------------------------
class SignatureDocument(models.Model):
    """A PDF document that needs to be signed as part of a flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        SignatureFlow,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name=_('flow'),
    )
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True, default='')
    file = models.FileField(_('file'), upload_to='signatures/templates/', validators=[validate_document_file])
    page_count = models.PositiveIntegerField(
        _('page count'),
        default=0,
        help_text=_('Auto-populated on upload.'),
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_signature_documents',
        verbose_name=_('uploaded by'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['flow', 'title']
        verbose_name = _('Signature Document')
        verbose_name_plural = _('Signature Documents')

    def __str__(self):
        return f"{self.title} ({self.flow.name})"


# ---------------------------------------------------------------------------
# SignaturePlacement — Where on a PDF page a signature goes
# ---------------------------------------------------------------------------
class SignaturePlacement(models.Model):
    """Defines where a signature/initials/date field appears on a PDF page.

    Coordinates are stored as **percentages** of page dimensions so placements
    remain correct regardless of rendering DPI or zoom level.
    """

    class FieldType(models.TextChoices):
        SIGNATURE = 'signature', _('Signature')
        INITIALS = 'initials', _('Initials')
        DATE = 'date', _('Date Signed')
        NAME = 'name', _('Printed Name')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        SignatureDocument,
        on_delete=models.CASCADE,
        related_name='placements',
        verbose_name=_('document'),
    )
    step = models.ForeignKey(
        SignatureFlowStep,
        on_delete=models.CASCADE,
        related_name='placements',
        verbose_name=_('step'),
        help_text=_('Which signer step this placement belongs to.'),
    )
    field_type = models.CharField(
        _('field type'),
        max_length=15,
        choices=FieldType.choices,
        default=FieldType.SIGNATURE,
    )
    page_number = models.PositiveIntegerField(
        _('page number'),
        help_text=_('1-indexed page number.'),
    )
    x = models.FloatField(
        _('X position'),
        help_text=_('X position as percentage of page width (0-100).'),
    )
    y = models.FloatField(
        _('Y position'),
        help_text=_('Y position as percentage of page height (0-100).'),
    )
    width = models.FloatField(
        _('width'),
        default=20.0,
        help_text=_('Width as percentage of page width.'),
    )
    height = models.FloatField(
        _('height'),
        default=5.0,
        help_text=_('Height as percentage of page height.'),
    )

    class Meta:
        ordering = ['document', 'page_number', 'y', 'x']
        verbose_name = _('Signature Placement')
        verbose_name_plural = _('Signature Placements')

    def __str__(self):
        return (
            f"{self.get_field_type_display()} on page {self.page_number} "
            f"for {self.step.label}"
        )


# ---------------------------------------------------------------------------
# SigningPacket — Active signing session (instance of a flow)
# ---------------------------------------------------------------------------
class SigningPacket(models.Model):
    """An instance of a signature flow being executed for a specific entity."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        DECLINED = 'declined', _('Declined')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        SignatureFlow,
        on_delete=models.PROTECT,
        related_name='packets',
        verbose_name=_('flow'),
    )

    # Generic FK to attach to any model (Award, Closeout, or standalone)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('content type'),
    )
    object_id = models.CharField(
        _('object ID'),
        max_length=255,
        blank=True,
        default='',
    )
    source_entity = GenericForeignKey('content_type', 'object_id')

    title = models.CharField(
        _('title'),
        max_length=255,
        help_text=_('Descriptive title for this signing session.'),
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_signing_packets',
        verbose_name=_('initiated by'),
    )

    # Final signed document — generated after all signers complete
    signed_document = models.FileField(
        _('signed document'),
        upload_to='signatures/signed/',
        null=True,
        blank=True,
        validators=[validate_document_file],
    )

    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    cancelled_at = models.DateTimeField(_('cancelled at'), null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_signing_packets',
        verbose_name=_('cancelled by'),
    )
    cancel_reason = models.TextField(_('cancel reason'), blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Signing Packet')
        verbose_name_plural = _('Signing Packets')
        indexes = [
            models.Index(
                fields=['content_type', 'object_id'],
                name='idx_packet_entity',
            ),
            models.Index(
                fields=['status', 'created_at'],
                name='idx_packet_status',
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def progress(self):
        """Return (signed_count, total_count) tuple."""
        steps = self.steps.all()
        total = steps.count()
        signed = steps.filter(status=SigningStep.Status.SIGNED).count()
        return signed, total

    @property
    def current_step(self):
        """Return the currently active signing step, if any."""
        return self.steps.filter(status=SigningStep.Status.ACTIVE).first()


# ---------------------------------------------------------------------------
# SigningStep — Status of each step in an active packet
# ---------------------------------------------------------------------------
class SigningStep(models.Model):
    """Tracks the status of a single signing step within a packet."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        ACTIVE = 'active', _('Active')
        SIGNED = 'signed', _('Signed')
        DECLINED = 'declined', _('Declined')
        SKIPPED = 'skipped', _('Skipped')

    class SignatureType(models.TextChoices):
        TYPED = 'typed', _('Typed')
        UPLOADED = 'uploaded', _('Uploaded Image')
        DRAWN = 'drawn', _('Drawn')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    packet = models.ForeignKey(
        SigningPacket,
        on_delete=models.CASCADE,
        related_name='steps',
        verbose_name=_('packet'),
    )
    flow_step = models.ForeignKey(
        SignatureFlowStep,
        on_delete=models.PROTECT,
        related_name='signing_steps',
        verbose_name=_('flow step'),
    )
    order = models.PositiveIntegerField(_('order'))

    signer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='signing_steps',
        verbose_name=_('signer'),
        help_text=_('User assigned to sign at this step.'),
    )

    status = models.CharField(
        _('status'),
        max_length=15,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # Signature data (populated when signed)
    signature_type = models.CharField(
        _('signature type'),
        max_length=10,
        choices=SignatureType.choices,
        blank=True,
        default='',
    )
    typed_name = models.CharField(
        _('typed name'),
        max_length=255,
        blank=True,
        default='',
        help_text=_('Name typed as signature.'),
    )
    signature_image = models.FileField(
        _('signature image'),
        upload_to='signatures/captured/',
        null=True,
        blank=True,
        help_text=_('Uploaded or drawn signature image (PNG).'),
        validators=[validate_image_file],
    )

    signed_at = models.DateTimeField(_('signed at'), null=True, blank=True)
    signed_ip = models.GenericIPAddressField(_('signed IP'), null=True, blank=True)
    declined_at = models.DateTimeField(_('declined at'), null=True, blank=True)
    decline_reason = models.TextField(_('decline reason'), blank=True, default='')

    reminded_at = models.DateTimeField(
        _('reminded at'),
        null=True,
        blank=True,
        help_text=_('Last time a reminder email was sent.'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['packet', 'order']
        verbose_name = _('Signing Step')
        verbose_name_plural = _('Signing Steps')
        indexes = [
            models.Index(
                fields=['signer', 'status'],
                name='idx_signstep_signer_status',
            ),
        ]

    def __str__(self):
        return (
            f"Step {self.order} ({self.signer.get_full_name()}) "
            f"— {self.get_status_display()}"
        )


# ---------------------------------------------------------------------------
# UserSignature — Saved signature preferences per user
# ---------------------------------------------------------------------------
class UserSignature(models.Model):
    """A user's saved signature for quick reuse."""

    class SignatureType(models.TextChoices):
        TYPED = 'typed', _('Typed')
        UPLOADED = 'uploaded', _('Uploaded Image')
        DRAWN = 'drawn', _('Drawn')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_signatures',
        verbose_name=_('user'),
    )
    label = models.CharField(
        _('label'),
        max_length=100,
        default='Default',
        help_text=_('Label for this signature (e.g. "Formal", "Initials").'),
    )
    signature_type = models.CharField(
        _('signature type'),
        max_length=10,
        choices=SignatureType.choices,
    )
    typed_name = models.CharField(
        _('typed name'),
        max_length=255,
        blank=True,
        default='',
    )
    signature_image = models.FileField(
        _('signature image'),
        upload_to='signatures/saved/',
        null=True,
        blank=True,
        validators=[validate_image_file],
    )
    is_default = models.BooleanField(_('default'), default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        verbose_name = _('User Signature')
        verbose_name_plural = _('User Signatures')

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.label} ({self.get_signature_type_display()})"


# ---------------------------------------------------------------------------
# SignatureRole — Manageable roles for standalone mode
# ---------------------------------------------------------------------------
class SignatureRole(models.Model):
    """Manageable roles for standalone (Manifest) mode.

    In Harbor mode, roles come from core.models.User.Role instead.
    This model provides a database-backed alternative so admins can
    add, edit, and delete roles through the UI.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(
        _('key'),
        max_length=25,
        unique=True,
        help_text=_('Machine-readable identifier (e.g. "director").'),
    )
    label = models.CharField(
        _('label'),
        max_length=100,
        help_text=_('Human-readable name (e.g. "Director").'),
    )
    description = models.TextField(_('description'), blank=True, default='')
    is_active = models.BooleanField(_('active'), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']
        verbose_name = _('Signature Role')
        verbose_name_plural = _('Signature Roles')

    def __str__(self):
        return self.label


# ---------------------------------------------------------------------------
# Notification — Used by Manifest standalone
# In Harbor mode, core.Notification is used instead.
# ---------------------------------------------------------------------------
class Notification(AbstractNotification):
    """Manifest in-app notification."""

    class Meta(AbstractNotification.Meta):
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')


class NotificationPreference(AbstractNotificationPreference):
    """Manifest per-user notification channel preferences."""

    class Meta(AbstractNotificationPreference.Meta):
        verbose_name = _('Notification Preference')
        verbose_name_plural = _('Notification Preferences')


# ---------------------------------------------------------------------------
# AuditLog — Used by Manifest standalone (KEEL_AUDIT_LOG_MODEL = 'signatures.AuditLog')
# In Harbor mode, core.AuditLog is used instead.
# ---------------------------------------------------------------------------
class AuditLog(AbstractAuditLog):
    """Manifest audit log — inherits from Keel's immutable AbstractAuditLog."""

    class Meta(AbstractAuditLog.Meta):
        verbose_name = _('Audit Log')
        verbose_name_plural = _('Audit Logs')
