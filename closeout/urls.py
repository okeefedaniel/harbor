from django.urls import path

from . import views

app_name = 'closeout'

urlpatterns = [
    path('', views.CloseoutListView.as_view(), name='list'),
    path('<uuid:pk>/', views.CloseoutDetailView.as_view(), name='detail'),
    path(
        'initiate/<uuid:award_id>/',
        views.CloseoutInitiateView.as_view(),
        name='initiate',
    ),
    path(
        'checklist/<uuid:pk>/',
        views.CloseoutChecklistUpdateView.as_view(),
        name='update-checklist',
    ),
    path(
        'checklist/<uuid:pk>/toggle/',
        views.CloseoutChecklistToggleView.as_view(),
        name='checklist-toggle',
    ),
    path(
        'fund-return/<uuid:closeout_id>/',
        views.FundReturnCreateView.as_view(),
        name='fund-return-create',
    ),
    path(
        'document/<uuid:closeout_id>/',
        views.CloseoutDocumentUploadView.as_view(),
        name='document-upload',
    ),
    path(
        '<uuid:pk>/complete/',
        views.CloseoutCompleteView.as_view(),
        name='complete',
    ),
]
