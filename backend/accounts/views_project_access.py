"""JWT-authenticated project access-detail endpoints for the platform."""

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

from accounts.authentication import SessionJWTAuthentication
from accounts.permissions import IsAdminRole
from accounts.project_access_api import (
    project_access_detail_handler,
    project_access_legacy_classify_handler,
    project_access_note_detail_handler,
    project_access_note_reveal_handler,
    project_access_notes_handler,
    project_access_password_delete_handler,
    project_access_password_reveal_handler,
)


_platform_permissions = [IsAuthenticated, IsAdminRole]


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_detail(request, project_id):
    return project_access_detail_handler(request, project_id)


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_password_reveal(request, project_id, environment):
    return project_access_password_reveal_handler(request, project_id, environment)


@api_view(['DELETE'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_password_delete(request, project_id, environment):
    return project_access_password_delete_handler(request, project_id, environment)


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_notes(request, project_id):
    return project_access_notes_handler(request, project_id)


@api_view(['PATCH', 'DELETE'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_note_detail(request, project_id, note_id):
    return project_access_note_detail_handler(request, project_id, note_id)


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_note_reveal(request, project_id, note_id):
    return project_access_note_reveal_handler(request, project_id, note_id)


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes(_platform_permissions)
def platform_project_access_legacy_classify(request, project_id):
    return project_access_legacy_classify_handler(request, project_id)
