"""JWT readers and explicit retry over the shared notice service."""
from rest_framework.response import Response

from accounts.serializers_delivery_notifications import RetryDeliveryNoticeSerializer
from accounts.services import delivery_notifications as notices
from accounts.services.delivery_access import fail
from accounts.views_delivery import delivery_endpoint


@delivery_endpoint(['GET'])
def delivery_notice_list(request, project_id):
    try:
        page = int(request.query_params.get('page', 1))
    except (ValueError, TypeError):
        fail('La página debe ser un entero positivo.')
    return Response(notices.list_events(project_id, request.user, page, request.query_params.get('status')))


@delivery_endpoint(['GET'])
def delivery_notice_detail(request, project_id, event_id):
    return Response(notices.get_event(project_id, request.user, event_id))


@delivery_endpoint(['GET'])
def delivery_notice_retry_preview(request, project_id, event_id):
    try:
        version = int(request.query_params.get('expected_version'))
    except (ValueError, TypeError):
        fail('Indica la versión del aviso.')
    return Response(notices.retry_impact(project_id, request.user, event_id, version))


@delivery_endpoint(['POST'])
def delivery_notice_retry(request, project_id, event_id):
    serializer = RetryDeliveryNoticeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(notices.retry_event(project_id, request.user, event_id, **serializer.validated_data))
