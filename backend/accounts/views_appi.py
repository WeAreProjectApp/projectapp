"""JWT client endpoints. No administrative or provider credentials are exposed."""
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.authentication import SessionJWTAuthentication
from accounts.serializers_appi import ConversationSerializer, HistorySerializer, QuestionSerializer
from accounts.services import appi
from accounts.services.platform_ai_quota import snapshot


def _validated(kind, data):
    serializer = kind(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


@never_cache
@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def quota_view(request):
    appi.require_appi(request.user)
    return Response(snapshot(request.user))


@never_cache
@api_view(['GET', 'POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def conversations_view(request):
    if request.method == 'GET':
        return Response({'results': appi.list_conversations(request.user)})
    item = appi.create_conversation(request.user, _validated(ConversationSerializer, request.data))
    return Response(appi.conversation_data(item), status=201)


@never_cache
@api_view(['GET', 'DELETE'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def conversation_view(request, conversation_id):
    if request.method == 'DELETE':
        appi.delete_conversation(request.user, conversation_id)
        return Response(status=204)
    values = _validated(HistorySerializer, request.query_params)
    return Response(appi.detail(request.user, conversation_id, values.get('before')))


@never_cache
@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def messages_view(request, conversation_id):
    item = appi.submit(request.user, conversation_id, _validated(QuestionSerializer, request.data))
    return Response({**appi.turn_data(request.user, item), 'quota': snapshot(request.user)}, status=202 if item.status in ('pending', 'processing') else 200)


@never_cache
@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def message_view(request, conversation_id, turn_id):
    return Response(appi.message(request.user, conversation_id, turn_id))
