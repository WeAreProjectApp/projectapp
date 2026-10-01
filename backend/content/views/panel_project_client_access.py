"""Policy management remains separate from the limited client projection."""
from rest_framework.response import Response
from accounts.project_collaboration_api import endpoint
from accounts.services import project_client_access as access

@endpoint(['GET', 'PATCH'], channel='panel')
def panel_client_access_policy(request, project_id):
    if request.method == 'PATCH':
        return Response(access.update_policy(project_id, request.user, request.data, channel='panel'))
    return Response(access.get_policy(project_id, request.user, channel='panel'))

@endpoint(['GET'], channel='panel')
def panel_client_access_preview(request, project_id):
    return Response(access.preview_access(project_id, request.user, channel='panel'))

@endpoint(['GET'], channel='panel')
def panel_client_access_events(request, project_id):
    return Response(access.list_events(project_id, request.user, channel='panel', page=request.query_params.get('page', 1)))
