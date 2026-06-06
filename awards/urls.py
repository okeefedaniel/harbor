from django.urls import path

from core import batch as bulk_views

from . import views

app_name = 'awards'

urlpatterns = [
    path('', views.AwardListView.as_view(), name='list'),
    path('my/', views.MyAwardsView.as_view(), name='my-awards'),
    path(
        'create/<uuid:application_id>/',
        views.AwardCreateView.as_view(),
        name='create',
    ),
    path('<uuid:pk>/', views.AwardDetailView.as_view(), name='detail'),
    path('<uuid:pk>/edit/', views.AwardUpdateView.as_view(), name='edit'),
    path(
        '<uuid:pk>/amendment/',
        views.AwardAmendmentCreateView.as_view(),
        name='amendment-create',
    ),
    path(
        'amendment/<uuid:pk>/',
        views.AwardAmendmentDetailView.as_view(),
        name='amendment-detail',
    ),
    path(
        '<uuid:award_id>/document/',
        views.AwardDocumentUploadView.as_view(),
        name='document-upload',
    ),
    path(
        'amendments/<uuid:pk>/approve/',
        views.AwardAmendmentApproveView.as_view(),
        name='amendment-approve',
    ),
    path(
        'amendments/<uuid:pk>/deny/',
        views.AwardAmendmentDenyView.as_view(),
        name='amendment-deny',
    ),
    path(
        'bulk/export/',
        bulk_views.BulkAwardExportView.as_view(),
        name='bulk-export',
    ),
    # Manifest e-Signature (post-0.14 roundtrip via keel.signatures).
    # The `signature_request` URL name is preserved so existing
    # templates and notification helpers keep resolving; the view now
    # routes through keel.signatures.client.send_to_manifest.
    path(
        '<uuid:pk>/signature/request/',
        views.SignatureRequestView.as_view(),
        name='signature_request',
    ),
    path(
        '<uuid:pk>/signature/local/',
        views.AwardLocalSignView.as_view(),
        name='signature-local',
    ),
    # Legacy DocuSign callback — retained for rollback; the running
    # flow no longer populates SignatureRequest via this path, but
    # any in-flight DocuSign envelopes created before the cutover can
    # still complete here. Remove in a follow-up once no legacy
    # envelopes remain.
    path(
        'docusign/callback/',
        views.DocuSignWebhookView.as_view(),
        name='docusign_callback',
    ),
    path(
        'signature/<uuid:pk>/status/',
        views.SignatureStatusView.as_view(),
        name='signature_status',
    ),

    # CSO Wave 4: gated download for AwardAttachment files.
    path(
        'attachment/<uuid:pk>/download/',
        views.AwardAttachmentDownloadView.as_view(),
        name='attachment-download',
    ),
]
