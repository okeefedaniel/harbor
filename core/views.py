from collections import OrderedDict

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from datetime import timedelta
from django.db.models import Avg, Count, Sum, Q
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from applications.models import Application
from awards.models import Award
from core.forms import (
    ClaimReviewForm, OrganizationContactForm, OrganizationForm,
    ProfileForm, RegistrationForm, UserRoleForm,
)
from core.mixins import SortableListMixin, SystemAdminRequiredMixin
from core.models import (
    Agency, AGENCY_STAFF_ROLES, GRANT_MANAGER_ROLES, Notification,
    Organization, OrganizationClaim, OrganizationContact, users_with_roles,
)
from core.utils import rate_limit, safe_redirect_url

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterView(CreateView):
    """Public registration for external (applicant) users."""

    form_class = RegistrationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('core:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _('Your account has been created. Please log in.'),
        )
        # Notify system admins about the new registration
        from core.notifications import notify_new_user_registered
        notify_new_user_registered(self.object)
        return response


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileView(LoginRequiredMixin, UpdateView):
    """Allow an authenticated user to edit their own profile."""

    form_class = ProfileForm
    template_name = 'core/profile.html'
    success_url = reverse_lazy('core:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Profile updated successfully.'))
        return response


# ---------------------------------------------------------------------------
# Organization management (applicants)
# ---------------------------------------------------------------------------
class OrganizationCreateView(LoginRequiredMixin, CreateView):
    """Allow an applicant to create their organization profile."""

    form_class = OrganizationForm
    template_name = 'core/organization_form.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from core.models import get_harbor_profile
            if get_harbor_profile(request.user).organization_id:
                messages.info(
                    request,
                    _('You already have an organization. You can edit it below.'),
                )
                return redirect('core:organization-edit')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        from core.models import get_harbor_profile
        profile = get_harbor_profile(self.request.user)
        profile.organization = self.object
        profile.save(update_fields=['organization'])
        messages.success(self.request, _('Organization created successfully.'))
        return response

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        return safe_redirect_url(self.request, next_url, fallback=reverse_lazy('core:profile'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = False
        context['next_url'] = self.request.GET.get('next', '')
        return context


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    """Allow an applicant to edit their organization profile."""

    form_class = OrganizationForm
    template_name = 'core/organization_form.html'
    success_url = reverse_lazy('core:profile')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            from core.models import get_harbor_profile
            if not get_harbor_profile(request.user).organization_id:
                messages.warning(request, _('Please create your organization first.'))
                return redirect('core:organization-create')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        from core.models import get_harbor_profile
        return get_harbor_profile(self.request.user).organization

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Organization updated successfully.'))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_edit'] = True
        return context


# ---------------------------------------------------------------------------
# User Management (System Admin only)
# ---------------------------------------------------------------------------
class UserListView(LoginRequiredMixin, SortableListMixin, ListView):
    """List all users for system administrators to manage roles."""

    model = User
    template_name = 'core/user_list.html'
    context_object_name = 'users'
    paginate_by = 25

    sortable_fields = {
        'name': 'last_name',
        'username': 'username',
        'role': 'role',
        'agency': 'agency__abbreviation',
        'is_active': 'is_active',
        'last_login': 'last_login',
    }
    default_sort = 'name'
    default_dir = 'asc'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'system_admin':
            messages.error(request, _('Access denied. System administrators only.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = User.objects.all()
        # Search/filter
        search = self.request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )
        role_filter = self.request.GET.get('role', '')
        if role_filter:
            from keel.accounts.models import ProductAccess
            user_ids = ProductAccess.objects.filter(
                product='harbor', role=role_filter, is_active=True,
            ).values_list('user_id', flat=True)
            qs = qs.filter(pk__in=user_ids)
        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.forms import UserRoleForm
        context['roles'] = UserRoleForm.ROLE_CHOICES
        context['current_role'] = self.request.GET.get('role', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class UserRoleUpdateView(LoginRequiredMixin, UpdateView):
    """Allow system admins to update a user's role and agency assignment."""

    model = User
    form_class = UserRoleForm
    template_name = 'core/user_role_edit.html'
    context_object_name = 'edit_user'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request.user, 'role', '') != 'system_admin':
            messages.error(request, _('Access denied. System administrators only.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse_lazy('core:user-list')

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        messages.success(
            self.request,
            _('User "%(username)s" updated to %(role)s.') % {
                'username': user.username,
                'role': getattr(user, 'role', 'applicant'),
            },
        )
        return response


# ---------------------------------------------------------------------------
# Organization Claims
# ---------------------------------------------------------------------------
class OrganizationClaimView(LoginRequiredMixin, View):
    """Allow an authenticated user to claim an organization."""

    def post(self, request, pk):
        org = get_object_or_404(Organization, pk=pk, is_active=True)

        # Check for existing pending claim
        existing = OrganizationClaim.objects.filter(
            organization=org, user=request.user, status=OrganizationClaim.Status.PENDING,
        ).exists()
        if existing:
            messages.info(request, _('You already have a pending claim for this organization.'))
            return redirect('dashboard')

        OrganizationClaim.objects.create(organization=org, user=request.user)
        messages.success(
            request,
            _('Your claim for "%(org)s" has been submitted for review.') % {'org': org.name},
        )

        # Notify Program Officers
        from core.notifications import notify_organization_claim_submitted
        notify_organization_claim_submitted(org, request.user)

        return redirect('dashboard')

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk, is_active=True)
        existing = OrganizationClaim.objects.filter(
            organization=org, user=request.user, status=OrganizationClaim.Status.PENDING,
        ).exists()
        return redirect('dashboard') if existing else self._render(request, org)

    def _render(self, request, org):
        from django.shortcuts import render
        return render(request, 'core/organization_claim.html', {'organization': org})


class OrganizationClaimListView(LoginRequiredMixin, ListView):
    """List pending organization claims for Program Officers to review."""

    model = OrganizationClaim
    template_name = 'core/organization_claim_list.html'
    context_object_name = 'claims'
    paginate_by = 25

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request.user, 'role', '') not in GRANT_MANAGER_ROLES:
            messages.error(request, _('Access denied.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = OrganizationClaim.objects.select_related('organization', 'user', 'reviewed_by')
        status_filter = self.request.GET.get('status', 'pending')
        if status_filter and status_filter in dict(OrganizationClaim.Status.choices):
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', 'pending')
        context['statuses'] = OrganizationClaim.Status.choices
        context['pending_count'] = OrganizationClaim.objects.filter(
            status=OrganizationClaim.Status.PENDING,
        ).count()
        return context


class OrganizationClaimReviewView(LoginRequiredMixin, View):
    """Allow Program Officers to approve or deny an organization claim."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request.user, 'role', '') not in GRANT_MANAGER_ROLES:
            messages.error(request, _('Access denied.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        claim = get_object_or_404(
            OrganizationClaim.objects.select_related('organization', 'user'),
            pk=pk,
        )
        form = ClaimReviewForm()
        return self._render(request, claim, form)

    def post(self, request, pk):
        claim = get_object_or_404(
            OrganizationClaim.objects.select_related('organization', 'user'),
            pk=pk,
        )
        if claim.status != OrganizationClaim.Status.PENDING:
            messages.info(request, _('This claim has already been reviewed.'))
            return redirect('core:organization-claims')

        form = ClaimReviewForm(request.POST)
        if not form.is_valid():
            return self._render(request, claim, form)

        action = form.cleaned_data['action']
        claim.reviewed_by = request.user
        claim.reviewed_at = timezone.now()
        claim.reviewer_notes = form.cleaned_data.get('reviewer_notes', '')

        if action == 'approve':
            claim.status = OrganizationClaim.Status.APPROVED
            # Link the user to the organization via HarborProfile
            from core.models import get_harbor_profile
            profile = get_harbor_profile(claim.user)
            if not profile.organization_id:
                profile.organization = claim.organization
                profile.save(update_fields=['organization'])
            messages.success(
                request,
                _('Claim approved. %(user)s is now linked to %(org)s.') % {
                    'user': claim.user.get_full_name() or claim.user.username,
                    'org': claim.organization.name,
                },
            )
        else:
            claim.status = OrganizationClaim.Status.DENIED
            messages.warning(request, _('Claim denied.'))

        claim.save()

        # Notify the claimant
        from core.notifications import notify_organization_claim_reviewed
        notify_organization_claim_reviewed(claim)

        return redirect('core:organization-claims')

    def _render(self, request, claim, form):
        from django.shortcuts import render
        return render(request, 'core/organization_claim_review.html', {
            'claim': claim,
            'form': form,
        })


class OrganizationContactAssignView(LoginRequiredMixin, View):
    """Assign a staff contact to an organization."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or getattr(request.user, 'role', '') not in GRANT_MANAGER_ROLES:
            messages.error(request, _('Access denied.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        existing = OrganizationContact.objects.filter(organization=org).first()
        form = OrganizationContactForm(instance=existing)
        return self._render(request, org, form, existing)

    def post(self, request, pk):
        org = get_object_or_404(Organization, pk=pk)
        existing = OrganizationContact.objects.filter(organization=org).first()
        form = OrganizationContactForm(request.POST, instance=existing)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.organization = org
            contact.assigned_by = request.user
            contact.save()
            messages.success(
                request,
                _('%(user)s assigned as contact for %(org)s.') % {
                    'user': contact.assigned_to.get_full_name() or contact.assigned_to.username,
                    'org': org.name,
                },
            )
            return redirect('core:organization-claims')
        return self._render(request, org, form, existing)

    def _render(self, request, org, form, existing):
        from django.shortcuts import render
        return render(request, 'core/organization_contact_assign.html', {
            'organization': org,
            'form': form,
            'existing_contact': existing,
        })


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard.

    Context varies by user role:
    * Agency staff (agency_admin, program_officer, fiscal_officer, system_admin):
      - applications pending review
      - active awards for the user's agency
      - total funding across active awards
    * Applicants:
      - their own applications
      - their own awards
    * Reviewers / Auditors:
      - applications assigned or pending review
    """

    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        role = getattr(user, 'role', '') or ''
        if role == 'federal_coordinator':
            context.update(self._federal_coordinator_context(user))
        elif role in AGENCY_STAFF_ROLES:
            context.update(self._agency_context(user))
        elif role == 'applicant' or not role:
            context.update(self._applicant_context(user))
        elif role in ('reviewer', 'auditor'):
            context.update(self._reviewer_context(user))

        return context

    # -- private helpers ----------------------------------------------------

    @staticmethod
    def _agency_context(user):
        """Build dashboard context for agency-level staff."""
        agency_filter = Q()
        if user.agency_id:
            agency_filter = Q(grant_program__agency=user.agency)

        pending_applications = (
            Application.objects
            .filter(agency_filter)
            .filter(status__in=[
                Application.Status.SUBMITTED,
                Application.Status.UNDER_REVIEW,
            ])
            .select_related('grant_program', 'organization', 'applicant')
            .order_by('-submitted_at')[:10]
        )

        active_awards = (
            Award.objects
            .filter(
                status__in=[Award.Status.ACTIVE, Award.Status.EXECUTED],
            )
        )
        if user.agency_id:
            active_awards = active_awards.filter(agency=user.agency)
        active_awards = (
            active_awards
            .select_related('grant_program', 'organization', 'recipient')
            .order_by('-start_date')[:10]
        )

        total_funding_qs = Award.objects.filter(
            status__in=[Award.Status.ACTIVE, Award.Status.EXECUTED],
        )
        if user.agency_id:
            total_funding_qs = total_funding_qs.filter(agency=user.agency)
        total_funding = int(
            total_funding_qs.aggregate(total=Sum('award_amount'))['total']
            or 0
        )

        from applications.models import ApplicationAssignment

        my_assignments = (
            ApplicationAssignment.objects.filter(
                assigned_to=user,
                status__in=[
                    ApplicationAssignment.Status.ASSIGNED,
                    ApplicationAssignment.Status.IN_PROGRESS,
                ],
            )
            .select_related(
                'application', 'application__grant_program',
                'application__organization',
            )
            .order_by('-claimed_at')[:5]
        )

        # Build assignments dict for dashboard claim/assign buttons
        app_ids = [a.pk for a in pending_applications]
        dash_assignments = ApplicationAssignment.objects.filter(
            application_id__in=app_ids,
            status__in=[
                ApplicationAssignment.Status.ASSIGNED,
                ApplicationAssignment.Status.IN_PROGRESS,
            ],
        ).select_related('assigned_to')

        return {
            'pending_applications': pending_applications,
            'active_awards': active_awards,
            'total_funding': total_funding,
            'assignments_by_app': {
                str(a.application_id): a for a in dash_assignments
            },
            'can_assign': getattr(user, 'role', '') in GRANT_MANAGER_ROLES,
            'pending_applications_count': (
                Application.objects
                .filter(agency_filter)
                .filter(status__in=[
                    Application.Status.SUBMITTED,
                    Application.Status.UNDER_REVIEW,
                ])
                .count()
            ),
            'active_awards_count': (
                Award.objects
                .filter(
                    status__in=[Award.Status.ACTIVE, Award.Status.EXECUTED],
                    **({"agency": user.agency} if user.agency_id else {}),
                )
                .count()
            ),
            'my_assignments': my_assignments,
            'my_assignments_count': ApplicationAssignment.objects.filter(
                assigned_to=user,
                status__in=['assigned', 'in_progress'],
            ).count(),
            'pending_reviews_count': (
                Application.objects
                .filter(agency_filter)
                .filter(status=Application.Status.UNDER_REVIEW)
                .count()
            ),
            'pending_claims_count': OrganizationClaim.objects.filter(
                status=OrganizationClaim.Status.PENDING,
            ).count(),
        }

    @staticmethod
    def _applicant_context(user):
        """Build dashboard context for applicant users."""
        from core.models import get_harbor_profile
        from grants.models import GrantPreference, OpportunityMatch, SavedProgram

        recent_applications = (
            Application.objects
            .filter(applicant=user)
            .select_related('grant_program', 'organization')
            .order_by('-updated_at')[:10]
        )

        recent_awards = (
            Award.objects
            .filter(recipient=user)
            .select_related('grant_program', 'organization')
            .order_by('-created_at')[:10]
        )

        saved_programs = (
            SavedProgram.objects
            .filter(user=user)
            .select_related('grant_program', 'grant_program__agency')
            .order_by('-updated_at')[:5]
        )

        # AI-recommended matches (top 5, excluding dismissed)
        recommended_matches = (
            OpportunityMatch.objects
            .filter(user=user)
            .exclude(status=OpportunityMatch.Status.DISMISSED)
            .select_related('federal_opportunity', 'grant_program')
            [:5]
        )
        new_match_count = OpportunityMatch.objects.filter(
            user=user, status=OpportunityMatch.Status.NEW,
        ).count()

        applications_count = Application.objects.filter(applicant=user).count()
        awards_count = Award.objects.filter(recipient=user).count()
        saved_programs_count = SavedProgram.objects.filter(user=user).count()
        from django.urls import reverse
        browse_url = reverse('portal:opportunities')
        return {
            'recent_applications': recent_applications,
            'recent_awards': recent_awards,
            'applications_count': applications_count,
            'awards_count': awards_count,
            'saved_programs': saved_programs,
            'saved_programs_count': saved_programs_count,
            'applications_card_url': reverse('applications:my-applications') if applications_count else browse_url,
            'awards_card_url': reverse('awards:my-awards') if awards_count else browse_url,
            'saved_card_url': reverse('grants:saved-list') if saved_programs_count else browse_url,
            'pending_actions_count': Notification.objects.filter(
                recipient=user, is_read=False,
            ).count(),
            'recommended_matches': recommended_matches,
            'new_match_count': new_match_count,
            'has_ai_access': get_harbor_profile(user).has_ai_access,
            'has_preferences': GrantPreference.objects.filter(user=user, is_active=True).exists(),
        }

    @staticmethod
    def _reviewer_context(user):
        """Build dashboard context for reviewers and auditors."""
        from reviews.models import ReviewAssignment

        pending_applications = (
            Application.objects
            .filter(status__in=[
                Application.Status.SUBMITTED,
                Application.Status.UNDER_REVIEW,
            ])
            .select_related('grant_program', 'organization', 'applicant')
            .order_by('-submitted_at')[:10]
        )

        my_assignments = ReviewAssignment.objects.filter(reviewer=user)
        my_pending = my_assignments.filter(
            status__in=[
                ReviewAssignment.Status.ASSIGNED,
                ReviewAssignment.Status.IN_PROGRESS,
            ],
        ).count()
        my_completed = my_assignments.filter(
            status=ReviewAssignment.Status.COMPLETED,
        ).count()

        return {
            'pending_applications': pending_applications,
            'pending_applications_count': (
                Application.objects
                .filter(status__in=[
                    Application.Status.SUBMITTED,
                    Application.Status.UNDER_REVIEW,
                ])
                .count()
            ),
            'my_pending_reviews': my_pending,
            'my_completed_reviews': my_completed,
        }

    @staticmethod
    def _federal_coordinator_context(user):
        """Build dashboard context for the Federal Fund Coordinator."""
        from core.models import get_harbor_profile
        from grants.models import FederalOpportunity, GrantPreference, OpportunityMatch, TrackedOpportunity

        # Federal opportunity KPIs
        open_federal = FederalOpportunity.objects.filter(
            opportunity_status=FederalOpportunity.OpportunityStatus.POSTED,
        ).count()

        tracked_qs = TrackedOpportunity.objects.filter(tracked_by=user)
        tracked_count = tracked_qs.count()
        linked_count = tracked_qs.exclude(grant_program=None).count()

        total_federal_funding = FederalOpportunity.objects.filter(
            opportunity_status=FederalOpportunity.OpportunityStatus.POSTED,
            total_funding__isnull=False,
        ).aggregate(total=Sum('total_funding'))['total'] or 0

        # Tracked opportunities list
        tracked_opportunities = (
            tracked_qs
            .select_related('federal_opportunity', 'grant_program')
            .order_by('-updated_at')[:10]
        )

        # Recent federal opportunities (latest synced)
        recent_federal = (
            FederalOpportunity.objects
            .filter(opportunity_status=FederalOpportunity.OpportunityStatus.POSTED)
            .order_by('-synced_at')[:5]
        )

        # Approaching deadlines (tracked items closing within 14 days)
        from datetime import timedelta
        today = timezone.now().date()
        approaching_deadlines = (
            tracked_qs
            .filter(
                federal_opportunity__close_date__gte=today,
                federal_opportunity__close_date__lte=today + timedelta(days=14),
            )
            .select_related('federal_opportunity')
            .order_by('federal_opportunity__close_date')[:5]
        )

        # AI-recommended matches (top 5, excluding dismissed)
        recommended_matches = (
            OpportunityMatch.objects
            .filter(user=user)
            .exclude(status=OpportunityMatch.Status.DISMISSED)
            .select_related('federal_opportunity', 'grant_program')
            [:5]
        )
        new_match_count = OpportunityMatch.objects.filter(
            user=user, status=OpportunityMatch.Status.NEW,
        ).count()

        from django.urls import reverse
        browse_federal = reverse('portal:federal-opportunities')
        return {
            'open_federal_count': open_federal,
            'tracked_count': tracked_count,
            'linked_count': linked_count,
            'total_federal_funding': int(total_federal_funding),
            'tracked_opportunities': tracked_opportunities,
            'recent_federal': recent_federal,
            'tracked_card_url': reverse('grants:tracked-list') if tracked_count else browse_federal,
            'linked_card_url': reverse('grants:program-list') if linked_count else browse_federal,
            'approaching_deadlines': approaching_deadlines,
            'recommended_matches': recommended_matches,
            'new_match_count': new_match_count,
            'has_ai_access': get_harbor_profile(user).has_ai_access,
            'has_preferences': GrantPreference.objects.filter(user=user, is_active=True).exists(),
        }


# ---------------------------------------------------------------------------
# Statewide Analytics Dashboard
# ---------------------------------------------------------------------------
class AnalyticsDashboardView(SystemAdminRequiredMixin, TemplateView):
    """Statewide analytics dashboard for system administrators."""

    template_name = 'core/analytics.html'

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'role', '') != 'system_admin' and not getattr(request.user, 'is_superuser', False):
            messages.error(request, _('Access denied. System administrators only.'))
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from grants.models import GrantProgram
        from financial.models import DrawdownRequest, Transaction
        from reporting.models import Report

        # Overview KPIs
        context['total_programs'] = GrantProgram.objects.count()
        context['active_programs'] = GrantProgram.objects.filter(
            status__in=['posted', 'accepting_applications']
        ).count()
        context['total_applications'] = Application.objects.count()
        context['pending_applications'] = Application.objects.filter(
            status__in=['submitted', 'under_review']
        ).count()
        context['total_awards'] = Award.objects.count()
        context['active_awards'] = Award.objects.filter(
            status__in=['active', 'executed']
        ).count()
        context['total_funding'] = int(Award.objects.filter(
            status__in=['active', 'executed', 'completed']
        ).aggregate(total=Sum('award_amount'))['total'] or 0)

        # Application stats
        context['approval_rate'] = 0
        total_decided = Application.objects.filter(
            status__in=['approved', 'denied']
        ).count()
        if total_decided:
            approved = Application.objects.filter(status='approved').count()
            context['approval_rate'] = int((approved / total_decided) * 100)

        # Per-agency breakdown (single annotated query instead of N+1)
        from django.db.models import Subquery
        agency_stats = list(
            Agency.objects.filter(is_active=True)
            .annotate(
                programs=Count('grant_programs', distinct=True),
                applications=Count('grant_programs__applications', distinct=True),
                awards_count=Count('awards', distinct=True),
                total_funding=Sum(
                    'awards__award_amount',
                    filter=Q(awards__status__in=['active', 'executed', 'completed']),
                ),
            )
            .order_by('name')
        )
        # Build the list of dicts with 'agency' key for template compatibility
        agency_stats = [
            {
                'agency': a,
                'programs': a.programs,
                'applications': a.applications,
                'awards': a.awards_count,
                'total_funding': a.total_funding or 0,
            }
            for a in agency_stats
        ]
        context['agency_stats'] = agency_stats

        # Application status distribution
        context['status_distribution'] = (
            Application.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )

        # Overdue reports
        context['overdue_reports'] = Report.objects.filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'revision_requested'],
        ).select_related('award', 'template').count()

        # Recent activity
        context['recent_applications'] = Application.objects.select_related(
            'grant_program', 'applicant', 'organization'
        ).order_by('-created_at')[:5]

        context['recent_awards'] = Award.objects.select_related(
            'grant_program', 'agency', 'organization'
        ).order_by('-created_at')[:5]

        # Financial summary
        context['total_disbursed'] = int(Transaction.objects.filter(
            transaction_type__in=['payment', 'drawdown']
        ).aggregate(total=Sum('amount'))['total'] or 0)

        context['pending_drawdowns'] = DrawdownRequest.objects.filter(
            status='submitted'
        ).count()

        # ---------------------------------------------------------------
        # Chart data (JSON-safe for embedding via json_script)
        # ---------------------------------------------------------------

        # 1. Application status distribution for doughnut chart
        status_labels = dict(Application.Status.choices)
        chart_status_data = {}
        for item in context['status_distribution']:
            label = str(status_labels.get(item['status'], item['status']))
            chart_status_data[label] = item['count']

        # 2. Agency funding for horizontal bar chart
        chart_agency_data = OrderedDict()
        sorted_agencies = sorted(
            agency_stats, key=lambda s: s['total_funding'], reverse=True
        )
        for stat in sorted_agencies:
            abbr = stat['agency'].abbreviation
            chart_agency_data[abbr] = float(stat['total_funding'])

        # 3. Monthly award trends (last 12 months) for line chart
        twelve_months_ago = timezone.now() - timedelta(days=365)
        monthly_qs = (
            Award.objects
            .filter(created_at__gte=twelve_months_ago)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        chart_monthly_awards = OrderedDict()
        for entry in monthly_qs:
            month_label = entry['month'].strftime('%b %Y')
            chart_monthly_awards[month_label] = entry['count']

        # 4. Budget utilization: awarded vs disbursed per program (top 10)
        top_programs = (
            Award.objects
            .filter(status__in=['active', 'executed', 'completed'])
            .values('grant_program__title')
            .annotate(
                total_awarded=Sum('award_amount'),
                total_disbursed=Sum('transactions__amount',
                                    filter=Q(transactions__transaction_type__in=['payment', 'drawdown'])),
            )
            .order_by('-total_awarded')[:10]
        )
        chart_budget_data = OrderedDict()
        for prog in top_programs:
            title = prog['grant_program__title']
            if len(title) > 30:
                title = title[:27] + '...'
            chart_budget_data[title] = {
                'awarded': float(prog['total_awarded'] or 0),
                'disbursed': float(prog['total_disbursed'] or 0),
            }

        # Bundle all chart data into a single dict for the template.
        # json_script in the template handles JSON serialisation – do NOT
        # pre-serialise with json.dumps (that causes double-encoding).
        context['chart_data'] = {
            'status': chart_status_data,
            'agency': chart_agency_data,
            'monthly_awards': chart_monthly_awards,
            'budget': chart_budget_data,
        }

        return context


# ---------------------------------------------------------------------------
# Deadline Calendar
# ---------------------------------------------------------------------------
class DeadlineCalendarView(LoginRequiredMixin, TemplateView):
    """Calendar view showing upcoming grant deadlines and report due dates."""

    template_name = 'core/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from grants.models import GrantProgram
        from reporting.models import Report

        # Upcoming grant deadlines
        context['upcoming_deadlines'] = GrantProgram.objects.filter(
            application_deadline__gte=timezone.now(),
            is_published=True,
        ).order_by('application_deadline')[:20]

        # Overdue reports for the current user
        user = self.request.user
        overdue_reports_qs = Report.objects.filter(
            due_date__lt=timezone.now().date(),
            status__in=['draft', 'revision_requested'],
        ).select_related('award', 'award__grant_program')

        if user.is_agency_staff and user.agency_id:
            overdue_reports_qs = overdue_reports_qs.filter(award__agency=user.agency)
        elif not user.is_agency_staff and user.role != 'system_admin':
            overdue_reports_qs = overdue_reports_qs.filter(award__recipient=user)

        context['overdue_reports'] = overdue_reports_qs[:20]

        # Upcoming report deadlines
        upcoming_reports_qs = Report.objects.filter(
            due_date__gte=timezone.now().date(),
            status__in=['draft', 'revision_requested'],
        ).select_related('award', 'award__grant_program').order_by('due_date')

        if user.is_agency_staff and user.agency_id:
            upcoming_reports_qs = upcoming_reports_qs.filter(award__agency=user.agency)
        elif not user.is_agency_staff and user.role != 'system_admin':
            upcoming_reports_qs = upcoming_reports_qs.filter(award__recipient=user)

        context['upcoming_reports'] = upcoming_reports_qs[:20]

        # Awards expiring soon (within 90 days)
        ninety_days = timezone.now().date() + timedelta(days=90)
        expiring_qs = Award.objects.filter(
            end_date__lte=ninety_days,
            end_date__gte=timezone.now().date(),
            status__in=['active', 'executed'],
        ).select_related('grant_program', 'organization')

        if user.is_agency_staff and user.agency_id:
            expiring_qs = expiring_qs.filter(agency=user.agency)

        context['expiring_awards'] = expiring_qs[:20]

        return context


# ---------------------------------------------------------------------------
# Map View — Choropleth of grant distribution by CT municipality
# ---------------------------------------------------------------------------
class MapView(SystemAdminRequiredMixin, TemplateView):
    """Interactive Mapbox GL JS map showing grant distribution across CT."""

    template_name = 'core/map_view.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mapbox_token'] = settings.MAPBOX_ACCESS_TOKEN
        # Get list of agencies and programs for filter dropdowns
        from grants.models import GrantProgram

        context['agencies'] = Agency.objects.filter(
            is_active=True,
        ).order_by('abbreviation')
        context['programs'] = GrantProgram.objects.filter(
            status__in=['posted', 'accepting_applications', 'closed'],
        ).order_by('title')
        return context


class MapDataAPIView(SystemAdminRequiredMixin, View):
    """JSON endpoint returning per-municipality award aggregates."""

    def get(self, request):
        # Aggregate awards by organization city (= municipality)
        qs = (
            Award.objects
            .filter(status__in=['active', 'executed', 'completed'])
            .values('organization__city')
            .annotate(
                award_count=Count('id'),
                total_funding=Sum('award_amount'),
            )
            .order_by('-total_funding')
        )

        # Optional filters
        agency = request.GET.get('agency')
        program = request.GET.get('program')
        if agency:
            qs = qs.filter(agency__abbreviation=agency)
        if program:
            qs = qs.filter(grant_program__id=program)

        result = {}
        for item in qs:
            city = item['organization__city']
            if city:
                result[city.title()] = {
                    'award_count': item['award_count'],
                    'total_funding': float(item['total_funding'] or 0),
                }

        return JsonResponse({'municipalities': result})


class MunicipalityDetailView(SystemAdminRequiredMixin, SortableListMixin, ListView):
    """Tear sheet listing all awards for a specific CT municipality."""

    template_name = 'core/municipality_detail.html'
    context_object_name = 'awards'
    paginate_by = 20

    sortable_fields = {
        'award_number': 'award_number',
        'title': 'title',
        'organization': 'organization__name',
        'award_amount': 'award_amount',
        'status': 'status',
    }
    default_sort = 'award_amount'
    default_dir = 'desc'

    def get_queryset(self):
        self.municipality_name = self.kwargs['municipality_name']
        qs = (
            Award.objects
            .filter(
                status__in=['active', 'executed', 'completed'],
                organization__city__iexact=self.municipality_name,
            )
            .select_related('grant_program', 'agency', 'recipient', 'organization')
        )
        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['municipality_name'] = self.municipality_name.title()
        aggregates = self.get_queryset().aggregate(
            total_funding=Sum('award_amount'),
            award_count=Count('id'),
        )
        context['total_funding'] = aggregates['total_funding'] or 0
        context['award_count'] = aggregates['award_count'] or 0
        context['county'] = self.request.GET.get('county', '')
        context['planning_region'] = self.request.GET.get('region', '')
        return context


# Demo Quick Login was removed in the 2026-05-03 CSO sweep — the canonical
# implementation lives at keel.core.demo.demo_login_view (mounted at
# /demo-login/) which enforces the DEMO_ROLES allowlist, rate limits, and
# is_active check. The local copy here had drifted: it accepted any
# username (no role allowlist) and would have logged in dokadmin or any
# other privileged user when DEMO_MODE was on. It was never wired into
# any URL, but leaving it in the module is a footgun. See keel CLAUDE.md
# → "Demo authentication — passwordless contract" for the full rationale.
