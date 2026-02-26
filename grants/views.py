from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Exists, IntegerField, OuterRef, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from core.mixins import (
    AgencyObjectMixin,
    AgencyStaffRequiredMixin,
    SortableListMixin,
    FederalCoordinatorRequiredMixin,
    GrantManagerRequiredMixin,
)
from core.models import User
from core.utils import safe_redirect_url

from .forms import CollaboratorForm, GrantPreferenceForm, GrantProgramForm, TrackedOpportunityForm
from .matching import run_matching_async
from .models import (
    FederalOpportunity,
    FundingSource,
    GrantPreference,
    GrantProgram,
    OpportunityCollaborator,
    OpportunityMatch,
    SavedProgram,
    TrackedOpportunity,
)


class GrantProgramListView(AgencyStaffRequiredMixin, SortableListMixin, AgencyObjectMixin, ListView):
    """Agency staff view listing grant programs.

    System admins see all programs; other agency staff see only their
    own agency's programs.
    """

    model = GrantProgram
    template_name = 'grants/program_list.html'
    context_object_name = 'programs'
    paginate_by = 20

    sortable_fields = {
        'title': 'title',
        'agency': 'agency__abbreviation',
        'total_funding': 'total_funding',
        'status': 'status',
        'deadline': 'application_deadline',
    }
    default_sort = 'deadline'
    default_dir = 'asc'

    def get_queryset(self):
        qs = GrantProgram.objects.select_related(
            'agency', 'funding_source', 'created_by'
        )
        user = self.request.user
        if user.role != User.Role.SYSTEM_ADMIN and user.agency:
            qs = qs.filter(agency=user.agency)
        return self.apply_sorting(qs)


class GrantProgramCreateView(GrantManagerRequiredMixin, CreateView):
    """Create a new grant program.

    Supports ``?from_federal=<id>`` query parameter to pre-populate the form
    from a :model:`grants.FederalOpportunity`.  When used, a matching
    :model:`grants.FundingSource` (type=federal) is auto-created/found and
    the ``FederalOpportunity.funding_source`` FK is linked back.
    """

    model = GrantProgram
    form_class = GrantProgramForm
    template_name = 'grants/program_form.html'

    def _get_federal_opportunity(self):
        """Return the FederalOpportunity if ``from_federal`` is in the querystring."""
        fed_id = self.request.GET.get('from_federal')
        if fed_id:
            return FederalOpportunity.objects.filter(pk=fed_id).first()
        return None

    def get_initial(self):
        initial = super().get_initial()
        fed_opp = self._get_federal_opportunity()
        if fed_opp:
            # Auto-create or find a federal FundingSource from this opportunity
            cfda = ', '.join(fed_opp.cfda_numbers) if fed_opp.cfda_numbers else ''
            funding_source, _created = FundingSource.objects.get_or_create(
                source_type=FundingSource.SourceType.FEDERAL,
                federal_agency=fed_opp.agency_name or fed_opp.agency_code or '',
                cfda_number=cfda[:20],  # max_length=20
                defaults={
                    'name': f"Federal — {fed_opp.agency_name or fed_opp.agency_code}"[:255],
                    'description': f"Auto-created from Grants.gov opportunity {fed_opp.opportunity_number or fed_opp.opportunity_id}",
                },
            )
            # Link the FederalOpportunity to this FundingSource
            if not fed_opp.funding_source_id:
                fed_opp.funding_source = funding_source
                fed_opp.save(update_fields=['funding_source'])

            initial['title'] = fed_opp.title or ''
            initial['description'] = fed_opp.description or ''
            initial['funding_source'] = funding_source.pk
            initial['eligibility_criteria'] = fed_opp.eligible_applicants or ''
            if fed_opp.total_funding:
                initial['total_funding'] = fed_opp.total_funding
            if fed_opp.award_floor:
                initial['min_award'] = fed_opp.award_floor
            if fed_opp.award_ceiling:
                initial['max_award'] = fed_opp.award_ceiling
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fed_opp = self._get_federal_opportunity()
        if fed_opp:
            context['from_federal'] = fed_opp
        return context

    def form_valid(self, form):
        form.instance.agency = self.request.user.agency
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        # If created from a federal opportunity, link tracked record if one exists
        fed_opp = self._get_federal_opportunity()
        if fed_opp:
            TrackedOpportunity.objects.filter(
                federal_opportunity=fed_opp,
                tracked_by=self.request.user,
                grant_program__isnull=True,
            ).update(grant_program=self.object)

        return response

    def get_success_url(self):
        return reverse_lazy('grants:program-detail', kwargs={'pk': self.object.pk})


