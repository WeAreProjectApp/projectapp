"""JWT-only tutorial catalog for the client platform."""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.authentication import SessionJWTAuthentication
from content.services.platform_video_service import client_videos


@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def platform_videos(request):
    return Response(client_videos(request.user), headers={'Cache-Control': 'no-store'})
