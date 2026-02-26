from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('', views.ReviewDashboardView.as_view(), name='dashboard'),
    path(
        'application/<uuid:pk>/',
        views.ReviewApplicationView.as_view(),
        name='review-application',
    ),
    path(
        'application/<uuid:pk>/submit/',
        views.SubmitReviewView.as_view(),
        name='submit-review',
    ),
    path(
        'application/<uuid:pk>/summary/',
        views.ReviewSummaryView.as_view(),
        name='summary',
    ),
    path(
        'assign/<uuid:application_pk>/',
        views.ReviewAssignmentCreateView.as_view(),
        name='assign',
    ),
]
