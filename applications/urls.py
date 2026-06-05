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
    # CSO 2026-06-03 HIGH F-001: gated /media/ access for attachments.
    # Templates link via {% url 'applications:attachment-download' att.pk %}
    # instead of {{ doc.file.url }}.
    path(
        'attachment/<uuid:pk>/download/',
        views.AttachmentDownloadView.as_view(),
        name='attachment-download',
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

    # Wave 6: collaborator endpoints sized for shared keel/components partials.
    # Distinct from the reviewer-assignment endpoints above per Codex finding #9.
    path(
        '<uuid:pk>/collaborators/invite/',
        views.InviteApplicationCollaboratorView.as_view(),
        name='collaborator-invite',
    ),
    path(
        '<uuid:pk>/collaborators/remove/',
        views.RemoveApplicationCollaboratorView.as_view(),
        name='collaborator-remove',
    ),
]
