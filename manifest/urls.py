"""Manifest standalone URL configuration."""
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from keel.core.views import health_check, robots_txt
from keel.core.demo import demo_login_view


urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('health/', health_check),
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view(template_name='manifest/login.html'), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('demo-login/', demo_login_view, name='demo_login'),
    path('notifications/', include('keel.notifications.urls')),
    path('', include('signatures.urls')),
    path('keel/requests/', include('keel.requests.urls')),
    path('keel/', include('keel.core.foia_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
