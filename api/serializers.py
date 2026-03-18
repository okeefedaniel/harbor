"""
Django REST Framework serializers for the Beacon grant management system.

Each model that is exposed through the API has a full serializer and, where
appropriate, a lightweight "list" serializer that omits heavy nested data to
keep list endpoints fast.
"""

from rest_framework import serializers

from applications.models import Application
from awards.models import Award
from core.models import Agency, AuditLog, Notification, Organization, User
from financial.models import Budget, BudgetLineItem, DrawdownRequest, Transaction
from grants.models import GrantProgram
from reporting.models import Report
from reviews.models import ReviewAssignment, ReviewScore


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for external organizations that apply for grants."""

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'org_type',
            'duns_number', 'uei_number', 'ein',
            'sam_registered', 'sam_expiration',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code',
            'phone', 'website',
            'is_active', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AgencySerializer(serializers.ModelSerializer):
    """Serializer for state agencies."""

    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'abbreviation', 'description',
            'department_code', 'fund_code', 'program_code',
            'contact_name', 'contact_email', 'contact_phone',
            'address', 'website',
            'can_be_grantee', 'can_be_grantor',
            'is_active', 'onboarded_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for User accounts.

    The password field and other security-sensitive fields are excluded.
    """

    agency_name = serializers.CharField(source='agency.name', read_only=True, default=None)
    organization_name = serializers.CharField(
        source='organization.name', read_only=True, default=None,
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'title', 'phone',
            'agency', 'agency_name',
            'organization', 'organization_name',
            'is_state_user', 'is_active',
            'date_joined', 'last_login',
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for in-app notifications."""

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'title', 'message', 'priority',
            'link', 'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = [
            'id', 'recipient', 'title', 'message', 'priority',
            'link', 'created_at',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the immutable audit log.

    Only system administrators may access this data.
    """

    user_display = serializers.CharField(source='user.__str__', read_only=True, default='System')

    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_display', 'action',
            'entity_type', 'entity_id', 'description',
            'changes', 'ip_address', 'timestamp',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Grants
# ---------------------------------------------------------------------------

class GrantProgramSerializer(serializers.ModelSerializer):
    """Full serializer for grant programs, including all detail fields."""

    agency_name = serializers.CharField(source='agency.name', read_only=True)
    agency_abbreviation = serializers.CharField(source='agency.abbreviation', read_only=True)
    created_by_name = serializers.CharField(source='created_by.__str__', read_only=True)
    applications_count = serializers.IntegerField(read_only=True)
    is_accepting_applications = serializers.BooleanField(read_only=True)
    days_until_deadline = serializers.IntegerField(read_only=True)

    class Meta:
        model = GrantProgram
        fields = [
            'id', 'agency', 'agency_name', 'agency_abbreviation',
            'title', 'description',
            'funding_source', 'grant_type', 'eligibility_criteria',
            'total_funding', 'min_award', 'max_award',
            'match_required', 'match_percentage',
            'fiscal_year', 'multi_year', 'duration_months',
            'application_deadline', 'posting_date',
            'status', 'is_published', 'published_at',
            'contact_name', 'contact_email', 'contact_phone',
            'created_by', 'created_by_name',
            'applications_count', 'is_accepting_applications', 'days_until_deadline',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_name',
            'applications_count', 'is_accepting_applications', 'days_until_deadline',
            'created_at', 'updated_at',
        ]


class GrantProgramListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for grant program list views.

    Omits heavy text fields to reduce payload size.
    """

    agency_abbreviation = serializers.CharField(source='agency.abbreviation', read_only=True)
    is_accepting_applications = serializers.BooleanField(read_only=True)

    class Meta:
        model = GrantProgram
        fields = [
            'id', 'title', 'agency', 'agency_abbreviation',
            'grant_type', 'status',
            'total_funding', 'min_award', 'max_award',
            'application_deadline', 'posting_date',
            'is_published', 'is_accepting_applications',
        ]
        read_only_fields = ['id']


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class ApplicationSerializer(serializers.ModelSerializer):
    """Full serializer for grant applications."""

    applicant_name = serializers.CharField(source='applicant.__str__', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    grant_program_title = serializers.CharField(source='grant_program.title', read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'grant_program', 'grant_program_title',
            'applicant', 'applicant_name',
            'organization', 'organization_name',
            'status', 'submitted_at',
            'project_title', 'project_description',
            'requested_amount',
            'proposed_start_date', 'proposed_end_date',
            'match_amount', 'match_description',
            'is_editable',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'applicant', 'applicant_name',
            'organization_name', 'grant_program_title',
            'status', 'submitted_at', 'is_editable',
            'created_at', 'updated_at',
        ]


class ApplicationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for application list views."""

    applicant_name = serializers.CharField(source='applicant.__str__', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    grant_program_title = serializers.CharField(source='grant_program.title', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'grant_program', 'grant_program_title',
            'applicant', 'applicant_name',
            'organization', 'organization_name',
            'status', 'project_title', 'requested_amount',
            'submitted_at', 'created_at',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Awards
# ---------------------------------------------------------------------------

class AwardSerializer(serializers.ModelSerializer):
    """Full serializer for grant awards."""

    grant_program_title = serializers.CharField(source='grant_program.title', read_only=True)
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    recipient_name = serializers.CharField(source='recipient.__str__', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = Award
        fields = [
            'id', 'application',
            'grant_program', 'grant_program_title',
            'agency', 'agency_name',
            'recipient', 'recipient_name',
            'organization', 'organization_name',
            'award_number', 'title', 'status',
            'award_amount', 'award_date', 'start_date', 'end_date',
            'terms_and_conditions', 'special_conditions',
            'requires_match', 'match_amount',
            'approved_by', 'approved_at', 'executed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'grant_program_title', 'agency_name',
            'recipient_name', 'organization_name',
            'created_at', 'updated_at',
        ]


class AwardListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for award list views."""

    grant_program_title = serializers.CharField(source='grant_program.title', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    recipient_name = serializers.CharField(source='recipient.__str__', read_only=True)

    class Meta:
        model = Award
        fields = [
            'id', 'award_number', 'title', 'status',
            'grant_program', 'grant_program_title',
            'organization', 'organization_name',
            'recipient', 'recipient_name',
            'award_amount', 'start_date', 'end_date',
            'created_at',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------

class DrawdownRequestSerializer(serializers.ModelSerializer):
    """Serializer for drawdown (cash) requests against an award."""

    award_number = serializers.CharField(source='award.award_number', read_only=True)
    submitted_by_name = serializers.CharField(source='submitted_by.__str__', read_only=True)

    class Meta:
        model = DrawdownRequest
        fields = [
            'id', 'award', 'award_number',
            'request_number', 'amount',
            'period_start', 'period_end',
            'status', 'description', 'expenditure_details',
            'submitted_by', 'submitted_by_name', 'submitted_at',
            'reviewed_by', 'reviewed_at',
            'paid_at', 'payment_reference',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'award_number', 'submitted_by_name',
            'submitted_by', 'submitted_at',
            'reviewed_by', 'reviewed_at',
            'paid_at', 'payment_reference',
            'created_at', 'updated_at',
        ]


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for financial transaction records."""

    award_number = serializers.CharField(source='award.award_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.__str__', read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            'id', 'award', 'award_number',
            'transaction_type', 'amount', 'description',
            'reference_number', 'core_ct_reference',
            'transaction_date',
            'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = [
            'id', 'award_number', 'created_by', 'created_by_name', 'created_at',
        ]


class BudgetLineItemSerializer(serializers.ModelSerializer):
    """Inline serializer for budget line items."""

    class Meta:
        model = BudgetLineItem
        fields = [
            'id', 'category', 'description', 'amount',
            'federal_share', 'state_share', 'match_share', 'notes',
        ]
        read_only_fields = ['id']


class BudgetSerializer(serializers.ModelSerializer):
    """Serializer for award budgets, including nested line items."""

    award_number = serializers.CharField(source='award.award_number', read_only=True)
    line_items = BudgetLineItemSerializer(many=True, read_only=True)

    class Meta:
        model = Budget
        fields = [
            'id', 'award', 'award_number',
            'fiscal_year', 'total_amount', 'status',
            'submitted_at',
            'approved_by', 'approved_at',
            'line_items',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'award_number',
            'approved_by', 'approved_at',
            'created_at', 'updated_at',
        ]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

class ReportSerializer(serializers.ModelSerializer):
    """Serializer for grantee reports."""

    award_number = serializers.CharField(source='award.award_number', read_only=True)
    submitted_by_name = serializers.CharField(
        source='submitted_by.__str__', read_only=True, default=None,
    )
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'award', 'award_number',
            'template', 'report_type',
            'reporting_period_start', 'reporting_period_end',
            'status', 'data',
            'submitted_by', 'submitted_by_name', 'submitted_at',
            'reviewed_by', 'reviewed_at', 'reviewer_comments',
            'due_date', 'is_overdue',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'award_number', 'submitted_by_name',
            'submitted_by', 'submitted_at',
            'reviewed_by', 'reviewed_at',
            'is_overdue',
            'created_at', 'updated_at',
        ]


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

class ReviewScoreInlineSerializer(serializers.ModelSerializer):
    """Inline serializer for scores within a review assignment."""

    criterion_name = serializers.CharField(source='criterion.name', read_only=True)

    class Meta:
        model = ReviewScore
        fields = ['id', 'criterion', 'criterion_name', 'score', 'comment']
        read_only_fields = ['id']


class ReviewAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for review assignments including inline scores."""

    reviewer_name = serializers.CharField(source='reviewer.__str__', read_only=True)
    application_title = serializers.CharField(
        source='application.project_title', read_only=True,
    )
    scores = ReviewScoreInlineSerializer(many=True, read_only=True)

    class Meta:
        model = ReviewAssignment
        fields = [
            'id', 'application', 'application_title',
            'reviewer', 'reviewer_name',
            'rubric', 'status',
            'assigned_at', 'completed_at',
            'conflict_of_interest', 'conflict_notes',
            'scores',
        ]
        read_only_fields = [
            'id', 'application_title', 'reviewer_name',
            'assigned_at', 'scores',
        ]
