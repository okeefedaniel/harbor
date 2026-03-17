from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from awards.models import Award
from core.audit import log_audit
from core.export import CSVExportMixin
from core.filters import ReportFilter
from core.mixins import AgencyStaffRequiredMixin, GrantManagerRequiredMixin, SortableListMixin
from core.models import AuditLog
from core.notifications import notify_report_review_complete

from .forms import ReportForm
from .models import Report, SF425Report


# ---------------------------------------------------------------------------
# Report List
# ---------------------------------------------------------------------------
class ReportListView(LoginRequiredMixin, SortableListMixin, CSVExportMixin, ListView):
    """List reports visible to the current user."""

    model = Report
    template_name = 'reporting/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20
    csv_filename = 'reports.csv'
    csv_columns = [
        (_lazy('Report ID'), 'id'),
        (_lazy('Report Type'), 'get_report_type_display'),
        (_lazy('Award'), 'award.award_number'),
        (_lazy('Status'), 'get_status_display'),
        (_lazy('Due Date'), 'due_date'),
        (_lazy('Submitted'), 'submitted_at'),
    ]

    sortable_fields = {
        'report_type': 'report_type',
        'award': 'award__award_number',
        'status': 'status',
        'due_date': 'due_date',
        'submitted_at': 'submitted_at',
    }
    default_sort = 'due_date'
    default_dir = 'asc'

    def get_queryset(self):
        qs = Report.objects.select_related(
            'award', 'template', 'submitted_by', 'reviewed_by',
        )
        user = self.request.user
        if user.is_agency_staff and user.agency_id:
            qs = qs.filter(award__agency=user.agency)
        elif not user.is_agency_staff and user.role != 'system_admin':
            qs = qs.filter(award__recipient=user)

        self.filterset = ReportFilter(self.request.GET, queryset=qs)
        return self.apply_sorting(self.filterset.qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filterset
        return context


# ---------------------------------------------------------------------------
# Report Create
# ---------------------------------------------------------------------------
class ReportCreateView(LoginRequiredMixin, CreateView):
    """Create a new report for an award."""

    model = Report
    form_class = ReportForm
    template_name = 'reporting/report_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        messages.success(self.request, _('Report created successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy('reporting:detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Report Detail
# ---------------------------------------------------------------------------
class ReportDetailView(LoginRequiredMixin, DetailView):
    """Show details of a single report."""

    model = Report
    template_name = 'reporting/report_detail.html'
    context_object_name = 'report'

    def get_queryset(self):
        user = self.request.user
        qs = Report.objects.select_related(
            'award', 'template', 'submitted_by', 'reviewed_by',
        )
        if user.is_superuser or user.role == 'system_admin':
            return qs
        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)
        return qs.filter(award__recipient=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = self.object.documents.all()
        return context


# ---------------------------------------------------------------------------
# Report Submit  (POST only)
# ---------------------------------------------------------------------------
class ReportSubmitView(LoginRequiredMixin, View):
    """POST-only endpoint to submit a report for review."""

    http_method_names = ['post']

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)

        if report.status not in (Report.Status.DRAFT, Report.Status.REVISION_REQUESTED):
            return JsonResponse(
                {'error': _('Only draft or revision-requested reports can be submitted.')},
                status=400,
            )

        report.status = Report.Status.SUBMITTED
        report.submitted_by = request.user
        report.submitted_at = timezone.now()
        report.save(update_fields=[
            'status', 'submitted_by', 'submitted_at', 'updated_at',
        ])

        log_audit(
            user=request.user,
            action=AuditLog.Action.SUBMIT,
            entity_type='Report',
            entity_id=str(report.pk),
            description=f'Report "{report}" submitted for review.',
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('Report submitted successfully.'))
        return JsonResponse({
            'status': report.get_status_display(),
            'submitted_at': report.submitted_at.isoformat(),
        })


# ---------------------------------------------------------------------------
# SF-425 Generate
# ---------------------------------------------------------------------------
class SF425GenerateView(AgencyStaffRequiredMixin, TemplateView):
    """Generate an SF-425 Federal Financial Report for an award.

    Collects financial data from the award's transactions and drawdowns
    and renders the SF-425 template.
    """

    template_name = 'reporting/sf425.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        award = get_object_or_404(
            Award.objects.select_related(
                'grant_program', 'agency', 'recipient', 'organization',
            ),
            pk=self.kwargs['award_id'],
        )

        # Aggregate financial data for the SF-425
        transactions = award.transactions.all()
        federal_expenditures = (
            transactions.filter(transaction_type='drawdown')
            .aggregate(total=Sum('amount'))['total']
            or 0
        )
        federal_cash_receipts = (
            transactions.filter(transaction_type='payment')
            .aggregate(total=Sum('amount'))['total']
            or 0
        )

        context['award'] = award
        context['federal_expenditures'] = federal_expenditures
        context['federal_cash_receipts'] = federal_cash_receipts
        context['remaining_federal_funds'] = award.award_amount - federal_expenditures
        context['sf425_reports'] = award.sf425_reports.all()
        return context


