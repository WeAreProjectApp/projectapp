"""Thin session/CSRF administration and JWT client endpoints for help."""
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from accounts.authentication import SessionJWTAuthentication
from accounts.services import platform_help as service


class HelpCatalogQuerySerializer(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1, required=False)


class HelpClientsQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    search = serializers.CharField(max_length=200, required=False, default='')


class HelpProgressQuerySerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1, required=False)
    page = serializers.IntegerField(min_value=1, default=1)


def _query(serializer):
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _response(payload, status=200):
    response = Response(payload, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def client_help(request):
    query = _query(HelpCatalogQuerySerializer(data=request.query_params))
    return _response(service.client_catalog(request.user, query.get('project_id')))


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def client_progress(request, tour_id):
    return _response(service.record_progress(request.user, tour_id, request.data))


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def help_settings(request):
    return _response(service.update_flags(request.user, request.data) if request.method == 'PATCH'
                     else service.settings_payload(request.user))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def help_clients(request):
    query = _query(HelpClientsQuerySerializer(data=request.query_params))
    return _response(service.list_clients(request.user, query['page'], query['search']))


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def help_client(request, user_id):
    return _response(service.update_flags(request.user, request.data, user_id) if request.method == 'PATCH'
                     else service.client_payload(request.user, user_id))


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tours(request):
    return _response(service.write_tour(request.user, request.data), 201) if request.method == 'POST' else _response(service.admin_catalog(request.user))


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tour_detail(request, tour_id):
    return _response(service.write_tour(request.user, request.data, tour_id) if request.method == 'PATCH'
                     else service.get_tour(request.user, tour_id))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tour_publish(request, tour_id):
    return _response(service.publish_tour(request.user, tour_id, request.data))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tour_archive(request, tour_id):
    values = service.validated(service.TourVersionSerializer, request.data)
    return _response(service.write_tour(request.user, {**values, 'is_active': False}, tour_id))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tour_preview(request, tour_id):
    return _response(service.preview_tour(request.user, tour_id))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def tour_revisions(request, tour_id):
    return _response(service.revisions(request.user, tour_id))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def help_progress(request):
    query = _query(HelpProgressQuerySerializer(data=request.query_params))
    return _response(service.progress_report(request.user, query['page'], query.get('user_id')))
