import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FundingSource(models.Model):
    """Federal, state, or private funding source for grant programs."""

    class SourceType(models.TextChoices):
        FEDERAL = 'federal', _('Federal')
        STATE = 'state', _('State')
        PRIVATE = 'private', _('Private')
        MIXED = 'mixed', _('Mixed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        default=SourceType.STATE,
    )
    cfda_number = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text=_('Catalog of Federal Domestic Assistance number (federal sources only)'),
    )
    federal_agency = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text=_('Originating federal agency, if applicable'),
    )
    description = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Funding Source')
        verbose_name_plural = _('Funding Sources')

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class GrantProgram(models.Model):
    """A funding opportunity posted by a state agency."""

    class GrantType(models.TextChoices):
        COMPETITIVE = 'competitive', _('Competitive')
        NON_COMPETITIVE = 'non_competitive', _('Non-Competitive')
        FORMULA = 'formula', _('Formula')
        CONTINUATION = 'continuation', _('Continuation')
        OTHER = 'other', _('Other')

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        POSTED = 'posted', _('Posted')
        ACCEPTING_APPLICATIONS = 'accepting_applications', _('Accepting Applications')
        UNDER_REVIEW = 'under_review', _('Under Review')
        AWARDS_PENDING = 'awards_pending', _('Awards Pending')
        CLOSED = 'closed', _('Closed')
        CANCELLED = 'cancelled', _('Cancelled')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        'core.Agency',
        on_delete=models.PROTECT,
        related_name='grant_programs',
    )
    title = models.CharField(max_length=500)
    description = models.TextField()
    funding_source = models.ForeignKey(
        FundingSource,
        on_delete=models.PROTECT,
        related_name='grant_programs',
    )
    grant_type = models.CharField(
        max_length=20,
        choices=GrantType.choices,
        default=GrantType.COMPETITIVE,
    )
    eligibility_criteria = models.TextField(
        blank=True,
        default='',
        help_text=_('Description of who may apply'),
    )

    # Funding details
    total_funding = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_('Total funding available for this program'),
    )
    min_award = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_('Minimum award amount'),
    )
    max_award = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        help_text=_('Maximum award amount'),
    )

    # Match requirements
    match_required = models.BooleanField(
        default=False,
        help_text=_('Whether a matching contribution is required'),
    )
    match_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Required match as a percentage (e.g. 25.00 for 25%)'),
    )

    # Timeline
    fiscal_year = models.CharField(max_length=9, help_text=_('e.g. 2025-2026'))
    multi_year = models.BooleanField(
        default=False,
        help_text=_('Whether awards span multiple fiscal years'),
    )
    duration_months = models.IntegerField(help_text=_('Grant period duration in months'))
    application_deadline = models.DateTimeField(db_index=True)
    posting_date = models.DateTimeField()

    # Status and publishing
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Contact information
    contact_name = models.CharField(max_length=255, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=30, blank=True, default='')

    # Configurable application form structure
    application_form_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('JSON configuration defining custom application form sections and fields per program'),
    )

    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_grant_programs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-posting_date']
        verbose_name = _('Grant Program')
        verbose_name_plural = _('Grant Programs')

    def __str__(self):
        return self.title

    @property
    def is_accepting_applications(self):
        """Return True if the program is currently accepting applications."""
        return (
            self.status == self.Status.ACCEPTING_APPLICATIONS
            and self.application_deadline > timezone.now()
        )

    @property
    def days_until_deadline(self):
        """Return the number of days until the application deadline, or None if past."""
        if self.application_deadline <= timezone.now():
            return None
        delta = self.application_deadline - timezone.now()
        return delta.days

    @property
    def applications_count(self):
        """Return the total number of applications for this program."""
        return self.applications.count()


class GrantProgramDocument(models.Model):
    """Supporting documents attached to a grant program."""

    class DocumentType(models.TextChoices):
        NOFA = 'nofa', _('Notice of Funding Availability')
        GUIDELINES = 'guidelines', _('Program Guidelines')
        BUDGET_TEMPLATE = 'budget_template', _('Budget Template')
        APPLICATION_FORM = 'application_form', _('Application Form')
        FAQ = 'faq', _('FAQ')
        AMENDMENT = 'amendment', _('Amendment')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant_program = models.ForeignKey(
        GrantProgram,
        on_delete=models.CASCADE,
        related_name='documents',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    file = models.FileField(upload_to='grant_programs/docs/')
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_grant_documents',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', 'title']
        verbose_name = _('Grant Program Document')
        verbose_name_plural = _('Grant Program Documents')

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"


