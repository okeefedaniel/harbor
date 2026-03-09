from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'signatures'

urlpatterns = [
    # ---- Root redirect ----
    path('', RedirectView.as_view(pattern_name='signatures:packet-list'), name='index'),

    # ---- Admin: Flow configuration ----
    path('flows/', views.FlowListView.as_view(), name='flow-list'),
    path('flows/create/', views.FlowCreateView.as_view(), name='flow-create'),
    path('flows/<uuid:pk>/', views.FlowDetailView.as_view(), name='flow-detail'),
    path('flows/<uuid:pk>/edit/', views.FlowUpdateView.as_view(), name='flow-edit'),
    path('flows/<uuid:pk>/delete/', views.FlowDeleteView.as_view(), name='flow-delete'),

    # ---- Admin: Steps within a flow ----
    path(
        'flows/<uuid:flow_id>/steps/create/',
        views.StepCreateView.as_view(),
        name='step-create',
    ),
    path('steps/<uuid:pk>/edit/', views.StepUpdateView.as_view(), name='step-edit'),
    path('steps/<uuid:pk>/delete/', views.StepDeleteView.as_view(), name='step-delete'),

    # ---- Documents within a flow ----
    path(
        'flows/<uuid:flow_id>/documents/upload/',
        views.DocumentUploadView.as_view(),
        name='document-upload',
    ),
    path(
        'documents/<uuid:pk>/delete/',
        views.DocumentDeleteView.as_view(),
        name='document-delete',
    ),

    # ---- Placement editor (any authenticated user) ----
    path(
        'documents/<uuid:document_id>/placements/',
        views.PlacementEditorView.as_view(),
        name='placement-editor',
    ),
    path(
        'api/documents/<uuid:document_id>/placements/',
        views.PlacementAPIView.as_view(),
        name='placement-api',
    ),

    # ---- Signing packets ----
    path('packets/', views.PacketListView.as_view(), name='packet-list'),
    path(
        'packets/initiate/<uuid:flow_id>/',
        views.PacketInitiateView.as_view(),
        name='packet-initiate',
    ),
    path('packets/<uuid:pk>/', views.PacketDetailView.as_view(), name='packet-detail'),
    path(
        'packets/<uuid:pk>/cancel/',
        views.PacketCancelView.as_view(),
        name='packet-cancel',
    ),
    path(
        'packets/<uuid:pk>/audit/',
        views.PacketAuditView.as_view(),
        name='packet-audit',
    ),

    # ---- Signing interface (for signers) ----
    path('sign/<uuid:step_id>/', views.SigningView.as_view(), name='sign'),
    path(
        'sign/<uuid:step_id>/complete/',
        views.SigningCompleteView.as_view(),
        name='sign-complete',
    ),
    path(
        'sign/<uuid:step_id>/decline/',
        views.SigningDeclineView.as_view(),
        name='sign-decline',
    ),

    # ---- My pending signatures ----
    path('my/', views.MySignaturesView.as_view(), name='my-signatures'),

    # ---- User signature management ----
    path(
        'my/signatures/',
        views.UserSignatureListView.as_view(),
        name='user-signature-list',
    ),
    path(
        'my/signatures/create/',
        views.UserSignatureCreateView.as_view(),
        name='user-signature-create',
    ),
    path(
        'my/signatures/<uuid:pk>/delete/',
        views.UserSignatureDeleteView.as_view(),
        name='user-signature-delete',
    ),
    path(
        'my/signatures/<uuid:pk>/default/',
        views.UserSignatureSetDefaultView.as_view(),
        name='user-signature-set-default',
    ),

    # ---- Role management ----
    path('roles/', views.RoleListView.as_view(), name='role-list'),
    path('roles/create/', views.RoleCreateView.as_view(), name='role-create'),
    path('roles/<uuid:pk>/edit/', views.RoleUpdateView.as_view(), name='role-edit'),
    path('roles/<uuid:pk>/delete/', views.RoleDeleteView.as_view(), name='role-delete'),

    # ---- Template Builder wizard ----
    path('builder/', views.TemplateBuilderView.as_view(), name='template-builder'),
    path(
        'builder/<uuid:pk>/',
        views.TemplateBuilderView.as_view(),
        name='template-builder-edit',
    ),
    path(
        'api/builder/save/',
        views.TemplateBuilderSaveAPIView.as_view(),
        name='template-builder-save',
    ),
    path(
        'api/builder/<uuid:pk>/save/',
        views.TemplateBuilderSaveAPIView.as_view(),
        name='template-builder-save-edit',
    ),

    # ---- AJAX endpoints ----
    path(
        'api/packets/<uuid:pk>/status/',
        views.PacketStatusAPIView.as_view(),
        name='packet-status-api',
    ),
    path(
        'api/steps/<uuid:pk>/remind/',
        views.StepRemindAPIView.as_view(),
        name='step-remind-api',
    ),
]
