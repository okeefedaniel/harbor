"""
Harbor URL Configuration
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import HttpResponse, JsonResponse

from core import views as core_views


def health_check(request):
    """Lightweight health check endpoint for Railway."""
    return JsonResponse({"status": "ok"})


def robots_txt(request):
    """Serve robots.txt as a plain text response."""
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /auth/",
        "Disallow: /accounts/",
        "Allow: /",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

from django.utils.translation import gettext_lazy as _

admin.site.site_header = _('Harbor Administration')
admin.site.site_title = _('Harbor Admin')
admin.site.index_title = _('Grants Management System')

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('', include('portal.urls')),
    path('auth/', include('core.urls')),
    path('accounts/', include('allauth.urls')),
    # Convenience named URL for the "Sign in with Microsoft" button
    path(
        'auth/sso/microsoft/',
        RedirectView.as_view(url='/accounts/microsoft/login/?process=login', query_string=False),
        name='microsoft_login',
    ),
    path('dashboard/', core_views.DashboardView.as_view(), name='dashboard'),
    path('grants/', include('grants.urls')),
    path('applications/', include('applications.urls')),
    path('reviews/', include('reviews.urls')),
    path('awards/', include('awards.urls')),
    path('financial/', include('financial.urls')),
    path('reporting/', include('reporting.urls')),
    path('closeout/', include('closeout.urls')),
    path('signatures/', include('signatures.urls')),
    path('api/', include('api.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
