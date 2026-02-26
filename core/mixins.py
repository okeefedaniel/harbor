"""
Permission mixins for role-based access control and reusable view utilities.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models.expressions import BaseExpression


class AgencyStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to agency staff (system_admin, agency_admin, program_officer, fiscal_officer)."""

    def test_func(self):
        return self.request.user.is_agency_staff


class GrantManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to users who can manage grants (system_admin, agency_admin, program_officer)."""

    def test_func(self):
        return self.request.user.can_manage_grants


class ReviewerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to users who can review applications."""

    def test_func(self):
        return self.request.user.can_review


class ApplicantRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to applicant users."""

    def test_func(self):
        return self.request.user.role == 'applicant'


class FiscalOfficerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to fiscal officers or above."""

    def test_func(self):
        return self.request.user.role in ('fiscal_officer', 'agency_admin', 'system_admin')


class FederalCoordinatorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to users who can manage federal funding opportunities."""

    def test_func(self):
        return self.request.user.can_manage_federal


class AgencyObjectMixin:
    """Mixin that filters querysets by the user's agency for non-system-admins.

    Override ``get_agency_field()`` to specify the agency field path (default: 'agency').
    """

    def get_agency_field(self):
        return 'agency'

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role != 'system_admin' and user.agency_id:
            qs = qs.filter(**{self.get_agency_field(): user.agency})
        return qs


class SortableListMixin:
    """Add server-side column sorting to any ListView.

    Define ``sortable_fields`` as a dict mapping URL param names to either:
    - A string model field path for ``.order_by()`` (e.g. ``'title'``,
      ``'agency__name'``)
    - A Django ORM expression (e.g. ``Case/When``) for non-trivial ordering

    Views that override ``get_queryset()`` should call
    ``self.apply_sorting(qs)`` as the last step before returning.

    Template context provided:
    - ``current_sort``, ``current_dir`` — active sort state
    - ``filter_params`` — query string (sans sort/dir/page) for sort links
    - ``pagination_params`` — query string (sans page) for pagination links
    """

    sortable_fields = {}
    default_sort = ''
    default_dir = 'asc'

    def get_sort_params(self):
        sort = self.request.GET.get('sort', self.default_sort)
        direction = self.request.GET.get('dir', self.default_dir)
        if sort not in self.sortable_fields:
            sort = self.default_sort
        if direction not in ('asc', 'desc'):
            direction = self.default_dir
        return sort, direction

    def apply_sorting(self, qs):
        """Apply column sorting to the queryset."""
        sort, direction = self.get_sort_params()
        if not sort:
            return qs
        field = self.sortable_fields[sort]
        if isinstance(field, BaseExpression):
            alias = f'_sort_{sort}'
            qs = qs.annotate(**{alias: field})
            order_field = alias
        else:
            order_field = field
        if direction == 'desc':
            order_field = f'-{order_field}'
        return qs.order_by(order_field)

    def get_queryset(self):
        """Default: apply sorting to the parent queryset."""
        return self.apply_sorting(super().get_queryset())

    def _build_params(self, exclude):
        parts = []
        for key in self.request.GET:
            if key not in exclude:
                for val in self.request.GET.getlist(key):
                    parts.append(f'{key}={val}')
        return '&'.join(parts)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sort, direction = self.get_sort_params()
        ctx['current_sort'] = sort
        ctx['current_dir'] = direction
        ctx['filter_params'] = self._build_params({'sort', 'dir', 'page'})
        ctx['pagination_params'] = self._build_params({'page'})
        return ctx
