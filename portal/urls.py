from django.urls import path

from . import views

app_name = 'portal'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('opportunities/', views.OpportunityListView.as_view(), name='opportunities'),
    path(
        'opportunities/<uuid:pk>/',
        views.OpportunityDetailView.as_view(),
        name='opportunity-detail',
    ),
    path(
        'federal-opportunities/',
        views.FederalOpportunityListView.as_view(),
        name='federal-opportunities',
    ),
    path(
        'federal-opportunities/<int:pk>/',
        views.FederalOpportunityDetailView.as_view(),
        name='federal-opportunity-detail',
    ),
    path('about/', views.AboutView.as_view(), name='about'),
    path('help/', views.HelpView.as_view(), name='help'),
    path('manual/', views.UserManualView.as_view(), name='manual'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
    path('support/', views.SupportView.as_view(), name='support'),
    path('demo/', views.DemoGuideView.as_view(), name='demo'),
]
