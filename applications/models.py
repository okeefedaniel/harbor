import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.validators import validate_document_file


class Application(models.Model):
    """A grant application submitted by an organization for a grant program."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        UNDER_REVIEW = 'under_review', _('Under Review')
        REVISION_REQUESTED = 'revision_requested', _('Revision Requested')
        APPROVED = 'approved', _('Approved')
        DENIED = 'denied', _('Denied')
        WITHDRAWN = 'withdrawn', _('Withdrawn')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant_program = models.ForeignKey(
        'grants.GrantProgram',
        on_delete=models.PROTECT,
        related_name='applications',
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='applications',
    )
    organization = models.ForeignKey(
        'core.Organization',
        on_delete=models.PROTECT,
        related_name='applications',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Project details
    project_title = models.CharField(max_length=500)
    project_description = models.TextField()
    requested_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_('Amount of funding requested'),
    )
    proposed_start_date = models.DateField()
    proposed_end_date = models.DateField()

    # Match information
    match_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Proposed matching contribution amount'),
    )
    match_description = models.TextField(
        blank=True,
        default='',
        help_text=_('Description of matching funds or in-kind contributions'),
    )

    # Versioning
    version = models.IntegerField(default=1)
    version_notes = models.TextField(blank=True, default='')

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Application')
        verbose_name_plural = _('Applications')

    def __str__(self):
        return f"{self.project_title} - {self.organization}"

    def get_absolute_url(self):
        return reverse('applications:detail', kwargs={'pk': self.pk})

    @property
    def is_editable(self):
        """Return True if the application can still be edited."""
        return self.status in (self.Status.DRAFT, self.Status.REVISION_REQUESTED)


class ApplicationSection(models.Model):
    """A section within an application, storing flexible form data as JSON."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    section_name = models.CharField(max_length=255)
    section_order = models.IntegerField(default=0)
    content = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Flexible form data stored as JSON'),
    )
    is_complete = models.BooleanField(default=False)

    class Meta:
        ordering = ['section_order']
        unique_together = [('application', 'section_order')]
        verbose_name = _('Application Section')
        verbose_name_plural = _('Application Sections')

    def __str__(self):
        return f"{self.application.project_title} - {self.section_name}"


class ApplicationDocument(models.Model):
    """Supporting documents uploaded with an application."""

    class DocumentType(models.TextChoices):
        NARRATIVE = 'narrative', _('Project Narrative')
        BUDGET = 'budget', _('Budget')
        BUDGET_JUSTIFICATION = 'budget_justification', _('Budget Justification')
        LETTERS_OF_SUPPORT = 'letters_of_support', _('Letters of Support')
        RESUMES = 'resumes', _('Resumes / CVs')
        ORGANIZATIONAL_CHART = 'organizational_chart', _('Organizational Chart')
        AUDIT_REPORT = 'audit_report', _('Audit Report')
        TAX_EXEMPT_LETTER = 'tax_exempt_letter', _('Tax-Exempt Determination Letter')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to='applications/docs/', validators=[validate_document_file])
    document_type = models.CharField(
        max_length=25,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_application_documents',
    )
    version_number = models.IntegerField(default=1)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', 'title']
        verbose_name = _('Application Document')
        verbose_name_plural = _('Application Documents')

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"


