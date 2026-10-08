from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.serializers import UserProfileSerializer
from accounts.services.tokens import get_tokens_for_user


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def session_token_bridge(request):
    """
    Bridge endpoint: exchange a valid Django session (staff) for JWT tokens.

    Used by the admin panel frontend to navigate seamlessly into the
    platform without requiring a separate login.
    """
    user = request.user
    profile, _ = UserProfile.objects.update_or_create(
        user=user,
        defaults={
            'role': UserProfile.ROLE_ADMIN,
            'is_onboarded': True,
            'profile_completed': True,
            'created_by': user,
        },
    )

    tokens = get_tokens_for_user(user)
    return Response({
        'tokens': tokens,
        'user': UserProfileSerializer(profile, context={'request': request}).data,
    }, status=status.HTTP_200_OK)
