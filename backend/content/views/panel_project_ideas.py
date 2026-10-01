"""Thin ideas endpoints over the common domain services."""
from rest_framework.response import Response
from accounts.project_collaboration_api import endpoint
from accounts.services import project_ideas as ideas
from accounts.services import project_idea_collections as collections

@endpoint(['GET', 'POST'], channel='panel')
def panel_ideas(request, project_id):
    if request.method == 'POST':
        return Response(ideas.create_idea(project_id, request.user, request.data, channel='panel'), status=201)
    return Response(ideas.list_ideas(project_id, request.user, channel='panel', page=request.query_params.get('page', 1)))

@endpoint(['GET', 'PATCH'], channel='panel')
def panel_idea_detail(request, project_id, idea_id):
    if request.method == 'PATCH':
        return Response(ideas.edit_idea(project_id, request.user, idea_id, request.data, channel='panel'))
    return Response(ideas.get_idea(project_id, request.user, idea_id, channel='panel'))

@endpoint(['GET'], channel='panel')
def panel_idea_revisions(request, project_id, idea_id):
    return Response(ideas.revisions(project_id, request.user, idea_id, channel='panel', page=request.query_params.get('page', 1)))

@endpoint(['POST'], channel='panel')
def panel_idea_archive(request, project_id, idea_id):
    return Response(ideas.archive_idea(project_id, request.user, idea_id, request.data, channel='panel', restore=False))

@endpoint(['POST'], channel='panel')
def panel_idea_restore(request, project_id, idea_id):
    return Response(ideas.archive_idea(project_id, request.user, idea_id, request.data, channel='panel', restore=True))

@endpoint(['GET', 'POST'], channel='panel')
def panel_idea_collections(request, project_id):
    if request.method == 'POST':
        return Response(collections.create_collection(project_id, request.user, request.data, channel='panel'), status=201)
    return Response(collections.list_collections(project_id, request.user, channel='panel', page=request.query_params.get('page', 1)))

@endpoint(['GET'], channel='panel')
def panel_idea_collection_detail(request, project_id, collection_id):
    return Response(collections.get_collection(project_id, request.user, collection_id, channel='panel'))
