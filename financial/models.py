import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------
class Budget(models.Model):
    """Fiscal-year budget for an award."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        APPROVED = 'approved', _('Approved')
        REVISION_REQUESTED = 'revision_requested', _('Revision Requested')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='budgets',
    )
    fiscal_year = models.IntegerField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_budgets',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['award', '-fiscal_year']
        verbose_name = _('Budget')
        verbose_name_plural = _('Budgets')

    def __str__(self):
        return f"{self.award} - FY{self.fiscal_year}"


# ---------------------------------------------------------------------------
# BudgetLineItem
# ---------------------------------------------------------------------------
class BudgetLineItem(models.Model):
    """Individual line item within a budget."""

    class Category(models.TextChoices):
        PERSONNEL = 'personnel', _('Personnel')
        FRINGE = 'fringe', _('Fringe Benefits')
        TRAVEL = 'travel', _('Travel')
        EQUIPMENT = 'equipment', _('Equipment')
        SUPPLIES = 'supplies', _('Supplies')
        CONTRACTUAL = 'contractual', _('Contractual')
        CONSTRUCTION = 'construction', _('Construction')
        INDIRECT = 'indirect', _('Indirect Costs')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name='line_items',
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    federal_share = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    state_share = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    match_share = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Budget Line Item')
        verbose_name_plural = _('Budget Line Items')

    def __str__(self):
        return f"{self.budget} - {self.get_category_display()}: {self.description[:50]}"


# ---------------------------------------------------------------------------
# DrawdownRequest
# ---------------------------------------------------------------------------
class DrawdownRequest(models.Model):
    """Cash request from a subrecipient against an award."""

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        UNDER_REVIEW = 'under_review', _('Under Review')
        APPROVED = 'approved', _('Approved')
        PAID = 'paid', _('Paid')
        DENIED = 'denied', _('Denied')
        RETURNED = 'returned', _('Returned')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='drawdown_requests',
    )
    request_number = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    description = models.TextField(blank=True)
    expenditure_details = models.JSONField(default=dict, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submitted_drawdowns',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_drawdowns',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Drawdown Request')
        verbose_name_plural = _('Drawdown Requests')

    def __str__(self):
        return f"{self.award} - Drawdown #{self.request_number}"


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------
class Transaction(models.Model):
    """Financial transaction record for an award."""

    class TransactionType(models.TextChoices):
        OBLIGATION = 'obligation', _('Obligation')
        DRAWDOWN = 'drawdown', _('Drawdown')
        PAYMENT = 'payment', _('Payment')
        REFUND = 'refund', _('Refund')
        ADJUSTMENT = 'adjustment', _('Adjustment')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    transaction_type = models.CharField(
        max_length=15,
        choices=TransactionType.choices,
    )
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True)
    reference_number = models.CharField(max_length=100, blank=True)
    core_ct_reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('State ERP Reference'),
        help_text=_('Reference ID from the state enterprise financial system.'),
    )
    transaction_date = models.DateField(db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_transactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')

    def __str__(self):
        return (
            f"{self.award} - {self.get_transaction_type_display()} "
            f"${self.amount} ({self.transaction_date})"
        )


# ---------------------------------------------------------------------------
# CoreCTAccountString
# ---------------------------------------------------------------------------
class CoreCTAccountString(models.Model):
    """
    Maps an award to its state ERP accounting string.

    The state Enterprise Resource Planning (ERP) system is the state's
    financial system. The account string segments correspond to the
    chartfield structure for budget coding and financial reporting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    award = models.ForeignKey(
        'awards.Award',
        on_delete=models.CASCADE,
        related_name='account_strings',
    )
    fund = models.CharField(max_length=5, verbose_name=_('Fund'))
    department = models.CharField(max_length=8, verbose_name=_('Department'))
    sid = models.CharField(max_length=5, verbose_name=_('SID'))
    program = models.CharField(max_length=5, verbose_name=_('Program'))
    account = models.CharField(max_length=5, verbose_name=_('Account'))
    chartfield1 = models.CharField(
        max_length=6, blank=True, verbose_name=_('Chartfield 1'),
    )
    chartfield2 = models.CharField(
        max_length=8, blank=True, verbose_name=_('Chartfield 2'),
    )
    budget_ref_year = models.CharField(
        max_length=4, blank=True, verbose_name=_('Budget Ref Year'),
    )
    project = models.CharField(max_length=15, blank=True, verbose_name=_('Project'))

    class Meta:
        verbose_name = _('State ERP Account String')
        verbose_name_plural = _('State ERP Account Strings')

    def __str__(self):
        return (
            f"{self.fund}-{self.department}-{self.sid}-"
            f"{self.program}-{self.account}"
        )
