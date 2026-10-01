"""Thin ideas endpoints over the common domain services."""
from rest_framework.response import Response
from accounts.project_collaboration_api import endpoint, require_personal_session
from accounts.services import project_ideas as ideas
from accounts.services import project_idea_collections as collections

@endpoint(['GET', 'POST'], channel='platform')
def platform_ideas(request, project_id):
    if request.method == 'POST':
        require_personal_session(request)
        return Response(ideas.create_idea(project_id, request.user, request.data, channel='platform'), status=201)
    return Response(ideas.list_ideas(project_id, request.user, channel='platform', page=request.query_params.get('page', 1)))

@endpoint(['GET', 'PATCH'], channel='platform')
def platform_idea_detail(request, project_id, idea_id):
    if request.method == 'PATCH':
        require_personal_session(request)
        return Response(ideas.edit_idea(project_id, request.user, idea_id, request.data, channel='platform'))
    return Response(ideas.get_idea(project_id, request.user, idea_id, channel='platform'))

@endpoint(['GET'], channel='platform')
def platform_idea_revisions(request, project_id, idea_id):
    return Response(ideas.revisions(project_id, request.user, idea_id, channel='platform', page=request.query_params.get('page', 1)))

@endpoint(['POST'], channel='platform')
def platform_idea_archive(request, project_id, idea_id):
    return Response(ideas.archive_idea(project_id, request.user, idea_id, request.data, channel='platform', restore=False))

@endpoint(['POST'], channel='platform')
def platform_idea_restore(request, project_id, idea_id):
    return Response(ideas.archive_idea(project_id, request.user, idea_id, request.data, channel='platform', restore=True))

@endpoint(['GET', 'POST'], channel='platform')
def platform_idea_collections(request, project_id):
    if request.method == 'POST':
        return Response(collections.create_collection(project_id, request.user, request.data, channel='platform'), status=201)
    return Response(collections.list_collections(project_id, request.user, channel='platform', page=request.query_params.get('page', 1)))

@endpoint(['GET'], channel='platform')
def platform_idea_collection_detail(request, project_id, collection_id):
    return Response(collections.get_collection(project_id, request.user, collection_id, channel='platform'))
