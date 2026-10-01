"""Project-scoped collaboration routes (panel)."""
from django.urls import path
import content.views.panel_project_ideas as ideas
import content.views.panel_project_client_access as access

urlpatterns = [
    path('ideas/', ideas.panel_ideas, name='panel-ideas'),
    path('ideas/<int:idea_id>/', ideas.panel_idea_detail, name='panel-idea-detail'),
    path('ideas/<int:idea_id>/revisions/', ideas.panel_idea_revisions, name='panel-idea-revisions'),
    path('ideas/<int:idea_id>/archive/', ideas.panel_idea_archive, name='panel-idea-archive'),
    path('ideas/<int:idea_id>/restore/', ideas.panel_idea_restore, name='panel-idea-restore'),
    path('idea-collections/', ideas.panel_idea_collections, name='panel-idea-collections'),
    path('idea-collections/<int:collection_id>/', ideas.panel_idea_collection_detail, name='panel-idea-collection-detail'),
    path('access/client-policy/', access.panel_client_access_policy, name='panel-client-access-policy'),
    path('access/client-policy/preview/', access.panel_client_access_preview, name='panel-client-access-preview'),
    path('access/client-policy/events/', access.panel_client_access_events, name='panel-client-access-events'),
]
