"""
Django REST Framework ViewSets for the Grantify grant management system.

All viewsets enforce role-based queryset filtering:

* **Applicants** see only their own applications, awards, drawdowns, reports,
  and notifications.
* **Agency staff** (program officers, fiscal officers, agency admins) see data
  belonging to their agency.
* **System administrators** see all data across agencies.

Each viewset uses ``DjangoFilterBackend``, ``SearchFilter``, and
``OrderingFilter`` (configured globally in ``settings.REST_FRAMEWORK``).
"""

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from applications.models import Application
from awards.models import Award
from core.models import Agency, AuditLog, Notification, Organization, User
from financial.models import Budget, DrawdownRequest, Transaction
from grants.models import GrantProgram
from reporting.models import Report
from reviews.models import ReviewAssignment

from .permissions import IsAdminUser, IsAgencyStaff, IsFiscalOfficer, IsGrantManager
from .serializers import (
    AgencySerializer,
    ApplicationListSerializer,
    ApplicationSerializer,
    AuditLogSerializer,
    AwardListSerializer,
    AwardSerializer,
    BudgetSerializer,
    DrawdownRequestSerializer,
    GrantProgramListSerializer,
    GrantProgramSerializer,
    NotificationSerializer,
    OrganizationSerializer,
    ReportSerializer,
    ReviewAssignmentSerializer,
    TransactionSerializer,
    UserSerializer,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _is_system_admin(user):
    """Return True if the user holds the system_admin role."""
    return user.role == User.Role.SYSTEM_ADMIN


# ---------------------------------------------------------------------------
# Grant Programs
# ---------------------------------------------------------------------------

class GrantProgramViewSet(viewsets.ModelViewSet):
    """
    ViewSet for grant programs.

    **List / Retrieve** -- available to all authenticated users.  Published
    programs are visible to everyone; unpublished (draft) programs are visible
    only to the owning agency's staff and system admins.

    **Create / Update / Delete** -- restricted to grant managers
    (system_admin, agency_admin, program_officer).
    """

    filterset_fields = ['agency', 'status', 'grant_type', 'fiscal_year', 'is_published']
    search_fields = ['title', 'description', 'agency__name', 'agency__abbreviation']
    ordering_fields = ['title', 'posting_date', 'application_deadline', 'total_funding', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return GrantProgramListSerializer
        return GrantProgramSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsGrantManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Return grant programs filtered by the requesting user's role.

        * Applicants and reviewers see only published programs.
        * Agency staff see their own agency's programs (all statuses) plus
          other agencies' published programs.
        * System admins see everything.
        """
        user = self.request.user
        qs = GrantProgram.objects.select_related('agency', 'funding_source', 'created_by')

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            # Own agency: all programs.  Other agencies: published only.
            from django.db.models import Q
            return qs.filter(
                Q(agency=user.agency) | Q(is_published=True)
            )

        # Applicants / reviewers / other roles: published only.
        return qs.filter(is_published=True)

    def perform_create(self, serializer):
        """Set the creating user and default agency from the request user."""
        serializer.save(
            created_by=self.request.user,
            agency=self.request.user.agency or serializer.validated_data.get('agency'),
        )


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class ApplicationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for grant applications.

    **Applicants** see only their own applications and may create new ones.
    **Agency staff** see applications for their agency's grant programs.
    **System admins** see all applications.
    """

    filterset_fields = ['grant_program', 'status', 'organization']
    search_fields = ['project_title', 'project_description', 'organization__name']
    ordering_fields = ['project_title', 'requested_amount', 'submitted_at', 'created_at', 'status']

    def get_serializer_class(self):
        if self.action == 'list':
            return ApplicationListSerializer
        return ApplicationSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.select_related(
            'grant_program', 'applicant', 'organization',
        )

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(grant_program__agency=user.agency)

        # Applicants see only their own applications.
        return qs.filter(applicant=user)

    def perform_create(self, serializer):
        """Automatically assign the requesting user as the applicant."""
        serializer.save(
            applicant=self.request.user,
            organization=self.request.user.organization,
        )


# ---------------------------------------------------------------------------
# Awards
# ---------------------------------------------------------------------------

class AwardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for grant awards.

    **Recipients** see their own awards.
    **Agency staff** see awards administered by their agency.
    **System admins** see all awards.
    """

    filterset_fields = ['grant_program', 'agency', 'status', 'organization']
    search_fields = ['award_number', 'title', 'organization__name']
    ordering_fields = ['award_number', 'award_amount', 'start_date', 'end_date', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return AwardListSerializer
        return AwardSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAgencyStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Award.objects.select_related(
            'grant_program', 'agency', 'recipient', 'organization', 'application',
        )

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(agency=user.agency)

        # Recipients see their own awards.
        return qs.filter(recipient=user)


# ---------------------------------------------------------------------------
# Drawdown Requests
# ---------------------------------------------------------------------------

class DrawdownRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for drawdown (cash) requests.

    **Grantees** see and create drawdown requests for their own awards.
    **Agency staff** see drawdowns for their agency's awards.
    **System admins** see all drawdowns.
    """

    filterset_fields = ['award', 'status']
    search_fields = ['request_number', 'description', 'award__award_number']
    ordering_fields = ['amount', 'period_start', 'period_end', 'created_at', 'status']

    serializer_class = DrawdownRequestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = DrawdownRequest.objects.select_related('award', 'submitted_by', 'reviewed_by')

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)

        return qs.filter(submitted_by=user)

    def perform_create(self, serializer):
        serializer.save(submitted_by=self.request.user)


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for financial transactions.

    **Read access** is available to grantees (own awards), agency staff
    (own agency), and system admins (all).

    **Create** is restricted to fiscal officers and system admins.
    Update and delete are not permitted through the API; transactions are
    effectively immutable.
    """

    filterset_fields = ['award', 'transaction_type']
    search_fields = ['reference_number', 'core_ct_reference', 'description', 'award__award_number']
    ordering_fields = ['transaction_date', 'amount', 'created_at']
    http_method_names = ['get', 'post', 'head', 'options']

    serializer_class = TransactionSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsFiscalOfficer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Transaction.objects.select_related('award', 'created_by')

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)

        return qs.filter(award__recipient=user)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

class BudgetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for award budgets.

    **Grantees** see budgets for their own awards.
    **Agency staff** see budgets for awards under their agency.
    **System admins** see all budgets.
    """

    filterset_fields = ['award', 'status', 'fiscal_year']
    search_fields = ['award__award_number']
    ordering_fields = ['fiscal_year', 'total_amount', 'created_at']

    serializer_class = BudgetSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Budget.objects.select_related('award', 'approved_by').prefetch_related('line_items')

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)

        return qs.filter(award__recipient=user)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for grantee reports.

    **Grantees** see and manage reports for their own awards.
    **Agency staff** see reports for awards under their agency.
    **System admins** see all reports.
    """

    filterset_fields = ['award', 'report_type', 'status']
    search_fields = ['award__award_number', 'report_type']
    ordering_fields = ['due_date', 'reporting_period_start', 'reporting_period_end', 'created_at']

    serializer_class = ReportSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Report.objects.select_related('award', 'template', 'submitted_by', 'reviewed_by')

        if _is_system_admin(user):
            return qs

        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)

        return qs.filter(award__recipient=user)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for external organizations.

    **Applicants** see only their own organization.
    **Agency staff** see all organizations.
    **System admins** see all organizations.
    """

    filterset_fields = ['org_type', 'is_active', 'sam_registered', 'state', 'city']
    search_fields = ['name', 'ein', 'uei_number', 'duns_number', 'city']
    ordering_fields = ['name', 'created_at']

    serializer_class = OrganizationSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAgencyStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Organization.objects.all()

        if _is_system_admin(user) or user.is_agency_staff:
            return qs

        # Applicants see only their own organization.
        if user.organization:
            return qs.filter(pk=user.organization_id)
        return qs.none()


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for in-app notifications.

    Users see only their own notifications.  Supports a custom ``mark_read``
    action to flag one or all notifications as read.
    """

    filterset_fields = ['is_read', 'priority']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'priority', 'is_read']
    http_method_names = ['get', 'patch', 'head', 'options']

    serializer_class = NotificationSerializer

    def get_queryset(self):
        """Return only the requesting user's notifications."""
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['patch'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """
        Mark a single notification as read.

        **PATCH** ``/api/notifications/{id}/mark-read/``
        """
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['patch'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark all unread notifications for the requesting user as read.

        **PATCH** ``/api/notifications/mark-all-read/``
        """
        now = timezone.now()
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=now,
        )
        return Response({'marked_read': updated}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Audit Log  (read-only, admin only)
# ---------------------------------------------------------------------------

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for the immutable audit log.

    Access is restricted to system administrators.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]
    filterset_fields = ['action', 'entity_type', 'user']
    search_fields = ['description', 'entity_type', 'entity_id']
    ordering_fields = ['timestamp', 'action', 'entity_type']

    serializer_class = AuditLogSerializer

    def get_queryset(self):
        return AuditLog.objects.select_related('user').all()
