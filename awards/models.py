import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Award
# ---------------------------------------------------------------------------
class Award(models.Model):
    """Grant award issued to a recipient after application approval."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        PENDING_APPROVAL = 'pending_approval', _('Pending Approval')
        APPROVED = 'approved', _('Approved')
        EXECUTED = 'executed', _('Executed')
        ACTIVE = 'active', _('Active')
        ON_HOLD = 'on_hold', _('On Hold')
        COMPLETED = 'completed', _('Completed')
        TERMINATED = 'terminated', _('Terminated')
        CANCELLED = 'cancelled', _('Cancelled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='award',
    )
    grant_program = models.ForeignKey(
        'grants.GrantProgram',
        on_delete=models.CASCADE,
        related_name='awards',
    )
    agency = models.ForeignKey(
        'core.Agency',
        on_delete=models.CASCADE,
        related_name='awards',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='awards_received',
    )
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.CASCADE,
        related_name='awards',
    )

    award_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    award_amount = models.DecimalField(max_digits=15, decimal_places=2)
    award_date = models.DateField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)

    terms_and_conditions = models.TextField()
    special_conditions = models.TextField(blank=True)

    requires_match = models.BooleanField(default=False)
    match_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_awards',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Award')
        verbose_name_plural = _('Awards')

    def __str__(self):
        return f"{self.award_number} - {self.title}"


# ---------------------------------------------------------------------------
# AwardAmendment
# ---------------------------------------------------------------------------
class AwardAmendment(models.Model):
    """Formal modification to an existing award."""

    class AmendmentType(models.TextChoices):
        BUDGET_MODIFICATION = 'budget_modification', _('Budget Modification')
        TIME_EXTENSION = 'time_extension', _('Time Extension')
        SCOPE_CHANGE = 'scope_change', _('Scope Change')
        PERSONNEL_CHANGE = 'personnel_change', _('Personnel Change')
        OTHER = 'other', _('Other')

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        APPROVED = 'approved', _('Approved')
        DENIED = 'denied', _('Denied')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        Award,
        on_delete=models.CASCADE,
        related_name='amendments',
    )
    amendment_number = models.IntegerField()
    amendment_type = models.CharField(
        max_length=25,
        choices=AmendmentType.choices,
    )
    description = models.TextField()
    old_value = models.JSONField(default=dict)
    new_value = models.JSONField(default=dict)

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_amendments',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_amendments',
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['award', 'amendment_number']
        verbose_name = _('Award Amendment')
        verbose_name_plural = _('Award Amendments')

    def __str__(self):
        return f"{self.award.award_number} - Amendment #{self.amendment_number}"


# ---------------------------------------------------------------------------
# AwardDocument
# ---------------------------------------------------------------------------
class AwardDocument(models.Model):
    """Document attached to an award."""

    class DocumentType(models.TextChoices):
        AGREEMENT = 'agreement', _('Agreement')
        AMENDMENT = 'amendment', _('Amendment')
        CORRESPONDENCE = 'correspondence', _('Correspondence')
        REPORT = 'report', _('Report')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        Award,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='awards/docs/')
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_award_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Award Document')
        verbose_name_plural = _('Award Documents')

    def __str__(self):
        return f"{self.award.award_number} - {self.title}"


# ---------------------------------------------------------------------------
# SubRecipient
# ---------------------------------------------------------------------------
class SubRecipient(models.Model):
    """Sub-recipient/sub-grantee receiving pass-through funds from a primary award."""

    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        SUSPENDED = 'suspended', _('Suspended')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name='sub_recipients')
    organization = models.ForeignKey('core.Organization', on_delete=models.PROTECT, related_name='sub_recipient_awards')
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    sub_award_amount = models.DecimalField(max_digits=15, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    scope_of_work = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE)
    risk_level = models.CharField(max_length=10, choices=[('low', _('Low')), ('medium', _('Medium')), ('high', _('High'))], default='low')
    monitoring_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name']
        verbose_name = _('Sub-Recipient')
        verbose_name_plural = _('Sub-Recipients')

    def __str__(self):
        return f"{self.organization.name} - {self.award.award_number}"


# ---------------------------------------------------------------------------
# PerformanceMetric
# ---------------------------------------------------------------------------
class PerformanceMetric(models.Model):
    """Tracks performance outcomes and KPIs for an award."""

    class MetricType(models.TextChoices):
        OUTPUT = 'output', _('Output')
        OUTCOME = 'outcome', _('Outcome')
        EFFICIENCY = 'efficiency', _('Efficiency')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name='performance_metrics')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metric_type = models.CharField(max_length=15, choices=MetricType.choices, default=MetricType.OUTPUT)
    target_value = models.DecimalField(max_digits=15, decimal_places=2)
    actual_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unit_of_measure = models.CharField(max_length=100, help_text=_('e.g. people served, jobs created'))
    reporting_period = models.CharField(max_length=50, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['award', 'name']
        verbose_name = _('Performance Metric')
        verbose_name_plural = _('Performance Metrics')

    def __str__(self):
        return f"{self.award.award_number} - {self.name}"

    @property
    def percent_achieved(self):
        if self.target_value and self.actual_value:
            return round((self.actual_value / self.target_value) * 100, 1)
        return 0


# ---------------------------------------------------------------------------
# SignatureRequest  (DocuSign e-Signature)
# ---------------------------------------------------------------------------
class SignatureRequest(models.Model):
    """Tracks a DocuSign e-signature request for an award agreement."""

    class Status(models.TextChoices):
        SENT = 'sent', _('Sent')
        DELIVERED = 'delivered', _('Delivered')
        SIGNED = 'signed', _('Signed')
        DECLINED = 'declined', _('Declined')
        VOIDED = 'voided', _('Voided')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name='signature_requests')
    envelope_id = models.CharField(max_length=100, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_signatures',
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    signed_document = models.FileField(upload_to='awards/signed/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = _('Signature Request')
        verbose_name_plural = _('Signature Requests')

    def __str__(self):
        return f"Signature for {self.award.award_number} - {self.get_status_display()}"