class GrantProgramUpdateView(GrantManagerRequiredMixin, AgencyObjectMixin, UpdateView):
    """Edit an existing grant program."""

    model = GrantProgram
    form_class = GrantProgramForm
    template_name = 'grants/program_form.html'

    def get_queryset(self):
        qs = GrantProgram.objects.select_related('agency', 'funding_source')
        user = self.request.user
        if user.role != User.Role.SYSTEM_ADMIN and user.agency:
            qs = qs.filter(agency=user.agency)
        return qs

    def get_success_url(self):
        return reverse_lazy('grants:program-detail', kwargs={'pk': self.object.pk})


class GrantProgramDetailView(AgencyStaffRequiredMixin, DetailView):
    """Detail view for a grant program, including applications and documents."""

    model = GrantProgram
    template_name = 'grants/program_detail.html'
    context_object_name = 'program'

    def get_queryset(self):
        return GrantProgram.objects.select_related(
            'agency', 'funding_source', 'created_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['applications'] = self.object.applications.select_related(
            'applicant', 'organization'
        ).all()
        context['documents'] = self.object.documents.all()
        return context


class PublishGrantProgramView(GrantManagerRequiredMixin, View):
    """POST-only view to toggle the published state and status of a grant program."""

    http_method_names = ['post']

    def post(self, request, pk):
        program = get_object_or_404(GrantProgram, pk=pk)

        # Agency ownership check: non-system-admins may only publish
        # programs belonging to their own agency.
        if request.user.role != 'system_admin' and program.agency_id != request.user.agency_id:
            raise PermissionDenied

        if program.is_published:
            # Un-publish: revert to draft
            program.is_published = False
            program.status = GrantProgram.Status.DRAFT
            program.published_at = None
        else:
            # Publish
            program.is_published = True
            program.status = GrantProgram.Status.POSTED
            program.published_at = timezone.now()

        program.save(update_fields=[
            'is_published', 'status', 'published_at', 'updated_at',
        ])

        return JsonResponse({
            'is_published': program.is_published,
            'status': program.get_status_display(),
        })


# ---------------------------------------------------------------------------
# Tracked Federal Opportunities (Federal Fund Coordinator views)
# ---------------------------------------------------------------------------

class TrackedOpportunityListView(FederalCoordinatorRequiredMixin, SortableListMixin, ListView):
    """List federal opportunities tracked by the current user."""

    model = TrackedOpportunity
    template_name = 'grants/tracked_opportunities.html'
    context_object_name = 'tracked_opportunities'
    paginate_by = 20

    sortable_fields = {
        'opportunity': 'federal_opportunity__title',
        'agency': 'federal_opportunity__agency_name',
        'status': 'status',
        'priority': Case(
            When(priority='high', then=Value(1)),
            When(priority='medium', then=Value(2)),
            When(priority='low', then=Value(3)),
            output_field=IntegerField(),
        ),
        'close_date': 'federal_opportunity__close_date',
    }
    default_sort = 'close_date'
    default_dir = 'asc'

    def get_queryset(self):
        qs = TrackedOpportunity.objects.select_related(
            'federal_opportunity', 'grant_program',
        ).filter(tracked_by=self.request.user)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = TrackedOpportunity.TrackingStatus.choices
        context['priority_choices'] = [
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
        ]
        context['current_status'] = self.request.GET.get('status', '')
        context['current_priority'] = self.request.GET.get('priority', '')
        return context


