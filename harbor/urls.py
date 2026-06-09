"""
Harbor URL Configuration
"""
from django.contrib import admin
from django.contrib.auth.views import LoginView
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import views as core_views
from keel.accounts.forms import LoginForm
from keel.accounts.views import (
    accept_invitation,
    accept_invitation_complete,
    accept_invitation_signout,
)
from keel.core.views import health_check, robots_txt, favicon_view, SuiteLogoutView
from keel.core.demo import demo_login_view
from keel.core.search_views import search_view

from django.utils.translation import gettext_lazy as _

admin.site.site_header = _('Harbor Administration')
admin.site.site_title = _('Harbor Admin')
admin.site.index_title = _('Grants Management System')

urlpatterns = [
    path('demo-login/', demo_login_view, name='demo_login'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('favicon.ico', favicon_view, name='favicon'),
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('', include('portal.urls')),
    # Canonical login lives at /accounts/login/. The legacy /auth/login/
    # path is preserved as a 301 to keep old bookmarks and inbound links
    # working. Pattern is mounted BEFORE the auth/ include so it wins
    # the resolver match. (ISSUE-019)
    path(
        'auth/login/',
        RedirectView.as_view(url='/accounts/login/', permanent=True),
    ),
    path('auth/', include('core.urls')),
    # Override allauth's bare LoginView at /accounts/login/ with the shared
    # keel LoginForm so the input fields render with Bootstrap styling.
    # Mounted before the allauth include so it shadows allauth's default.
    path('accounts/login/', LoginView.as_view(
        template_name='account/login.html',
        authentication_form=LoginForm,
    ), name='account_login'),
    path('accounts/logout/', SuiteLogoutView.as_view(), name='account_logout'),
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
    path('notifications/', include('keel.notifications.urls')),
    path('settings/', include('keel.settings.urls')),
    path('activity/', include('keel.activity.urls')),
    # keel.scheduling — staff-only registry + run-log dashboard for scheduled mgmt commands.
    path('scheduling/', include('keel.scheduling.urls')),
    path('api/', include('api.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('search/', search_view, name='search'),
    path('keel/requests/', include('keel.requests.urls')),
    path('keel/signatures/', include('keel.signatures.urls')),
    path('keel/mentions/', include('keel.mentions.urls')),
    path('keel/', include('keel.core.foia_urls')),
    # Invitation acceptance lives at /invite/ for clean URLs — the keel
    # package's urls.py docstring instructs consumers to mount this at
    # the top level. Without it, links built by
    # keel.accounts.views.send_invitation via
    # request.build_absolute_uri('/invite/<token>/') 404 on this host.
    path('invite/<str:token>/', accept_invitation, name='accept_invitation'),
    path('invite/<str:token>/sign-out/', accept_invitation_signout, name='accept_invitation_signout'),
    path('invite/<str:token>/complete/', accept_invitation_complete, name='accept_invitation_complete'),
    path('keel/', include('keel.accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
