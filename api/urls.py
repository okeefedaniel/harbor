"""
URL configuration for the Grantify REST API.

All endpoints are registered through a DRF ``DefaultRouter`` and served
under the ``/api/`` prefix (configured in the project-level ``urls.py``).
"""

from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

router.register(r'grant-programs', views.GrantProgramViewSet, basename='grantprogram')
router.register(r'applications', views.ApplicationViewSet, basename='application')
router.register(r'awards', views.AwardViewSet, basename='award')
router.register(r'drawdown-requests', views.DrawdownRequestViewSet, basename='drawdownrequest')
router.register(r'transactions', views.TransactionViewSet, basename='transaction')
router.register(r'budgets', views.BudgetViewSet, basename='budget')
router.register(r'reports', views.ReportViewSet, basename='report')
router.register(r'organizations', views.OrganizationViewSet, basename='organization')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'audit-logs', views.AuditLogViewSet, basename='auditlog')

urlpatterns = router.urls