class TrackOpportunityView(FederalCoordinatorRequiredMixin, View):
    """POST-only view to start tracking a federal opportunity."""

    http_method_names = ['post']

    def post(self, request):
        opp_id = request.POST.get('federal_opportunity_id')
        opp = get_object_or_404(FederalOpportunity, pk=opp_id)

        tracked, created = TrackedOpportunity.objects.get_or_create(
            federal_opportunity=opp,
            tracked_by=request.user,
            defaults={'status': TrackedOpportunity.TrackingStatus.WATCHING},
        )

        if created:
            messages.success(
                request,
                _('Now tracking "%(title)s".') % {'title': opp.title[:60]},
            )
        else:
            messages.info(
                request,
                _('You are already tracking this opportunity.'),
            )

        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('dashboard')))


class TrackedOpportunityDetailView(FederalCoordinatorRequiredMixin, DetailView):
    """Detail view for a tracked opportunity with edit form and collaborators."""

    model = TrackedOpportunity
    template_name = 'grants/tracked_opportunity_detail.html'
    context_object_name = 'tracked'

    def get_queryset(self):
        return TrackedOpportunity.objects.select_related(
            'federal_opportunity', 'grant_program', 'tracked_by',
        ).filter(tracked_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = TrackedOpportunityForm(instance=self.object)
        context['collaborator_form'] = CollaboratorForm()
        context['collaborators'] = self.object.collaborators.select_related(
            'user', 'invited_by',
        ).filter(is_active=True)
        return context


class TrackedOpportunityUpdateView(FederalCoordinatorRequiredMixin, UpdateView):
    """Update a tracked opportunity's status, notes, priority, or linked program."""

    model = TrackedOpportunity
    form_class = TrackedOpportunityForm
    template_name = 'grants/tracked_opportunity_detail.html'
    context_object_name = 'tracked'

    def get_queryset(self):
        return TrackedOpportunity.objects.select_related(
            'federal_opportunity', 'grant_program', 'tracked_by',
        ).filter(tracked_by=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['collaborator_form'] = CollaboratorForm()
        context['collaborators'] = self.object.collaborators.select_related(
            'user', 'invited_by',
        ).filter(is_active=True)
        return context

    def form_valid(self, form):
        messages.success(self.request, _('Tracking details updated.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('grants:tracked-detail', kwargs={'pk': self.object.pk})


class AddCollaboratorView(FederalCoordinatorRequiredMixin, FormView):
    """Add an internal or external collaborator to a tracked opportunity."""

    form_class = CollaboratorForm
    template_name = 'grants/add_collaborator.html'

    def dispatch(self, request, *args, **kwargs):
        self.tracked = get_object_or_404(
            TrackedOpportunity,
            pk=self.kwargs['pk'],
            tracked_by=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        collab_type = form.cleaned_data['collaborator_type']
        role = form.cleaned_data['role']

        collab_kwargs = {
            'tracked_opportunity': self.tracked,
            'role': role,
            'invited_by': self.request.user,
        }

        if collab_type == 'internal':
            user = get_object_or_404(User, username=form.cleaned_data['username'])
            collab_kwargs['user'] = user
        else:
            collab_kwargs['email'] = form.cleaned_data['email']
            collab_kwargs['name'] = form.cleaned_data.get('name', '')

        OpportunityCollaborator.objects.create(**collab_kwargs)
        messages.success(self.request, _('Collaborator added successfully.'))
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('grants:tracked-detail', kwargs={'pk': self.tracked.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tracked'] = self.tracked
        return context


class RemoveCollaboratorView(FederalCoordinatorRequiredMixin, View):
    """POST-only view to deactivate a collaborator from a tracked opportunity."""

    http_method_names = ['post']

    def post(self, request, pk, collab_pk):
        tracked = get_object_or_404(
            TrackedOpportunity, pk=pk, tracked_by=request.user,
        )
        collaborator = get_object_or_404(
            OpportunityCollaborator, pk=collab_pk, tracked_opportunity=tracked,
        )
        collaborator.is_active = False
        collaborator.save(update_fields=['is_active'])

        messages.success(request, _('Collaborator removed.'))
        return redirect(reverse('grants:tracked-detail', kwargs={'pk': pk}))


# ---------------------------------------------------------------------------
# Applicant Saved Programs (Watchlist)
# ---------------------------------------------------------------------------
class SaveProgramView(LoginRequiredMixin, View):
    """POST-only toggle to save/unsave a grant program for an applicant."""

    http_method_names = ['post']

    def post(self, request):
        program_id = request.POST.get('grant_program_id')
        program = get_object_or_404(GrantProgram, pk=program_id, is_published=True)

        saved, created = SavedProgram.objects.get_or_create(
            grant_program=program,
            user=request.user,
            defaults={'interest_level': SavedProgram.InterestLevel.WATCHING},
        )

        if created:
            messages.success(
                request,
                _('Saved "%(title)s" to your watchlist.') % {
                    'title': program.title[:60],
                },
            )
        else:
            saved.delete()
            messages.info(request, _('Removed from your watchlist.'))

        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('portal:opportunities')))


class SavedProgramListView(LoginRequiredMixin, SortableListMixin, ListView):
    """List grant programs saved/bookmarked by the current user."""

    model = SavedProgram
    template_name = 'grants/saved_programs.html'
    context_object_name = 'saved_programs'
    paginate_by = 20

    sortable_fields = {
        'program': 'grant_program__title',
        'interest_level': 'interest_level',
        'deadline': 'grant_program__application_deadline',
        'created_at': 'created_at',
    }
    default_sort = 'created_at'
    default_dir = 'desc'

    def get_queryset(self):
        qs = SavedProgram.objects.filter(
            user=self.request.user,
        ).select_related('grant_program', 'grant_program__agency')

        interest = self.request.GET.get('interest_level')
        if interest:
            qs = qs.filter(interest_level=interest)

        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['interest_choices'] = SavedProgram.InterestLevel.choices
        context['current_interest'] = self.request.GET.get('interest_level', '')
        return context


class UpdateSavedProgramView(LoginRequiredMixin, View):
    """POST-only view to update a saved program's interest level and notes."""

    http_method_names = ['post']

    def post(self, request, pk):
        saved = get_object_or_404(SavedProgram, pk=pk, user=request.user)
        interest = request.POST.get('interest_level')
        notes = request.POST.get('notes', '').strip()

        if interest and interest in dict(SavedProgram.InterestLevel.choices):
            saved.interest_level = interest
        saved.notes = notes
        saved.save(update_fields=['interest_level', 'notes', 'updated_at'])

        messages.success(request, _('Saved program updated.'))
        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('grants:saved-list')))


# ---------------------------------------------------------------------------
# AI Grant Matching — Preferences & Recommendations
# ---------------------------------------------------------------------------

class GrantPreferenceView(LoginRequiredMixin, UpdateView):
    """Create or update the user's grant-matching preferences.

    After a successful save the view kicks off AI matching in a background
    thread so that recommendations are ready by the time the user visits
    the Recommendations page.
    """

    model = GrantPreference
    form_class = GrantPreferenceForm
    template_name = 'grants/grant_preferences.html'
    success_url = reverse_lazy('grants:recommendations')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.has_ai_access:
            messages.info(
                request,
                _('To use AI-powered grant matching, please add your '
                  'Anthropic API key in your profile settings.'),
            )
            return redirect('core:profile')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj, _created = GrantPreference.objects.get_or_create(
            user=self.request.user,
        )
        return obj

    def form_valid(self, form):
        response = super().form_valid(form)
        # Fire background matching so recommendations appear quickly
        run_matching_async(self.request.user)
        messages.success(
            self.request,
            _('Preferences saved! AI matching is running — recommendations '
              'will appear shortly.'),
        )
        return response


class RecommendedMatchesView(LoginRequiredMixin, ListView):
    """List AI-recommended opportunity matches for the current user."""

    model = OpportunityMatch
    template_name = 'grants/recommendations.html'
    context_object_name = 'matches'
    paginate_by = 20

    def get_queryset(self):
        tracked_subquery = TrackedOpportunity.objects.filter(
            federal_opportunity=OuterRef('federal_opportunity'),
            tracked_by=self.request.user,
        )
        saved_subquery = SavedProgram.objects.filter(
            grant_program=OuterRef('grant_program'),
            user=self.request.user,
        )

        qs = OpportunityMatch.objects.filter(
            user=self.request.user,
        ).exclude(
            status=OpportunityMatch.Status.DISMISSED,
        ).select_related(
            'federal_opportunity', 'grant_program',
        ).annotate(
            is_tracked=Exists(tracked_subquery),
            is_saved=Exists(saved_subquery),
        )

        # Optional source filter
        source = self.request.GET.get('source')
        if source in ('federal', 'state'):
            qs = qs.filter(source=source)

        # Mark new matches as viewed
        qs.filter(status=OpportunityMatch.Status.NEW).update(
            status=OpportunityMatch.Status.VIEWED,
        )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_source'] = self.request.GET.get('source', '')
        context['total_matches'] = OpportunityMatch.objects.filter(
            user=self.request.user,
        ).exclude(status=OpportunityMatch.Status.DISMISSED).count()
        context['new_matches'] = OpportunityMatch.objects.filter(
            user=self.request.user,
            status=OpportunityMatch.Status.NEW,
        ).count()
        # Check if the user has set up preferences
        context['has_preferences'] = GrantPreference.objects.filter(
            user=self.request.user,
        ).exists()
        context['has_ai_access'] = self.request.user.has_ai_access
        return context


class DismissMatchView(LoginRequiredMixin, View):
    """POST-only view to dismiss a match recommendation."""

    http_method_names = ['post']

    def post(self, request, pk):
        match = get_object_or_404(
            OpportunityMatch, pk=pk, user=request.user,
        )
        match.status = OpportunityMatch.Status.DISMISSED
        match.save(update_fields=['status', 'updated_at'])
        messages.info(request, _('Recommendation dismissed.'))
        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('grants:recommendations')))


class TrackAndDismissView(FederalCoordinatorRequiredMixin, View):
    """POST-only: track a federal opportunity AND dismiss the recommendation."""

    http_method_names = ['post']

    def post(self, request, pk):
        match = get_object_or_404(
            OpportunityMatch, pk=pk, user=request.user,
        )
        if match.federal_opportunity:
            TrackedOpportunity.objects.get_or_create(
                federal_opportunity=match.federal_opportunity,
                tracked_by=request.user,
                defaults={
                    'status': TrackedOpportunity.TrackingStatus.WATCHING,
                },
            )
        match.status = OpportunityMatch.Status.DISMISSED
        match.save(update_fields=['status', 'updated_at'])
        messages.success(
            request,
            _('Opportunity tracked and recommendation dismissed.'),
        )
        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('grants:recommendations')))