class ApplicationComment(models.Model):
    """Comments on an application, with support for internal staff-only notes."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='application_comments',
    )
    content = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text=_('If True, this comment is visible only to staff reviewers'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Application Comment')
        verbose_name_plural = _('Application Comments')

    def __str__(self):
        visibility = 'Internal' if self.is_internal else 'Public'
        return f"Comment by {self.author} ({visibility}) on {self.application}"


class ApplicationComplianceItem(models.Model):
    """Pre-award due-diligence checklist item for an application.

    Each item represents a compliance requirement that must be verified
    by agency staff before the application can be approved.  Items are
    created automatically when an application is submitted and can be
    toggled via the application detail page.
    """

    class ItemType(models.TextChoices):
        SAM_REGISTRATION = 'sam_registration', _('SAM Registration Active')
        TAX_EXEMPT = 'tax_exempt', _('Tax-Exempt Status Verified')
        AUDIT_CLEARANCE = 'audit_clearance', _('Audit Clearance')
        DEBARMENT_CHECK = 'debarment_check', _('Debarment / Suspension Check')
        BUDGET_REVIEW = 'budget_review', _('Budget Review Complete')
        NARRATIVE_REVIEW = 'narrative_review', _('Narrative Review Complete')
        INSURANCE_VERIFIED = 'insurance_verified', _('Insurance Verification')
        MATCH_VERIFIED = 'match_verified', _('Match Funds Verified')
        CONFLICT_OF_INTEREST = 'conflict_of_interest', _('Conflict of Interest Check')
        ELIGIBILITY_CONFIRMED = 'eligibility_confirmed', _('Eligibility Confirmed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='compliance_items',
    )
    item_type = models.CharField(
        max_length=30,
        choices=ItemType.choices,
    )
    label = models.CharField(
        max_length=255,
        help_text=_('Human-readable description of the compliance requirement'),
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_compliance_items',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(
        blank=True,
        default='',
        help_text=_('Staff notes about this compliance item'),
    )
    is_required = models.BooleanField(
        default=True,
        help_text=_('Whether this item must be verified before approval'),
    )

    class Meta:
        ordering = ['item_type']
        unique_together = [('application', 'item_type')]
        verbose_name = _('Application Compliance Item')
        verbose_name_plural = _('Application Compliance Items')

    def __str__(self):
        status = 'Verified' if self.is_verified else 'Pending'
        return f"{self.label} ({status})"


class StaffDocument(models.Model):
    """Internal staff documents attached to an application.

    These are separate from applicant-uploaded documents and are only
    visible to agency staff (e.g. verification letters, due-diligence
    memos, background check results).
    """

    class DocumentType(models.TextChoices):
        VERIFICATION = 'verification', _('Verification Document')
        BACKGROUND_CHECK = 'background_check', _('Background Check')
        DUE_DILIGENCE = 'due_diligence', _('Due Diligence Memo')
        REFERENCE_CHECK = 'reference_check', _('Reference Check')
        SITE_VISIT = 'site_visit', _('Site Visit Report')
        LEGAL_REVIEW = 'legal_review', _('Legal Review')
        FINANCIAL_REVIEW = 'financial_review', _('Financial Review')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='staff_documents',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to='applications/staff_docs/', validators=[validate_document_file])
    document_type = models.CharField(
        max_length=25,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_staff_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', 'title']
        verbose_name = _('Staff Document')
        verbose_name_plural = _('Staff Documents')

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"


class ApplicationStatusHistory(models.Model):
    """Audit trail of status changes for an application."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    old_status = models.CharField(
        max_length=20,
        choices=Application.Status.choices,
    )
    new_status = models.CharField(
        max_length=20,
        choices=Application.Status.choices,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='application_status_changes',
    )
    comment = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Application Status History')
        verbose_name_plural = _('Application Status Histories')

    def __str__(self):
        return f"{self.application}: {self.old_status} -> {self.new_status}"


class ApplicationAssignment(models.Model):
    """Assignment of internal staff to process/work on an application.

    This is distinct from ReviewAssignment (which is for formal scoring
    reviews with rubrics).  ApplicationAssignment tracks which staff member
    is responsible for shepherding an application through the
    due-diligence pipeline.
    """

    class Status(models.TextChoices):
        ASSIGNED = 'assigned', _('Assigned')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        REASSIGNED = 'reassigned', _('Reassigned')

    class AssignmentType(models.TextChoices):
        CLAIMED = 'claimed', _('Self-Claimed')
        MANAGER_ASSIGNED = 'manager_assigned', _('Manager Assigned')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        'Application',
        on_delete=models.CASCADE,
        related_name='staff_assignments',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='application_assignments',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_applications',
        help_text=_('The manager who made this assignment (null if self-claimed)'),
    )
    assignment_type = models.CharField(
        max_length=20,
        choices=AssignmentType.choices,
        default=AssignmentType.CLAIMED,
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )
    notes = models.TextField(blank=True, default='')
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-assigned_at']
        verbose_name = _('Application Assignment')
        verbose_name_plural = _('Application Assignments')

    def __str__(self):
        return (
            f"{self.assigned_to} \u2192 {self.application} "
            f"({self.get_status_display()})"
        )
