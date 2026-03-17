from collections import defaultdict
from decimal import Decimal

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
from core.filters import DrawdownFilter, TransactionFilter
from core.mixins import AgencyStaffRequiredMixin, FiscalOfficerRequiredMixin, SortableListMixin
from core.models import AuditLog
from core.notifications import notify_drawdown_status_changed

from .forms import BudgetForm, BudgetLineItemForm, DrawdownRequestForm, TransactionForm
from .models import Budget, BudgetLineItem, DrawdownRequest, Transaction


# ---------------------------------------------------------------------------
# Budget Detail
# ---------------------------------------------------------------------------
class BudgetDetailView(AgencyStaffRequiredMixin, DetailView):
    """Show budget details including all line items."""

    model = Budget
    template_name = 'financial/budget_detail.html'
    context_object_name = 'budget'

    def get_queryset(self):
        return Budget.objects.select_related('award', 'approved_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['line_items'] = self.object.line_items.all()
        return context


# ---------------------------------------------------------------------------
# Budget Create
# ---------------------------------------------------------------------------
class BudgetCreateView(AgencyStaffRequiredMixin, CreateView):
    """Create a new budget for an award."""

    model = Budget
    form_class = BudgetForm
    template_name = 'financial/budget_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        messages.success(self.request, _('Budget created successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy('financial:budget-detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Drawdown List
# ---------------------------------------------------------------------------
class DrawdownListView(LoginRequiredMixin, SortableListMixin, CSVExportMixin, ListView):
    """List all drawdown requests visible to the current user."""

    model = DrawdownRequest
    template_name = 'financial/drawdown_list.html'
    context_object_name = 'drawdowns'
    paginate_by = 20
    csv_filename = 'drawdowns.csv'
    csv_columns = [
        (_lazy('Request Number'), 'request_number'),
        (_lazy('Award'), 'award.award_number'),
        (_lazy('Amount'), 'amount'),
        (_lazy('Status'), 'get_status_display'),
        (_lazy('Submitted By'), lambda o: o.submitted_by.get_full_name() if o.submitted_by else ''),
        (_lazy('Submitted At'), 'submitted_at'),
        (_lazy('Reviewed By'), lambda o: o.reviewed_by.get_full_name() if o.reviewed_by else ''),
    ]

    sortable_fields = {
        'request_number': 'request_number',
        'award': 'award__award_number',
        'amount': 'amount',
        'status': 'status',
        'submitted_at': 'submitted_at',
    }
    default_sort = 'submitted_at'
    default_dir = 'desc'

    def get_queryset(self):
        qs = DrawdownRequest.objects.select_related(
            'award', 'submitted_by', 'reviewed_by',
        )
        user = self.request.user
        if user.is_agency_staff and user.agency_id:
            qs = qs.filter(award__agency=user.agency)
        elif not user.is_agency_staff and user.role != 'system_admin':
            qs = qs.filter(submitted_by=user)

        self.filterset = DrawdownFilter(self.request.GET, queryset=qs)
        return self.apply_sorting(self.filterset.qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filterset
        return context


# ---------------------------------------------------------------------------
# Drawdown Create
# ---------------------------------------------------------------------------
class DrawdownCreateView(LoginRequiredMixin, CreateView):
    """Create a new drawdown request against an award."""

    model = DrawdownRequest
    form_class = DrawdownRequestForm
    template_name = 'financial/drawdown_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def _generate_request_number(self):
        """Generate a sequential request number for the award."""
        last = (
            DrawdownRequest.objects
            .filter(award=self.award)
            .order_by('-request_number')
            .values_list('request_number', flat=True)
            .first()
        )
        if last:
            try:
                seq = int(last.rsplit('-', 1)[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"DR-{self.award.award_number}-{seq:04d}"

    def form_valid(self, form):
        form.instance.award = self.award
        form.instance.submitted_by = self.request.user
        form.instance.request_number = self._generate_request_number()
        messages.success(self.request, _('Drawdown request created successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy(
            'financial:drawdown-detail', kwargs={'pk': self.object.pk}
        )


# ---------------------------------------------------------------------------
# Drawdown Detail
# ---------------------------------------------------------------------------
class DrawdownDetailView(LoginRequiredMixin, DetailView):
    """Show details of a single drawdown request."""

    model = DrawdownRequest
    template_name = 'financial/drawdown_detail.html'
    context_object_name = 'drawdown'

    def get_queryset(self):
        user = self.request.user
        qs = DrawdownRequest.objects.select_related(
            'award', 'submitted_by', 'reviewed_by',
        )
        if user.is_superuser or user.role == 'system_admin':
            return qs
        if user.is_agency_staff and user.agency:
            return qs.filter(award__agency=user.agency)
        return qs.filter(award__recipient=user)


# ---------------------------------------------------------------------------
# Drawdown Approve  (POST only)
# ---------------------------------------------------------------------------
class DrawdownApproveView(FiscalOfficerRequiredMixin, View):
    """POST-only endpoint to approve a drawdown request."""

    http_method_names = ['post']

    def post(self, request, pk):
        drawdown = get_object_or_404(DrawdownRequest, pk=pk)

        if drawdown.status != DrawdownRequest.Status.SUBMITTED:
            return JsonResponse(
                {'error': _('Only submitted drawdowns can be approved.')},
                status=400,
            )

        drawdown.status = DrawdownRequest.Status.APPROVED
        drawdown.reviewed_by = request.user
        drawdown.reviewed_at = timezone.now()
        drawdown.save(update_fields=[
            'status', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        notify_drawdown_status_changed(drawdown, drawdown.status)

        log_audit(
            user=request.user,
            action=AuditLog.Action.APPROVE,
            entity_type='DrawdownRequest',
            entity_id=str(drawdown.pk),
            description=f'Drawdown request "{drawdown.request_number}" approved.',
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('Drawdown request approved.'))
        return JsonResponse({
            'status': drawdown.get_status_display(),
            'reviewed_by': str(drawdown.reviewed_by),
        })


# ---------------------------------------------------------------------------
# Transaction List
# ---------------------------------------------------------------------------
class TransactionListView(AgencyStaffRequiredMixin, SortableListMixin, CSVExportMixin, ListView):
    """List financial transactions visible to the current user."""

    model = Transaction
    template_name = 'financial/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 25
    csv_filename = 'transactions.csv'
    csv_columns = [
        (_lazy('Transaction ID'), 'id'),
        (_lazy('Award'), 'award.award_number'),
        (_lazy('Type'), 'get_transaction_type_display'),
        (_lazy('Amount'), 'amount'),
        (_lazy('Description'), 'description'),
        (_lazy('Created By'), lambda o: o.created_by.get_full_name() if o.created_by else ''),
        (_lazy('Created At'), 'created_at'),
    ]

    sortable_fields = {
        'transaction_date': 'transaction_date',
        'transaction_type': 'transaction_type',
        'amount': 'amount',
        'reference_number': 'reference_number',
    }
    default_sort = 'transaction_date'
    default_dir = 'desc'

    def get_queryset(self):
        qs = Transaction.objects.select_related('award', 'created_by')
        user = self.request.user
        if user.is_agency_staff and user.agency_id:
            qs = qs.filter(award__agency=user.agency)
        elif not user.is_agency_staff and user.role != 'system_admin':
            qs = qs.filter(award__recipient=user)

        self.filterset = TransactionFilter(self.request.GET, queryset=qs)
        return self.apply_sorting(self.filterset.qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.filterset
        return context


# ---------------------------------------------------------------------------
# Budget Update
# ---------------------------------------------------------------------------
class BudgetUpdateView(AgencyStaffRequiredMixin, UpdateView):
    """Edit an existing budget."""

    model = Budget
    form_class = BudgetForm
    template_name = 'financial/budget_form.html'

    def get_queryset(self):
        return Budget.objects.select_related('award')

    def form_valid(self, form):
        messages.success(self.request, _('Budget updated successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.object.award
        return context

    def get_success_url(self):
        return reverse_lazy('financial:budget-detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Budget Line Item Create
# ---------------------------------------------------------------------------
class BudgetLineItemCreateView(LoginRequiredMixin, CreateView):
    """Add a line item to a budget."""

    model = BudgetLineItem
    form_class = BudgetLineItemForm
    template_name = 'financial/lineitem_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.budget = get_object_or_404(
            Budget.objects.select_related('award'), pk=kwargs['budget_id'],
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.budget = self.budget
        messages.success(self.request, _('Line item added successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['budget'] = self.budget
        return context

    def get_success_url(self):
        return reverse_lazy('financial:budget-detail', kwargs={'pk': self.budget.pk})


# ---------------------------------------------------------------------------
# Drawdown Update
# ---------------------------------------------------------------------------
class DrawdownUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing drawdown request (only draft status)."""

    model = DrawdownRequest
    form_class = DrawdownRequestForm
    template_name = 'financial/drawdown_form.html'

    def get_queryset(self):
        return DrawdownRequest.objects.filter(
            status=DrawdownRequest.Status.DRAFT,
        ).select_related('award')

    def form_valid(self, form):
        messages.success(self.request, _('Drawdown request updated.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.object.award
        return context

    def get_success_url(self):
        return reverse_lazy(
            'financial:drawdown-detail', kwargs={'pk': self.object.pk}
        )


# ---------------------------------------------------------------------------
# Drawdown Deny  (POST only)
# ---------------------------------------------------------------------------
class DrawdownDenyView(FiscalOfficerRequiredMixin, View):
    """POST-only endpoint to deny a drawdown request."""

    http_method_names = ['post']

    def post(self, request, pk):
        drawdown = get_object_or_404(DrawdownRequest, pk=pk)

        if drawdown.status not in (
            DrawdownRequest.Status.SUBMITTED,
            DrawdownRequest.Status.UNDER_REVIEW,
        ):
            messages.error(request, _('This drawdown cannot be denied in its current state.'))
            return redirect('financial:drawdown-detail', pk=drawdown.pk)

        drawdown.status = DrawdownRequest.Status.DENIED
        drawdown.reviewed_by = request.user
        drawdown.reviewed_at = timezone.now()
        drawdown.save(update_fields=[
            'status', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        notify_drawdown_status_changed(drawdown, drawdown.status)

        log_audit(
            user=request.user,
            action=AuditLog.Action.REJECT,
            entity_type='DrawdownRequest',
            entity_id=str(drawdown.pk),
            description=f'Drawdown request "{drawdown.request_number}" denied.',
            ip_address=getattr(request, 'audit_ip', None),
        )

        messages.success(request, _('Drawdown request denied.'))
        return redirect('financial:drawdown-detail', pk=drawdown.pk)


# ---------------------------------------------------------------------------
# Drawdown Return  (POST only)
# ---------------------------------------------------------------------------
class DrawdownReturnView(FiscalOfficerRequiredMixin, View):
    """POST-only endpoint to return a drawdown request for revision."""

    http_method_names = ['post']

    def post(self, request, pk):
        drawdown = get_object_or_404(DrawdownRequest, pk=pk)

        if drawdown.status not in (
            DrawdownRequest.Status.SUBMITTED,
            DrawdownRequest.Status.UNDER_REVIEW,
        ):
            messages.error(request, _('This drawdown cannot be returned in its current state.'))
            return redirect('financial:drawdown-detail', pk=drawdown.pk)

        drawdown.status = DrawdownRequest.Status.RETURNED
        drawdown.reviewed_by = request.user
        drawdown.reviewed_at = timezone.now()
        drawdown.save(update_fields=[
            'status', 'reviewed_by', 'reviewed_at', 'updated_at',
        ])

        notify_drawdown_status_changed(drawdown, drawdown.status)

        messages.success(request, _('Drawdown request returned for revision.'))
        return redirect('financial:drawdown-detail', pk=drawdown.pk)


# ---------------------------------------------------------------------------
# Transaction Create
# ---------------------------------------------------------------------------
class TransactionCreateView(FiscalOfficerRequiredMixin, CreateView):
    """Record a financial transaction for an award."""

    model = Transaction
    form_class = TransactionForm
    template_name = 'financial/transaction_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        form.instance.created_by = self.request.user
        messages.success(self.request, _('Transaction recorded successfully.'))
        response = super().form_valid(form)

        log_audit(
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            entity_type='Transaction',
            entity_id=str(self.object.pk),
            description=f'Transaction recorded for award "{self.award}".',
            ip_address=getattr(self.request, 'audit_ip', None),
        )

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy('financial:transaction-list')


# ---------------------------------------------------------------------------
# Budget vs Actual
# ---------------------------------------------------------------------------
class BudgetVsActualView(LoginRequiredMixin, TemplateView):
    """Compare budgeted amounts against actual spending per category."""

    template_name = 'financial/budget_vs_actual.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        award = get_object_or_404(
            Award.objects.select_related('grant_program', 'agency', 'organization'),
            pk=self.kwargs['award_id'],
        )
        context['award'] = award

        # Aggregate budget line items by category across all approved budgets
        budget_by_category = defaultdict(lambda: {
            'federal': Decimal('0'),
            'state': Decimal('0'),
            'match': Decimal('0'),
            'total': Decimal('0'),
        })

        line_items = BudgetLineItem.objects.filter(
            budget__award=award,
            budget__status__in=['approved', 'submitted', 'draft'],
        ).values('category').annotate(
            total_amount=Sum('amount'),
            total_federal=Sum('federal_share'),
            total_state=Sum('state_share'),
            total_match=Sum('match_share'),
        )

        for item in line_items:
            cat = item['category']
            budget_by_category[cat]['federal'] = item['total_federal'] or Decimal('0')
            budget_by_category[cat]['state'] = item['total_state'] or Decimal('0')
            budget_by_category[cat]['match'] = item['total_match'] or Decimal('0')
            budget_by_category[cat]['total'] = item['total_amount'] or Decimal('0')

        # Aggregate actual spending by category from transactions
        actual_by_category = defaultdict(Decimal)
        transactions = Transaction.objects.filter(
            award=award,
            transaction_type__in=['payment', 'drawdown'],
        )
        # Sum all transactions for total actual spent
        total_actual = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        # Build rows for the template
        category_choices = dict(BudgetLineItem.Category.choices)
        rows = []
        grand_budgeted_federal = Decimal('0')
        grand_budgeted_state = Decimal('0')
        grand_budgeted_match = Decimal('0')
        grand_budgeted_total = Decimal('0')
        grand_actual = Decimal('0')

        for cat_key, cat_label in BudgetLineItem.Category.choices:
            if cat_key not in budget_by_category:
                continue
            budgeted = budget_by_category[cat_key]
            # Proportional actual spending based on budget share
            if grand_budgeted_total == Decimal('0'):
                # Calculate grand total first
                for k in budget_by_category:
                    grand_budgeted_total += budget_by_category[k]['total']

            rows.append({
                'category': cat_label,
                'budgeted_federal': budgeted['federal'],
                'budgeted_state': budgeted['state'],
                'budgeted_match': budgeted['match'],
                'budgeted_total': budgeted['total'],
            })

        # Recalculate grand totals properly
        grand_budgeted_federal = Decimal('0')
        grand_budgeted_state = Decimal('0')
        grand_budgeted_match = Decimal('0')
        grand_budgeted_total = Decimal('0')

        for row in rows:
            grand_budgeted_federal += row['budgeted_federal']
            grand_budgeted_state += row['budgeted_state']
            grand_budgeted_match += row['budgeted_match']
            grand_budgeted_total += row['budgeted_total']

        # Distribute actual spending proportionally across categories
        for row in rows:
            if grand_budgeted_total > 0:
                proportion = row['budgeted_total'] / grand_budgeted_total
                row['actual_spent'] = (total_actual * proportion).quantize(Decimal('0.01'))
            else:
                row['actual_spent'] = Decimal('0')
            row['remaining'] = row['budgeted_total'] - row['actual_spent']
            if row['budgeted_total'] > 0:
                row['pct_used'] = int(
                    (row['actual_spent'] / row['budgeted_total']) * 100
                )
            else:
                row['pct_used'] = 0
            grand_actual += row['actual_spent']

        context['rows'] = rows
        context['grand_budgeted_federal'] = grand_budgeted_federal
        context['grand_budgeted_state'] = grand_budgeted_state
        context['grand_budgeted_match'] = grand_budgeted_match
        context['grand_budgeted_total'] = grand_budgeted_total
        context['grand_actual'] = grand_actual
        context['grand_remaining'] = grand_budgeted_total - grand_actual
        if grand_budgeted_total > 0:
            context['grand_pct_used'] = int(
                (grand_actual / grand_budgeted_total) * 100
            )
        else:
            context['grand_pct_used'] = 0

        return context