class MatchFeedbackView(LoginRequiredMixin, View):
    """POST-only: record thumbs up/down feedback on a recommendation."""

    http_method_names = ['post']

    def post(self, request, pk):
        match = get_object_or_404(
            OpportunityMatch, pk=pk, user=request.user,
        )
        feedback = request.POST.get('feedback', '')
        reason = request.POST.get('feedback_reason', '')

        if feedback in dict(OpportunityMatch.Feedback.choices):
            match.feedback = feedback
        if feedback == 'negative' and reason in dict(
            OpportunityMatch.FeedbackReason.choices,
        ):
            match.feedback_reason = reason
        else:
            match.feedback_reason = ''

        match.save(update_fields=['feedback', 'feedback_reason', 'updated_at'])

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'feedback': match.feedback,
                'show_preferences_hint': (
                    match.feedback == 'negative' and bool(match.feedback_reason)
                ),
            })

        if match.feedback == 'negative' and match.feedback_reason:
            messages.info(request, _(
                'Thanks for the feedback! Consider updating your '
                'preferences to improve future recommendations.',
            ))
        else:
            messages.success(request, _('Feedback recorded. Thank you!'))

        next_url = request.POST.get('next', '')
        return redirect(safe_redirect_url(request, next_url, fallback=reverse('grants:recommendations')))
