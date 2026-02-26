from django.urls import path

from core import batch as bulk_views

from . import views

app_name = 'applications'

urlpatterns = [
    path('', views.ApplicationListView.as_view(), name='list'),
    path('my/', views.MyApplicationsView.as_view(), name='my-applications'),
    path(
        'create/<uuid:grant_program_id>/',
        views.ApplicationCreateView.as_view(),
        name='create',
    ),
    path('<uuid:pk>/', views.ApplicationDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.ApplicationUpdateView.as_view(), name='update'),
    path('<uuid:pk>/submit/', views.ApplicationSubmitView.as_view(), name='submit'),
    path(
        '<uuid:pk>/withdraw/',
        views.ApplicationWithdrawView.as_view(),
        name='withdraw',
    ),
    path(
        '<uuid:pk>/comment/',
        views.AddCommentView.as_view(),
        name='add-comment',
    ),
    path(
        '<uuid:pk>/upload/',
        views.UploadDocumentView.as_view(),
        name='upload-document',
    ),
    # Staff due-diligence endpoints
    path(
        '<uuid:pk>/status-change/',
        views.ApplicationStatusChangeView.as_view(),
        name='status-change',
    ),
    path(
        '<uuid:pk>/compliance/<uuid:item_pk>/toggle/',
        views.ToggleComplianceView.as_view(),
        name='toggle-compliance',
    ),
    path(
        '<uuid:pk>/staff-upload/',
        views.UploadStaffDocumentView.as_view(),
        name='upload-staff-document',
    ),
    # Staff application assignments
    path('my-assignments/', views.MyAssignmentsView.as_view(), name='my-assignments'),
    path('<uuid:pk>/claim/', views.ClaimApplicationView.as_view(), name='claim'),
    path('<uuid:pk>/assign/', views.AssignApplicationView.as_view(), name='assign'),
    path(
        'assignments/<uuid:pk>/status/',
        views.UpdateAssignmentStatusView.as_view(),
        name='assignment-status',
    ),

    path(
        'bulk/status-change/',
        bulk_views.BulkApplicationStatusChangeView.as_view(),
        name='bulk-status-change',
    ),
]
