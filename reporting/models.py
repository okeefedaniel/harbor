import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.validators import validate_document_file


# ---------------------------------------------------------------------------
# ReportTemplate
# ---------------------------------------------------------------------------
class ReportTemplate(models.Model):
    """Defines the structure and schedule for a type of grant report."""

    class ReportType(models.TextChoices):
        PROGRESS = 'progress', _('Progress')
        FISCAL = 'fiscal', _('Fiscal')
        PROGRAMMATIC = 'programmatic', _('Programmatic')
        FINAL_PROGRESS = 'final_progress', _('Final Progress')
        FINAL_FISCAL = 'final_fiscal', _('Final Fiscal')
        SF425 = 'sf425', _('SF-425 Federal Financial Report')
        CUSTOM = 'custom', _('Custom')

    class Frequency(models.TextChoices):
        MONTHLY = 'monthly', _('Monthly')
        QUARTERLY = 'quarterly', _('Quarterly')
        SEMI_ANNUAL = 'semi_annual', _('Semi-Annual')
        ANNUAL = 'annual', _('Annual')
        ONE_TIME = 'one_time', _('One Time')
        AS_NEEDED = 'as_needed', _('As Needed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
    )
    agency = models.ForeignKey(
        'core.Agency',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='report_templates',
        help_text=_('Leave blank for statewide templates.'),
    )
    sections = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Defines the report structure and fields.'),
    )
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.QUARTERLY,
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_report_templates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Report Template')
        verbose_name_plural = _('Report Templates')

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
class Report(models.Model):
    """A report submitted by a grantee against an award."""

    class ReportType(models.TextChoices):
        PROGRESS = 'progress', _('Progress')
        FISCAL = 'fiscal', _('Fiscal')
        PROGRAMMATIC = 'programmatic', _('Programmatic')
        FINAL_PROGRESS = 'final_progress', _('Final Progress')
        FINAL_FISCAL = 'final_fiscal', _('Final Fiscal')
        SF425 = 'sf425', _('SF-425 Federal Financial Report')
        CUSTOM = 'custom', _('Custom')

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        UNDER_REVIEW = 'under_review', _('Under Review')
        REVISION_REQUESTED = 'revision_requested', _('Revision Requested')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='reports',
    )
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports',
    )
    report_type = models.CharField(
        max_length=20,
        choices=ReportType.choices,
    )
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Stores the actual report data.'),
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_reports',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_reports',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_comments = models.TextField(blank=True, default='')
    due_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-due_date']
        verbose_name = _('Report')
        verbose_name_plural = _('Reports')

    def __str__(self):
        return (
            f"{self.get_report_type_display()} Report - "
            f"{self.reporting_period_start} to {self.reporting_period_end}"
        )

    @property
    def is_overdue(self):
        """True when the report is past its due date and has not been submitted or approved."""
        if self.status in (self.Status.APPROVED, self.Status.SUBMITTED, self.Status.UNDER_REVIEW):
            return False
        return self.due_date < timezone.now().date()


# ---------------------------------------------------------------------------
# ReportDocument
# ---------------------------------------------------------------------------
class ReportDocument(models.Model):
    """File attachment associated with a report."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='reports/docs/', validators=[validate_document_file])
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_report_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Report Document')
        verbose_name_plural = _('Report Documents')

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# SF425Report  (Federal Financial Report)
# ---------------------------------------------------------------------------
class SF425Report(models.Model):
    """Federal Financial Report (Standard Form 425) for federally funded awards."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        APPROVED = 'approved', _('Approved')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='sf425_reports',
    )
    reporting_period_start = models.DateField()
    reporting_period_end = models.DateField()
    federal_cash_receipts = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    federal_expenditures = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    federal_unliquidated_obligations = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    recipient_share_expenditures = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    remaining_federal_funds = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Stores all SF-425 fields.'),
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='generated_sf425_reports',
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_sf425_reports',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-reporting_period_end']
        verbose_name = _('SF-425 Report')
        verbose_name_plural = _('SF-425 Reports')

    def __str__(self):
        return (
            f"SF-425 - {self.award} - "
            f"{self.reporting_period_start} to {self.reporting_period_end}"
        )
