"""
URL configuration for the Harbor REST API.

All endpoints are registered through a DRF ``DefaultRouter`` and served
under the ``/api/`` prefix (configured in the project-level ``urls.py``).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .audit_feed import harbor_audit_feed
from .helm_activity import harbor_helm_activity
from .helm_feed import harbor_helm_feed
from .helm_inbox import harbor_helm_feed_inbox

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

urlpatterns = [
    # Bounty → Harbor federal opportunity intake
    path('federal-intake/', views.FederalIntakeView.as_view(), name='federal-intake'),
    # Helm executive dashboard feed
    path('v1/helm-feed/', harbor_helm_feed, name='helm-feed'),
    path('v1/helm-feed/inbox/', harbor_helm_feed_inbox, name='helm-feed-inbox'),
    path('v1/helm-feed/activity/', harbor_helm_activity, name='helm-feed-activity'),
    path('v1/audit-feed/', harbor_audit_feed, name='audit-feed'),
    # keel.ops canary — JSON metrics for external pollers (4 flag chips +
    # counters). Auth: staff session OR Authorization: Bearer
    # HARBOR_METRICS_TOKEN (resolves via KEEL_METRICS_TOKEN setting).
    path('v1/metrics/', include('keel.ops.urls')),
] + router.urls
