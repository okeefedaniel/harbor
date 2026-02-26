from django.urls import path

from core import batch as bulk_views

from . import views

app_name = 'financial'

urlpatterns = [
    path(
        'budgets/<uuid:pk>/',
        views.BudgetDetailView.as_view(),
        name='budget-detail',
    ),
    path(
        'budgets/create/<uuid:award_id>/',
        views.BudgetCreateView.as_view(),
        name='budget-create',
    ),
    path(
        'budgets/<uuid:pk>/edit/',
        views.BudgetUpdateView.as_view(),
        name='budget-edit',
    ),
    path(
        'budgets/<uuid:budget_id>/lineitem/',
        views.BudgetLineItemCreateView.as_view(),
        name='lineitem-create',
    ),
    path('drawdowns/', views.DrawdownListView.as_view(), name='drawdown-list'),
    path(
        'drawdowns/create/<uuid:award_id>/',
        views.DrawdownCreateView.as_view(),
        name='drawdown-create',
    ),
    path(
        'drawdowns/<uuid:pk>/',
        views.DrawdownDetailView.as_view(),
        name='drawdown-detail',
    ),
    path(
        'drawdowns/<uuid:pk>/edit/',
        views.DrawdownUpdateView.as_view(),
        name='drawdown-edit',
    ),
    path(
        'drawdowns/<uuid:pk>/approve/',
        views.DrawdownApproveView.as_view(),
        name='drawdown-approve',
    ),
    path(
        'drawdowns/<uuid:pk>/deny/',
        views.DrawdownDenyView.as_view(),
        name='drawdown-deny',
    ),
    path(
        'drawdowns/<uuid:pk>/return/',
        views.DrawdownReturnView.as_view(),
        name='drawdown-return',
    ),
    path(
        'transactions/',
        views.TransactionListView.as_view(),
        name='transaction-list',
    ),
    path(
        'transactions/create/<uuid:award_id>/',
        views.TransactionCreateView.as_view(),
        name='transaction-create',
    ),
    path(
        'awards/<uuid:award_id>/budget-vs-actual/',
        views.BudgetVsActualView.as_view(),
        name='budget-vs-actual',
    ),
    path(
        'drawdowns/bulk/approve/',
        bulk_views.BulkDrawdownApproveView.as_view(),
        name='bulk-drawdown-approve',
    ),
]
