import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Closeout
# ---------------------------------------------------------------------------
class Closeout(models.Model):
    """Grant award closeout process tracker."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', _('Not Started')
        IN_PROGRESS = 'in_progress', _('In Progress')
        PENDING_REVIEW = 'pending_review', _('Pending Review')
        COMPLETED = 'completed', _('Completed')
        REOPENED = 'reopened', _('Reopened')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.OneToOneField(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='closeout',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    initiated_at = models.DateTimeField(auto_now_add=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='initiated_closeouts',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_closeouts',
    )

    class Meta:
        ordering = ['-initiated_at']
        verbose_name = _('Closeout')
        verbose_name_plural = _('Closeouts')

    def __str__(self):
        return f"Closeout - {self.award} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# CloseoutChecklist
# ---------------------------------------------------------------------------
class CloseoutChecklist(models.Model):
    """Individual checklist item within a closeout process."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    closeout = models.ForeignKey(
        Closeout,
        on_delete=models.CASCADE,
        related_name='checklist_items',
    )
    item_name = models.CharField(max_length=255)
    item_description = models.TextField(blank=True, default='')
    is_required = models.BooleanField(default=True)
    is_completed = models.BooleanField(default=False)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_checklist_items',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['item_name']
        verbose_name = _('Closeout Checklist Item')
        verbose_name_plural = _('Closeout Checklist Items')

    def __str__(self):
        status = 'Done' if self.is_completed else 'Pending'
        return f"{self.item_name} [{status}]"


# ---------------------------------------------------------------------------
# CloseoutDocument
# ---------------------------------------------------------------------------
class CloseoutDocument(models.Model):
    """Document uploaded as part of the closeout process."""

    class DocumentType(models.TextChoices):
        FINAL_PROGRESS_REPORT = 'final_progress_report', _('Final Progress Report')
        FINAL_FISCAL_REPORT = 'final_fiscal_report', _('Final Fiscal Report')
        AUDIT_REPORT = 'audit_report', _('Audit Report')
        INVENTORY_REPORT = 'inventory_report', _('Inventory Report')
        REFUND_DOCUMENTATION = 'refund_documentation', _('Refund Documentation')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    closeout = models.ForeignKey(
        Closeout,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=25,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    file = models.FileField(upload_to='closeout/docs/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_closeout_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Closeout Document')
        verbose_name_plural = _('Closeout Documents')

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"


# ---------------------------------------------------------------------------
# FundReturn
# ---------------------------------------------------------------------------
class FundReturn(models.Model):
    """Tracks funds returned to the granting agency during closeout."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        PROCESSED = 'processed', _('Processed')
        CONFIRMED = 'confirmed', _('Confirmed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    closeout = models.ForeignKey(
        Closeout,
        on_delete=models.CASCADE,
        related_name='fund_returns',
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_reference = models.CharField(max_length=255, blank=True, default='')
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_fund_returns',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Fund Return')
        verbose_name_plural = _('Fund Returns')

    def __str__(self):
        return f"${self.amount} - {self.get_status_display()}"