# ---------------------------------------------------------------------------
# FederalOpportunity  (cached from Grants.gov API)
# ---------------------------------------------------------------------------
class FederalOpportunity(models.Model):
    """Federal grant opportunity cached from the Simpler Grants.gov API."""

    class OpportunityStatus(models.TextChoices):
        POSTED = 'posted', _('Posted')
        CLOSED = 'closed', _('Closed')
        ARCHIVED = 'archived', _('Archived')
        FORECASTED = 'forecasted', _('Forecasted')

    class FundingInstrument(models.TextChoices):
        GRANT = 'grant', _('Grant')
        COOPERATIVE_AGREEMENT = 'cooperative_agreement', _('Cooperative Agreement')
        PROCUREMENT_CONTRACT = 'procurement_contract', _('Procurement Contract')
        OTHER = 'other', _('Other')

    id = models.AutoField(primary_key=True)

    # Identifiers (from Grants.gov)
    opportunity_id = models.CharField(
        max_length=64,
        unique=True,
        help_text=_('Unique identifier from Grants.gov'),
    )
    opportunity_number = models.CharField(
        max_length=255, blank=True, default='',
        help_text=_('Opportunity number / NOFO number'),
    )

    # Core information
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True, default='')
    agency_name = models.CharField(max_length=255, blank=True, default='')
    agency_code = models.CharField(max_length=50, blank=True, default='')

    # Classification
    category = models.CharField(
        max_length=255, blank=True, default='',
        help_text=_('Funding category / opportunity category'),
    )
    funding_instrument = models.CharField(
        max_length=30,
        choices=FundingInstrument.choices,
        default=FundingInstrument.GRANT,
    )
    cfda_numbers = models.JSONField(
        default=list, blank=True,
        help_text=_('List of CFDA/Assistance Listing numbers'),
    )

    # Funding
    award_floor = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_('Minimum award amount'),
    )
    award_ceiling = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_('Maximum award amount'),
    )
    expected_awards = models.IntegerField(
        null=True, blank=True,
        help_text=_('Expected number of awards'),
    )
    total_funding = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_('Total estimated funding'),
    )

    # Dates
    post_date = models.DateField(null=True, blank=True)
    close_date = models.DateField(null=True, blank=True)
    archive_date = models.DateField(null=True, blank=True)

    # Status
    opportunity_status = models.CharField(
        max_length=15,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.POSTED,
    )

    # Eligibility
    applicant_types = models.JSONField(
        default=list, blank=True,
        help_text=_('List of eligible applicant types'),
    )
    eligible_applicants = models.TextField(
        blank=True, default='',
        help_text=_('Additional eligibility text'),
    )

    # External link
    grants_gov_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text=_('Link to the opportunity on Grants.gov'),
    )

    # Internal link to Beacon FundingSource (populated when staff creates
    # a GrantProgram from this opportunity)
    funding_source = models.ForeignKey(
        FundingSource,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='federal_opportunities',
        help_text=_('Linked FundingSource when a GrantProgram is created from this opportunity'),
    )

    # Sync metadata
    synced_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('When this record was last synced from Grants.gov'),
    )
    raw_data = models.JSONField(
        default=dict, blank=True,
        help_text=_('Full API response for this opportunity'),
    )

    class Meta:
        ordering = ['-post_date', '-close_date']
        verbose_name = _('Federal Opportunity')
        verbose_name_plural = _('Federal Opportunities')
        indexes = [
            models.Index(fields=['opportunity_status', 'close_date'], name='idx_fedopp_status_close'),
            models.Index(fields=['agency_code'], name='idx_fedopp_agency'),
        ]

    def __str__(self):
        return f"{self.opportunity_number or self.opportunity_id} — {self.title[:80]}"

    @property
    def is_open(self):
        """Return True if the opportunity is currently accepting applications."""
        if self.opportunity_status != self.OpportunityStatus.POSTED:
            return False
        if self.close_date and self.close_date < timezone.now().date():
            return False
        return True

    @property
    def days_until_close(self):
        """Return the number of days until close, or None if past/no date."""
        if not self.close_date:
            return None
        delta = self.close_date - timezone.now().date()
        return delta.days if delta.days >= 0 else None

    @property
    def funding_range_display(self):
        """Human-friendly funding range string."""
        if self.award_floor and self.award_ceiling:
            return f"${self.award_floor:,.0f} – ${self.award_ceiling:,.0f}"
        if self.award_ceiling:
            return f"Up to ${self.award_ceiling:,.0f}"
        if self.award_floor:
            return f"From ${self.award_floor:,.0f}"
        return "Not specified"


