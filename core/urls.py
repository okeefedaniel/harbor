from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from core.forms import LoginForm
from core import views

app_name = 'core'

urlpatterns = [
    path(
        'login/',
        LoginView.as_view(
            template_name='registration/login.html',
            authentication_form=LoginForm,
        ),
        name='login',
    ),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path(
        'organization/create/',
        views.OrganizationCreateView.as_view(),
        name='organization-create',
    ),
    path(
        'organization/edit/',
        views.OrganizationUpdateView.as_view(),
        name='organization-edit',
    ),
    path('demo-login/', views.DemoLoginView.as_view(), name='demo-login'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path(
        'users/<uuid:pk>/role/',
        views.UserRoleUpdateView.as_view(),
        name='user-role-edit',
    ),
    path(
        'users/<uuid:pk>/api-key/',
        views.user_api_key_update,
        name='user-api-key',
    ),
    path(
        'notifications/',
        views.NotificationListView.as_view(),
        name='notifications',
    ),
    path(
        'notifications/<uuid:pk>/read/',
        views.mark_notification_read,
        name='notification-read',
    ),
    path(
        'analytics/',
        views.AnalyticsDashboardView.as_view(),
        name='analytics',
    ),
    path(
        'calendar/',
        views.DeadlineCalendarView.as_view(),
        name='calendar',
    ),
    path(
        'map/',
        views.MapView.as_view(),
        name='map_view',
    ),
    path(
        'api/map-data/',
        views.MapDataAPIView.as_view(),
        name='map_data_api',
    ),
    path(
        'municipality/<str:municipality_name>/',
        views.MunicipalityDetailView.as_view(),
        name='municipality_detail',
    ),
]
