"""Project-scoped collaboration routes (platform)."""
from django.urls import path
import accounts.views_project_ideas as ideas
import accounts.views_project_client_access as access

urlpatterns = [
    path('ideas/', ideas.platform_ideas, name='platform-ideas'),
    path('ideas/<int:idea_id>/', ideas.platform_idea_detail, name='platform-idea-detail'),
    path('ideas/<int:idea_id>/revisions/', ideas.platform_idea_revisions, name='platform-idea-revisions'),
    path('ideas/<int:idea_id>/archive/', ideas.platform_idea_archive, name='platform-idea-archive'),
    path('ideas/<int:idea_id>/restore/', ideas.platform_idea_restore, name='platform-idea-restore'),
    path('idea-collections/', ideas.platform_idea_collections, name='platform-idea-collections'),
    path('idea-collections/<int:collection_id>/', ideas.platform_idea_collection_detail, name='platform-idea-collection-detail'),
    path('access/client-policy/', access.platform_client_access_policy, name='platform-client-access-policy'),
    path('access/client-policy/preview/', access.platform_client_access_preview, name='platform-client-access-preview'),
    path('access/client-policy/events/', access.platform_client_access_events, name='platform-client-access-events'),
    path('client-access/', access.platform_client_access, name='platform-client-access'),
    path('client-access/environments/<str:environment>/credentials/<str:field>/reveal/', access.platform_client_credential, name='platform-client-credential'),
]