# ---------------------------------------------------------------------------
# TrackedOpportunity  (Federal Coordinator's pipeline management)
# ---------------------------------------------------------------------------
class TrackedOpportunity(models.Model):
    """A federal opportunity being actively tracked by the Federal Fund Coordinator."""

    class TrackingStatus(models.TextChoices):
        WATCHING = 'watching', _('Watching')
        PREPARING = 'preparing', _('Preparing Application')
        APPLIED = 'applied', _('Applied')
        AWARDED = 'awarded', _('Awarded')
        DECLINED = 'declined', _('Declined')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    federal_opportunity = models.ForeignKey(
        FederalOpportunity,
        on_delete=models.CASCADE,
        related_name='tracked_records',
    )
    tracked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tracked_opportunities',
    )
    status = models.CharField(
        max_length=15,
        choices=TrackingStatus.choices,
        default=TrackingStatus.WATCHING,
    )
    notes = models.TextField(blank=True, default='')
    priority = models.CharField(
        max_length=10,
        choices=[('low', _('Low')), ('medium', _('Medium')), ('high', _('High'))],
        default='medium',
    )

    # Link to internal GrantProgram when created from this opportunity
    grant_program = models.ForeignKey(
        GrantProgram,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tracked_federal_opportunities',
        help_text=_('Internal Grant Program linked to this federal opportunity'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = _('Tracked Opportunity')
        verbose_name_plural = _('Tracked Opportunities')
        unique_together = ['federal_opportunity', 'tracked_by']

    def __str__(self):
        return f"[{self.get_status_display()}] {self.federal_opportunity.title[:60]}"


# ---------------------------------------------------------------------------
# OpportunityCollaborator  (invite internal/external people to collaborate)
# ---------------------------------------------------------------------------
class OpportunityCollaborator(models.Model):
    """A collaborator invited to work on a tracked federal opportunity."""

    class CollaboratorRole(models.TextChoices):
        LEAD = 'lead', _('Lead')
        CONTRIBUTOR = 'contributor', _('Contributor')
        REVIEWER = 'reviewer', _('Reviewer')
        OBSERVER = 'observer', _('Observer')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tracked_opportunity = models.ForeignKey(
        TrackedOpportunity,
        on_delete=models.CASCADE,
        related_name='collaborators',
    )

    # Internal user (if they have an account)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='federal_collaborations',
        help_text=_('Internal Beacon user'),
    )

    # External collaborator (if not in the system)
    email = models.EmailField(
        blank=True, default='',
        help_text=_('Email for external collaborators not yet in Beacon'),
    )
    name = models.CharField(
        max_length=255, blank=True, default='',
        help_text=_('Name for external collaborators'),
    )

    role = models.CharField(
        max_length=15,
        choices=CollaboratorRole.choices,
        default=CollaboratorRole.CONTRIBUTOR,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='federal_invitations_sent',
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['role', '-invited_at']
        verbose_name = _('Opportunity Collaborator')
        verbose_name_plural = _('Opportunity Collaborators')

    def __str__(self):
        display = str(self.user) if self.user else self.email or self.name
        return f"{display} ({self.get_role_display()})"

    @property
    def display_name(self):
        """Return the best name to show for this collaborator."""
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.name or self.email


class SavedProgram(models.Model):
    """A grant program bookmarked/saved by an applicant for future reference.

    Allows users to track programs of interest without starting an
    application.  Follows the same pattern as TrackedOpportunity.
    """

    class InterestLevel(models.TextChoices):
        WATCHING = 'watching', _('Watching')
        INTERESTED = 'interested', _('Interested')
        PLANNING_TO_APPLY = 'planning_to_apply', _('Planning to Apply')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant_program = models.ForeignKey(
        'GrantProgram',
        on_delete=models.CASCADE,
        related_name='saved_by_users',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_programs',
    )
    interest_level = models.CharField(
        max_length=20,
        choices=InterestLevel.choices,
        default=InterestLevel.WATCHING,
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Saved Program')
        verbose_name_plural = _('Saved Programs')
        unique_together = ['grant_program', 'user']

    def __str__(self):
        return f"[{self.get_interest_level_display()}] {self.grant_program.title[:60]}"


# ---------------------------------------------------------------------------
# GrantPreference  (AI matching preferences — Applicants & Fed Coordinators)
# ---------------------------------------------------------------------------
class GrantPreference(models.Model):
    """User preferences for AI-powered grant matching.

    Stores structured fields and free-text descriptions that the AI scoring
    service uses to evaluate relevance of new opportunities.  Works for both
    Applicants and Federal Fund Coordinators.
    """

    class FocusArea(models.TextChoices):
        EDUCATION = 'education', _('Education')
        HEALTH = 'health', _('Health & Human Services')
        ENVIRONMENT = 'environment', _('Environment & Energy')
        INFRASTRUCTURE = 'infrastructure', _('Infrastructure & Transportation')
        PUBLIC_SAFETY = 'public_safety', _('Public Safety')
        HOUSING = 'housing', _('Housing & Community Development')
        ECONOMIC_DEV = 'economic_dev', _('Economic Development')
        ARTS_CULTURE = 'arts_culture', _('Arts & Culture')
        TECHNOLOGY = 'technology', _('Technology & Innovation')
        AGRICULTURE = 'agriculture', _('Agriculture & Food')
        WORKFORCE = 'workforce', _('Workforce Development')
        JUSTICE = 'justice', _('Justice & Legal Services')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='grant_preference',
    )

    # Structured preferences
    focus_areas = models.JSONField(
        default=list, blank=True,
        help_text=_('List of focus area keys from FocusArea choices'),
    )
    eligible_org_types = models.JSONField(
        default=list, blank=True,
        help_text=_('List of organization type keys the user is interested in'),
    )
    funding_range_min = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_('Minimum funding amount of interest'),
    )
    funding_range_max = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text=_('Maximum funding amount of interest'),
    )

    # Free-text description for AI context
    description = models.TextField(
        blank=True, default='',
        help_text=_('Describe your priorities, mission, or what you are looking for in your own words'),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_('Whether AI matching is enabled for this user'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Grant Preference')
        verbose_name_plural = _('Grant Preferences')

    def __str__(self):
        return f"Preferences for {self.user}"


# ---------------------------------------------------------------------------
# OpportunityMatch  (AI-scored match between user and opportunity)
# ---------------------------------------------------------------------------
class OpportunityMatch(models.Model):
    """AI-scored match linking a user to a relevant opportunity.

    Matches may point to a FederalOpportunity (source=federal) or a
    GrantProgram (source=state).  UniqueConstraints prevent duplicate matches.
    """

    class Source(models.TextChoices):
        FEDERAL = 'federal', _('Federal')
        STATE = 'state', _('State')

    class Status(models.TextChoices):
        NEW = 'new', _('New')
        VIEWED = 'viewed', _('Viewed')
        SAVED = 'saved', _('Saved')
        DISMISSED = 'dismissed', _('Dismissed')

    class Feedback(models.TextChoices):
        POSITIVE = 'positive', _('Positive')
        NEGATIVE = 'negative', _('Negative')

    class FeedbackReason(models.TextChoices):
        WRONG_FOCUS = 'wrong_focus', _('Wrong focus area')
        BUDGET_TOO_LARGE = 'budget_too_large', _('Budget too large')
        BUDGET_TOO_SMALL = 'budget_too_small', _('Budget too small')
        ALREADY_AWARE = 'already_aware', _('Already aware of this')
        NOT_ELIGIBLE = 'not_eligible', _('Not eligible')
        NOT_RELEVANT = 'not_relevant', _('Not relevant to our mission')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='opportunity_matches',
    )
    source = models.CharField(
        max_length=10,
        choices=Source.choices,
    )

    # Nullable FKs — exactly one should be set per match
    federal_opportunity = models.ForeignKey(
        FederalOpportunity,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='matches',
    )
    grant_program = models.ForeignKey(
        GrantProgram,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='matches',
    )

    relevance_score = models.IntegerField(
        help_text=_('AI relevance score from 0 to 100'),
    )
    explanation = models.TextField(
        blank=True, default='',
        help_text=_('AI-generated explanation of why this is a match'),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
    )
    notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)

    feedback = models.CharField(
        max_length=10,
        choices=Feedback.choices,
        blank=True,
        default='',
        help_text=_('User feedback on this recommendation'),
    )
    feedback_reason = models.CharField(
        max_length=20,
        choices=FeedbackReason.choices,
        blank=True,
        default='',
        help_text=_('Reason for negative feedback'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-relevance_score', '-created_at']
        verbose_name = _('Opportunity Match')
        verbose_name_plural = _('Opportunity Matches')
        indexes = [
            models.Index(
                fields=['user', 'status'],
                name='idx_oppmatch_user_status',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'federal_opportunity'],
                condition=models.Q(federal_opportunity__isnull=False),
                name='unique_user_federal_match',
            ),
            models.UniqueConstraint(
                fields=['user', 'grant_program'],
                condition=models.Q(grant_program__isnull=False),
                name='unique_user_state_match',
            ),
        ]

    def __str__(self):
        title = self.opportunity_title
        return f"{self.user} — {title[:50]} ({self.relevance_score}%)"

    @property
    def opportunity_title(self):
        """Return the title of the matched opportunity."""
        if self.federal_opportunity:
            return self.federal_opportunity.title
        if self.grant_program:
            return self.grant_program.title
        return _('Unknown')

    @property
    def opportunity_url(self):
        """Return the best URL for the matched opportunity."""
        if self.federal_opportunity:
            from django.urls import reverse
            return reverse(
                'portal:federal-opportunity-detail',
                kwargs={'pk': self.federal_opportunity.pk},
            )
        if self.grant_program:
            from django.urls import reverse
            return reverse(
                'portal:opportunity-detail',
                kwargs={'pk': self.grant_program.pk},
            )
        return ''
