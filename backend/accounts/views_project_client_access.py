"""Policy management remains separate from the limited client projection."""
from rest_framework.response import Response
from accounts.project_collaboration_api import endpoint, require_personal_session
from accounts.services import project_client_access as access

@endpoint(['GET', 'PATCH'], channel='platform')
def platform_client_access_policy(request, project_id):
    if request.method == 'PATCH':
        return Response(access.update_policy(project_id, request.user, request.data, channel='platform'))
    return Response(access.get_policy(project_id, request.user, channel='platform'))

@endpoint(['GET'], channel='platform')
def platform_client_access_preview(request, project_id):
    return Response(access.preview_access(project_id, request.user, channel='platform'))

@endpoint(['GET'], channel='platform')
def platform_client_access_events(request, project_id):
    return Response(access.list_events(project_id, request.user, channel='platform', page=request.query_params.get('page', 1)))

@endpoint(['GET'], channel='platform')
def platform_client_access(request, project_id):
    return Response(access.client_access(project_id, request.user))

@endpoint(['POST'], channel='platform')
def platform_client_credential(request, project_id, environment, field):
    require_personal_session(request)
    return Response(access.reveal_credential(project_id, request.user, environment, field, request.data))
