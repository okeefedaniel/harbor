"""
FilterSet classes for django-filter integration across Beacon apps.

Provides full-text search and advanced filtering for all list views.
"""
import django_filters

from applications.models import Application
from awards.models import Award, AwardAmendment
from financial.models import DrawdownRequest, Transaction
from grants.models import GrantProgram
from reporting.models import Report


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
class ApplicationFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_search', label='Search')
    grant_program = django_filters.ModelChoiceFilter(
        queryset=GrantProgram.objects.all(),
        label='Grant Program',
    )
    status = django_filters.ChoiceFilter(choices=Application.Status.choices)
    submitted_after = django_filters.DateFilter(
        field_name='submitted_at', lookup_expr='gte', label='Submitted After',
    )
    submitted_before = django_filters.DateFilter(
        field_name='submitted_at', lookup_expr='lte', label='Submitted Before',
    )
    min_amount = django_filters.NumberFilter(
        field_name='requested_amount', lookup_expr='gte', label='Min Amount',
    )
    max_amount = django_filters.NumberFilter(
        field_name='requested_amount', lookup_expr='lte', label='Max Amount',
    )

    class Meta:
        model = Application
        fields = ['grant_program', 'status']

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(project_title__icontains=value)
            | Q(applicant__first_name__icontains=value)
            | Q(applicant__last_name__icontains=value)
            | Q(applicant__username__icontains=value)
            | Q(organization__name__icontains=value)
            | Q(id__icontains=value)
        )


# ---------------------------------------------------------------------------
# Awards
# ---------------------------------------------------------------------------
class AwardFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_search', label='Search')
    status = django_filters.MultipleChoiceFilter(choices=Award.Status.choices)
    agency = django_filters.ModelChoiceFilter(
        queryset=None,  # set in __init__
        label='Agency',
    )
    min_amount = django_filters.NumberFilter(
        field_name='award_amount', lookup_expr='gte', label='Min Amount',
    )
    max_amount = django_filters.NumberFilter(
        field_name='award_amount', lookup_expr='lte', label='Max Amount',
    )

    class Meta:
        model = Award
        fields = ['status', 'agency']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import Agency
        self.filters['agency'].queryset = Agency.objects.filter(is_active=True)

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(award_number__icontains=value)
            | Q(title__icontains=value)
            | Q(recipient__first_name__icontains=value)
            | Q(recipient__last_name__icontains=value)
            | Q(organization__name__icontains=value)
        )


# ---------------------------------------------------------------------------
# Drawdowns
# ---------------------------------------------------------------------------
class DrawdownFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=DrawdownRequest.Status.choices)
    award = django_filters.CharFilter(
        field_name='award__award_number', lookup_expr='icontains', label='Award #',
    )

    class Meta:
        model = DrawdownRequest
        fields = ['status']


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------
class TransactionFilter(django_filters.FilterSet):
    transaction_type = django_filters.ChoiceFilter(
        choices=Transaction.TransactionType.choices,
    )
    award = django_filters.CharFilter(
        field_name='award__award_number', lookup_expr='icontains', label='Award #',
    )
    min_amount = django_filters.NumberFilter(
        field_name='amount', lookup_expr='gte', label='Min Amount',
    )
    max_amount = django_filters.NumberFilter(
        field_name='amount', lookup_expr='lte', label='Max Amount',
    )

    class Meta:
        model = Transaction
        fields = ['transaction_type']


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class ReportFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Report.Status.choices)
    report_type = django_filters.ChoiceFilter(choices=Report.ReportType.choices)
    overdue = django_filters.BooleanFilter(method='filter_overdue', label='Overdue Only')

    class Meta:
        model = Report
        fields = ['status', 'report_type']

    def filter_overdue(self, queryset, name, value):
        if value:
            from django.utils import timezone
            return queryset.filter(
                due_date__lt=timezone.now().date(),
            ).exclude(
                status__in=['approved', 'submitted', 'under_review'],
            )
        return queryset


# ---------------------------------------------------------------------------
# Grant Programs
# ---------------------------------------------------------------------------
class GrantProgramFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_search', label='Search')
    grant_type = django_filters.ChoiceFilter(choices=GrantProgram.GrantType.choices)
    status = django_filters.ChoiceFilter(choices=GrantProgram.Status.choices)

    class Meta:
        model = GrantProgram
        fields = ['grant_type', 'status']

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(agency__name__icontains=value)
        )
