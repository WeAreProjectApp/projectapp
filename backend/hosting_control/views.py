from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.mcp.context import current_mcp_context
from . import services
from .authentication import HasRuntimeCredential, RuntimeAuthentication
from .serializers import ListInput, MessageInput, ModeInput, ReceiptInput


def response(data):
    return Response(data, headers={'Cache-Control': 'no-store'})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def controls(request):
    serializer = ListInput(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return response(services.listing(request.user, serializer.validated_data))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def detail(request, control_id):
    return response(services.detail(request.user, control_id))


def change(request, control_id, serializer_class):
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    context = current_mcp_context()
    source = f'mcp:{context.connector.slug}:credential:{context.credential.pk}' if context else 'panel'
    return response(services.update(request.user, control_id, serializer.validated_data, source))


@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def mode(request, control_id):
    return change(request, control_id, ModeInput)


@api_view(['PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def message(request, control_id):
    return change(request, control_id, MessageInput)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def events(request, control_id):
    return response(services.events(request.user, control_id, request.query_params.get('page', 1)))


@api_view(['GET'])
@authentication_classes([RuntimeAuthentication])
@permission_classes([HasRuntimeCredential])
def runtime_configs(request):
    targets = request.auth.targets.filter(lifecycle='active',
                                          control__resource__kind='project', control__resource__environment='production').select_related('control')
    return response({'configs': [services.runtime_payload(target) for target in targets]})


@api_view(['POST'])
@authentication_classes([RuntimeAuthentication])
@permission_classes([HasRuntimeCredential])
def runtime_receipt(request):
    serializer = ReceiptInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    return response(services.receive(request.auth, serializer.validated_data))
