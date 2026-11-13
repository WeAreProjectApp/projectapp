"""Private FBV projections; clients cannot choose whose flags to evaluate."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.exceptions import ValidationError

from accounts.authentication import SessionJWTAuthentication
from accounts.views_ai import private_api_view, private_response
from accounts.services import platform_features as service


@private_api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def effective(request):
    if request.query_params:
        raise ValidationError('La evaluación corresponde únicamente a tu cuenta.')
    profile = getattr(request.user, 'profile', None)
    from rest_framework.exceptions import PermissionDenied
    if profile is None or not request.user.is_active:
        raise PermissionDenied('Se requiere una cuenta de Plataforma.')
    return private_response({'user_id': request.user.pk,
        'features': {key: True for key in service.FEATURES} if profile.is_admin
                    else service.values_for(request.user.pk), 'catalog_version': service.CATALOG['version']})


@private_api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def settings(request):
    return private_response(service.update(request.user, request.data) if request.method == 'PATCH'
                            else service.payload(request.user))


@private_api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def clients(request):
    return private_response(service.list_clients(request.user, request.query_params.get('page', 1),
                                                request.query_params.get('search', '')))


@private_api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def client(request, user_id):
    return private_response(service.update(request.user, request.data, user_id) if request.method == 'PATCH'
                            else service.payload(request.user, user_id))


@private_api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def events(request):
    return private_response(service.events(request.user, request.query_params.get('page', 1),
                                          request.query_params.get('user_id')))

