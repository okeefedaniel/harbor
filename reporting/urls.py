from django.urls import path

from . import views

app_name = 'reporting'

urlpatterns = [
    path('', views.ReportListView.as_view(), name='list'),
    path(
        'create/<uuid:award_id>/',
        views.ReportCreateView.as_view(),
        name='create',
    ),
    path('<uuid:pk>/', views.ReportDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.ReportUpdateView.as_view(), name='edit'),
    path('<uuid:pk>/submit/', views.ReportSubmitView.as_view(), name='submit'),
    path('<uuid:pk>/review/', views.ReportReviewView.as_view(), name='review'),
    path(
        'sf425/<uuid:award_id>/',
        views.SF425GenerateView.as_view(),
        name='sf425',
    ),
    path(
        'sf425/<uuid:pk>/submit/',
        views.SF425SubmitView.as_view(),
        name='sf425-submit',
    ),
    path(
        'sf425/<uuid:pk>/approve/',
        views.SF425ApproveView.as_view(),
        name='sf425-approve',
    ),
]
