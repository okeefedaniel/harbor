from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView
from django.contrib.humanize.templatetags.humanize import intcomma

from keel.core.views import LandingView

from applications.models import Application
from grants.models import (
    FederalOpportunity,
    GrantProgram,
    GrantProgramDocument,
    TrackedOpportunity,
)


class HomeView(LandingView):
    """Public landing page for the Harbor portal — uses Keel's shared landing layout."""

    template_name = 'portal/home.html'
    authenticated_redirect = 'dashboard'

    features = [
        {'icon': 'bi-search', 'title': 'Discover Opportunities',
         'description': 'Browse and search state and federal funding opportunities filtered by agency, type, and status.',
         'color': 'blue'},
        {'icon': 'bi-file-earmark-text', 'title': 'Apply Online',
         'description': 'Complete grant applications online with built-in document uploads, validation, and progress saving.',
         'color': 'teal'},
        {'icon': 'bi-graph-up', 'title': 'Track Awards',
         'description': 'Monitor application status, manage active awards, submit reports, and request drawdowns.',
         'color': 'yellow'},
    ]

    steps = [
        {'title': 'Register', 'description': 'Create your account and set up your organization profile to get started.'},
        {'title': 'Find Opportunities', 'description': 'Browse available funding opportunities and filter by agency, type, or status.'},
        {'title': 'Apply', 'description': 'Complete and submit your application online with all required documents.'},
        {'title': 'Track Progress', 'description': 'Monitor your application status, manage awards, and submit required reports.'},
    ]

    def get_landing_stats(self):
        # Resilient: fall back to static stats if DB tables aren't present
        try:
            published = GrantProgram.objects.filter(is_published=True)
            count = published.count()
            total_funding = published.aggregate(total=Sum('total_funding'))['total'] or 0
            federal_count = FederalOpportunity.objects.filter(
                opportunity_status=FederalOpportunity.OpportunityStatus.POSTED,
            ).count()
            return [
                {'value': str(count), 'label': 'State Programs'},
                {'value': '$' + intcomma(int(total_funding)), 'label': 'State Funding'},
                {'value': str(federal_count), 'label': 'Federal Opportunities', 'url': '/federal-opportunities/'},
                {'value': '10+', 'label': 'Participating Agencies'},
            ]
        except Exception:
            return [
                {'value': 'State', 'label': 'Grants'},
                {'value': 'Federal', 'label': 'Opportunities'},
                {'value': 'Online', 'label': 'Applications'},
                {'value': '10+', 'label': 'Participating Agencies'},
            ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            published = GrantProgram.objects.filter(is_published=True)
            context['recent_opportunities'] = list(published.order_by('-posting_date')[:3])
            context['active_programs_count'] = published.count()
        except Exception:
            context['recent_opportunities'] = []
            context['active_programs_count'] = 0
        return context


class OpportunityListView(ListView):
    """Public listing of published grant opportunities with filtering."""

    model = GrantProgram
    template_name = 'portal/opportunities.html'
    context_object_name = 'opportunities'
    paginate_by = 12

    def get_queryset(self):
        qs = GrantProgram.objects.filter(is_published=True).select_related(
            'agency', 'funding_source'
        )

        agency = self.request.GET.get('agency')
        if agency:
            qs = qs.filter(agency_id=agency)

        grant_type = self.request.GET.get('grant_type')
        if grant_type:
            qs = qs.filter(grant_type=grant_type)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grant_types'] = GrantProgram.GrantType.choices
        context['statuses'] = GrantProgram.Status.choices
        context['current_filters'] = {
            'agency': self.request.GET.get('agency', ''),
            'grant_type': self.request.GET.get('grant_type', ''),
            'status': self.request.GET.get('status', ''),
        }

        # Build a dict mapping grant_program_id -> application status display
        # so the template can show "Application Submitted" badges, etc.
        if self.request.user.is_authenticated:
            user_apps = Application.objects.filter(
                applicant=self.request.user
            ).values_list('grant_program_id', 'status')
            context['user_applications'] = {
                str(gp_id): status for gp_id, status in user_apps
            }
        else:
            context['user_applications'] = {}

        context['view_mode'] = self.request.GET.get('view', 'cards')

        # Saved programs (watchlist) — set of saved program IDs for bookmark state
        if self.request.user.is_authenticated:
            from grants.models import SavedProgram
            saved_ids = SavedProgram.objects.filter(
                user=self.request.user,
            ).values_list('grant_program_id', flat=True)
            context['user_saved_programs'] = set(str(pk) for pk in saved_ids)
        else:
            context['user_saved_programs'] = set()

        return context


class OpportunityDetailView(DetailView):
    """Public detail view for a single grant opportunity."""

    model = GrantProgram
    template_name = 'portal/opportunity_detail.html'
    context_object_name = 'opportunity'

    def get_queryset(self):
        return GrantProgram.objects.filter(is_published=True).select_related(
            'agency', 'funding_source'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = self.object.documents.all()

        if self.request.user.is_authenticated:
            from grants.models import SavedProgram
            context['is_saved'] = SavedProgram.objects.filter(
                grant_program=self.object, user=self.request.user,
            ).exists()
        else:
            context['is_saved'] = False

        return context


class OpportunityDocumentDownloadView(View):
    """Public stream of a published GrantProgramDocument.

    CSO Wave 5: the portal opportunity detail page historically linked
    ``{{ doc.file.url }}`` directly, which (a) bypassed view-level ACL
    if /media/ ever started serving and (b) would happily serve a doc
    attached to an *unpublished* GrantProgram. This view re-runs the
    ``is_published=True`` gate per-request and streams via FileResponse.

    Intentionally NOT LoginRequired — the portal is anonymous-accessible
    by design (it's the public face of Harbor). Anonymity stops at the
    publication gate.
    """

    def get(self, request, pk):
        doc = get_object_or_404(
            GrantProgramDocument.objects.select_related('grant_program'),
            pk=pk,
        )
        # Same gate as OpportunityDetailView.get_queryset(). Published
        # opportunities are public; everything else 404s — don't confirm
        # whether the doc exists at all.
        if not doc.grant_program.is_published:
            raise Http404
        if not doc.file:
            raise Http404
        return FileResponse(
            doc.file.open('rb'),
            as_attachment=True,
            filename=doc.title or doc.file.name.rsplit('/', 1)[-1],
        )


class FederalOpportunityListView(ListView):
    """Public listing of federal grant opportunities with filtering."""

    model = FederalOpportunity
    template_name = 'portal/federal_opportunities.html'
    context_object_name = 'opportunities'
    paginate_by = 12

    def get_queryset(self):
        qs = FederalOpportunity.objects.all().order_by('-post_date')

        agency = self.request.GET.get('agency')
        if agency:
            qs = qs.filter(agency_code=agency)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(opportunity_status=status)

        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_filters'] = {
            'agency': self.request.GET.get('agency', ''),
            'status': self.request.GET.get('status', ''),
            'category': self.request.GET.get('category', ''),
            'q': self.request.GET.get('q', ''),
        }
        context['agency_codes'] = (
            FederalOpportunity.objects.exclude(agency_code='')
            .values_list('agency_code', flat=True)
            .distinct()
            .order_by('agency_code')
        )
        context['statuses'] = FederalOpportunity.OpportunityStatus.choices
        context['view_mode'] = self.request.GET.get('view', 'cards')
        return context


class FederalOpportunityDetailView(DetailView):
    """Public detail view for a single federal grant opportunity."""

    model = FederalOpportunity
    template_name = 'portal/federal_opportunity_detail.html'
    context_object_name = 'opportunity'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if (
            user.is_authenticated
            and hasattr(user, 'can_manage_federal')
            and user.can_manage_federal
        ):
            context['tracked_record'] = TrackedOpportunity.objects.filter(
                federal_opportunity=self.object,
                tracked_by=user,
            ).first()
        return context


class AboutView(TemplateView):
    """Static about page."""

    template_name = 'portal/about.html'


class HelpView(TemplateView):
    """Static help / FAQ page."""

    template_name = 'portal/help.html'


class UserManualView(TemplateView):
    """Comprehensive user manual for the Harbor system."""

    template_name = 'portal/user_manual.html'


class PrivacyPolicyView(TemplateView):
    """Privacy Policy page."""

    template_name = 'portal/privacy_policy.html'


class TermsOfServiceView(TemplateView):
    """Terms of Service page."""

    template_name = 'portal/terms_of_service.html'


class SupportView(TemplateView):
    """Support and documentation page."""

    template_name = 'portal/support.html'


class DemoGuideView(TemplateView):
    """Interactive product tour for RFP stakeholder presentations."""

    template_name = 'portal/demo_guide.html'
