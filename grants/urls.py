from django.urls import path

from . import views

app_name = 'grants'

urlpatterns = [
    path('', views.GrantProgramListView.as_view(), name='program-list'),
    path('create/', views.GrantProgramCreateView.as_view(), name='program-create'),
    path('<uuid:pk>/', views.GrantProgramDetailView.as_view(), name='program-detail'),
    path(
        '<uuid:pk>/edit/',
        views.GrantProgramUpdateView.as_view(),
        name='program-update',
    ),
    path(
        '<uuid:pk>/publish/',
        views.PublishGrantProgramView.as_view(),
        name='program-publish',
    ),

    # Federal tracked opportunities
    path('federal/tracked/', views.TrackedOpportunityListView.as_view(), name='tracked-list'),
    path('federal/tracked/add/', views.TrackOpportunityView.as_view(), name='tracked-add'),
    path('federal/tracked/<uuid:pk>/', views.TrackedOpportunityDetailView.as_view(), name='tracked-detail'),
    path('federal/tracked/<uuid:pk>/edit/', views.TrackedOpportunityUpdateView.as_view(), name='tracked-update'),
    path('federal/tracked/<uuid:pk>/collaborate/', views.AddCollaboratorView.as_view(), name='tracked-collaborate'),
    path(
        'federal/tracked/<uuid:pk>/collaborate/<uuid:collab_pk>/remove/',
        views.RemoveCollaboratorView.as_view(),
        name='tracked-remove-collaborator',
    ),

    # Applicant saved programs (watchlist)
    path('saved/', views.SavedProgramListView.as_view(), name='saved-list'),
    path('saved/toggle/', views.SaveProgramView.as_view(), name='saved-toggle'),
    path('saved/<uuid:pk>/update/', views.UpdateSavedProgramView.as_view(), name='saved-update'),

    # AI grant matching
    path('matching/preferences/', views.GrantPreferenceView.as_view(), name='preferences'),
    path('matching/recommendations/', views.RecommendedMatchesView.as_view(), name='recommendations'),
    path('matching/dismiss/<uuid:pk>/', views.DismissMatchView.as_view(), name='dismiss-match'),
    path('matching/track-dismiss/<uuid:pk>/', views.TrackAndDismissView.as_view(), name='track-and-dismiss'),
    path('matching/feedback/<uuid:pk>/', views.MatchFeedbackView.as_view(), name='match-feedback'),
]
