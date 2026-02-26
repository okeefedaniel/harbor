from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from awards.models import Award
from core.audit import log_audit
from core.mixins import AgencyStaffRequiredMixin, GrantManagerRequiredMixin, SortableListMixin
from core.models import AuditLog
from core.notifications import notify_closeout_initiated

from .forms import CloseoutChecklistForm, CloseoutDocumentForm, FundReturnForm
from .models import Closeout, CloseoutChecklist, CloseoutDocument, FundReturn


# ---------------------------------------------------------------------------
# Closeout List
# ---------------------------------------------------------------------------
class CloseoutListView(LoginRequiredMixin, SortableListMixin, ListView):
    """List all closeouts with filtering."""

    model = Closeout
    template_name = 'closeout/closeout_list.html'
    context_object_name = 'closeouts'
    paginate_by = 20

    sortable_fields = {
        'award': 'award__award_number',
        'status': 'status',
        'initiated_at': 'initiated_at',
    }
    default_sort = 'initiated_at'
    default_dir = 'desc'

    def get_queryset(self):
        qs = Closeout.objects.select_related(
            'award', 'award__grant_program', 'award__agency',
            'award__organization', 'initiated_by',
        )
        user = self.request.user
        if user.role != 'system_admin' and user.agency_id:
            qs = qs.filter(award__agency=user.agency)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Awards that need closeout (expired, no closeout record)
        context['awards_needing_closeout'] = Award.objects.filter(
            end_date__lt=timezone.now().date(),
            status__in=['active', 'executed'],
        ).exclude(
            closeout__isnull=False,
        ).select_related('grant_program', 'agency', 'organization')[:10]
        context['status_choices'] = Closeout.Status.choices
        return context