# ---------------------------------------------------------------------------
# Report Update
# ---------------------------------------------------------------------------
class ReportUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing report (only draft or revision-requested)."""

    model = Report
    form_class = ReportForm
    template_name = 'reporting/report_form.html'

    def get_queryset(self):
        return Report.objects.filter(
            status__in=(Report.Status.DRAFT, Report.Status.REVISION_REQUESTED),
        ).select_related('award')

    def form_valid(self, form):
        messages.success(self.request, _('Report updated successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.object.award
        return context

    def get_success_url(self):
        return reverse_lazy('reporting:detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Report Review  (POST only)
# ---------------------------------------------------------------------------
class ReportReviewView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to approve or request revision of a report."""

    http_method_names = ['post']

    def post(self, request, pk):
        report = get_object_or_404(Report, pk=pk)

        if report.status not in (Report.Status.SUBMITTED, Report.Status.UNDER_REVIEW):
            messages.error(request, _('This report cannot be reviewed in its current state.'))
            return redirect('reporting:detail', pk=report.pk)

        action = request.POST.get('action')
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.reviewer_comments = request.POST.get('comments', '')

        if action == 'approve':
            report.status = Report.Status.APPROVED
            audit_action = AuditLog.Action.APPROVE
            audit_desc = f'Report "{report}" approved.'
            messages.success(request, _('Report approved.'))
        elif action == 'revision':
            report.status = Report.Status.REVISION_REQUESTED
            audit_action = AuditLog.Action.REJECT
            audit_desc = f'Report "{report}" returned for revision.'
            messages.success(request, _('Revision requested.'))
        elif action == 'reject':
            report.status = Report.Status.REJECTED
            audit_action = AuditLog.Action.REJECT
            audit_desc = f'Report "{report}" rejected.'
            messages.success(request, _('Report rejected.'))
        else:
            messages.error(request, _('Invalid review action.'))
            return redirect('reporting:detail', pk=report.pk)

        report.save()
        notify_report_review_complete(report, action)

        log_audit(
            user=request.user,
            action=audit_action,
            entity_type='Report',
            entity_id=str(report.pk),
            description=audit_desc,
            ip_address=getattr(request, 'audit_ip', None),
        )

        return redirect('reporting:detail', pk=report.pk)


# ---------------------------------------------------------------------------
# SF-425 Submit  (POST only)
# ---------------------------------------------------------------------------
class SF425SubmitView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to submit an SF-425 report."""

    http_method_names = ['post']

    def post(self, request, pk):
        sf425 = get_object_or_404(SF425Report, pk=pk)

        if sf425.status != SF425Report.Status.DRAFT:
            messages.error(request, _('Only draft SF-425 reports can be submitted.'))
            return redirect('reporting:sf425', award_id=sf425.award_id)

        sf425.status = SF425Report.Status.SUBMITTED
        sf425.submitted_at = timezone.now()
        sf425.save(update_fields=['status', 'submitted_at'])

        messages.success(request, _('SF-425 report submitted.'))
        return redirect('reporting:sf425', award_id=sf425.award_id)


# ---------------------------------------------------------------------------
# SF-425 Approve  (POST only)
# ---------------------------------------------------------------------------
class SF425ApproveView(GrantManagerRequiredMixin, View):
    """POST-only endpoint to approve an SF-425 report."""

    http_method_names = ['post']

    def post(self, request, pk):
        sf425 = get_object_or_404(SF425Report, pk=pk)

        if sf425.status != SF425Report.Status.SUBMITTED:
            messages.error(request, _('Only submitted SF-425 reports can be approved.'))
            return redirect('reporting:sf425', award_id=sf425.award_id)

        sf425.status = SF425Report.Status.APPROVED
        sf425.approved_by = request.user
        sf425.approved_at = timezone.now()
        sf425.save(update_fields=['status', 'approved_by', 'approved_at'])

        log_audit(
            user=request.user,
            action=AuditLog.Action.APPROVE,
            entity_type='SF425Report',
            entity_id=str(sf425.pk),
            description=f'SF-425 report for award "{sf425.award}" approved.',
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('SF-425 report approved.'))
        return redirect('reporting:sf425', award_id=sf425.award_id)