# ---------------------------------------------------------------------------
# Closeout Detail
# ---------------------------------------------------------------------------
class CloseoutDetailView(AgencyStaffRequiredMixin, DetailView):
    """Display the closeout record with checklist items, documents,
    and fund returns."""

    model = Closeout
    template_name = 'closeout/closeout_detail.html'
    context_object_name = 'closeout'

    def get_queryset(self):
        return Closeout.objects.select_related(
            'award', 'initiated_by', 'completed_by',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        closeout = self.object
        context['checklist_items'] = closeout.checklist_items.select_related(
            'completed_by',
        ).all()
        context['documents'] = closeout.documents.select_related(
            'uploaded_by',
        ).all()
        context['fund_returns'] = closeout.fund_returns.select_related(
            'processed_by',
        ).all()

        checklist_qs = context['checklist_items']
        context['total_count'] = checklist_qs.count()
        context['completed_count'] = checklist_qs.filter(is_completed=True).count()
        context['all_required_completed'] = not checklist_qs.filter(
            is_required=True, is_completed=False,
        ).exists()
        context['fund_returns_total'] = (
            context['fund_returns'].aggregate(total=Sum('amount'))['total'] or 0
        )
        return context


# ---------------------------------------------------------------------------
# Closeout Initiate  (POST only)
# ---------------------------------------------------------------------------
class CloseoutInitiateView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to initiate the closeout process for an award.

    Creates a Closeout record with default checklist items if one does
    not already exist.
    """

    http_method_names = ['post']

    # Standard checklist items created on initiation
    DEFAULT_CHECKLIST_ITEMS = [
        (_('Final Progress Report'), _('Submit the final progress report.'), True),
        (_('Final Fiscal Report'), _('Submit the final fiscal/financial report.'), True),
        (_('Equipment Inventory'), _('Complete and submit the equipment inventory.'), False),
        (_('Audit Resolution'), _('Resolve any outstanding audit findings.'), True),
        (_('Fund Return'), _('Return any unobligated funds to the agency.'), True),
        (_('Record Retention'), _('Confirm record-retention requirements are met.'), True),
    ]

    def post(self, request, award_id):
        award = get_object_or_404(Award, pk=award_id)

        # Prevent duplicate closeout records
        if hasattr(award, 'closeout'):
            return JsonResponse(
                {'error': _('A closeout record already exists for this award.')},
                status=400,
            )

        closeout = Closeout.objects.create(
            award=award,
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=request.user,
        )

        # Seed with default checklist items
        for item_name, description, required in self.DEFAULT_CHECKLIST_ITEMS:
            CloseoutChecklist.objects.create(
                closeout=closeout,
                item_name=item_name,
                item_description=description,
                is_required=required,
            )

        notify_closeout_initiated(closeout)

        log_audit(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity_type='Closeout',
            entity_id=str(closeout.pk),
            description=f'Closeout initiated for award "{award}".',
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('Closeout process initiated.'))
        return JsonResponse({
            'closeout_id': str(closeout.pk),
            'status': closeout.get_status_display(),
        })


# ---------------------------------------------------------------------------
# Closeout Checklist Update
# ---------------------------------------------------------------------------
class CloseoutChecklistUpdateView(AgencyStaffRequiredMixin, UpdateView):
    """Update a single checklist item (mark complete / add notes)."""

    model = CloseoutChecklist
    form_class = CloseoutChecklistForm
    template_name = 'closeout/checklist_form.html'
    context_object_name = 'checklist_item'

    def form_valid(self, form):
        item = form.instance
        if item.is_completed and not item.completed_at:
            item.completed_by = self.request.user
            item.completed_at = timezone.now()
        elif not item.is_completed:
            item.completed_by = None
            item.completed_at = None

        messages.success(self.request, _('Checklist item updated.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy(
            'closeout:detail', kwargs={'pk': self.object.closeout_id}
        )


# ---------------------------------------------------------------------------
# Fund Return Create
# ---------------------------------------------------------------------------
class FundReturnCreateView(AgencyStaffRequiredMixin, CreateView):
    """Record a fund return during the closeout process."""

    model = FundReturn
    form_class = FundReturnForm
    template_name = 'closeout/fund_return_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.closeout = get_object_or_404(Closeout, pk=kwargs['closeout_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.closeout = self.closeout
        messages.success(self.request, _('Fund return recorded successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['closeout'] = self.closeout
        return context

    def get_success_url(self):
        return reverse_lazy(
            'closeout:detail', kwargs={'pk': self.closeout.pk}
        )


# ---------------------------------------------------------------------------
# Checklist Toggle  (POST only)
# ---------------------------------------------------------------------------
class CloseoutChecklistToggleView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to toggle a checklist item's completion status."""

    http_method_names = ['post']

    def post(self, request, pk):
        item = get_object_or_404(CloseoutChecklist, pk=pk)

        if item.is_completed:
            item.is_completed = False
            item.completed_by = None
            item.completed_at = None
        else:
            item.is_completed = True
            item.completed_by = request.user
            item.completed_at = timezone.now()

        item.save()
        messages.success(request, _('Checklist item updated.'))
        return redirect('closeout:detail', pk=item.closeout_id)


# ---------------------------------------------------------------------------
# Closeout Document Upload
# ---------------------------------------------------------------------------
class CloseoutDocumentUploadView(AgencyStaffRequiredMixin, CreateView):
    """Upload a document as part of the closeout process."""

    model = CloseoutDocument
    form_class = CloseoutDocumentForm
    template_name = 'closeout/document_upload_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.closeout = get_object_or_404(Closeout, pk=kwargs['closeout_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.closeout = self.closeout
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, _('Document uploaded successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['closeout'] = self.closeout
        return context

    def get_success_url(self):
        return reverse_lazy(
            'closeout:detail', kwargs={'pk': self.closeout.pk}
        )


# ---------------------------------------------------------------------------
# Closeout Complete  (POST only)
# ---------------------------------------------------------------------------
class CloseoutCompleteView(GrantManagerRequiredMixin, View):
    """POST-only endpoint to mark a closeout as completed."""

    http_method_names = ['post']

    def post(self, request, pk):
        closeout = get_object_or_404(Closeout, pk=pk)

        # Verify all required checklist items are completed
        required_incomplete = closeout.checklist_items.filter(
            is_required=True, is_completed=False,
        ).exists()

        if required_incomplete:
            messages.error(
                request,
                _('All required checklist items must be completed before '
                  'the closeout can be finalized.'),
            )
            return redirect('closeout:detail', pk=closeout.pk)

        closeout.status = Closeout.Status.COMPLETED
        closeout.completed_at = timezone.now()
        closeout.completed_by = request.user
        closeout.save()

        # Also mark the associated award as completed
        award = closeout.award
        award.status = Award.Status.COMPLETED
        award.save(update_fields=['status', 'updated_at'])

        log_audit(
            user=request.user,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Closeout',
            entity_id=str(closeout.pk),
            description=f'Closeout for award "{closeout.award}" completed.',
            changes={'old_status': 'in_progress', 'new_status': 'completed'},
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('Closeout completed successfully.'))
        return redirect('closeout:detail', pk=closeout.pk)
