from django.core.paginator import Paginator
from django.db.models import Count, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import CommunicationMessage, CommunicationThread, Document
from content.serializers.communication import (
    CommunicationDateCorrectionWriteSerializer,
    CommunicationDraftUpdateSerializer,
    CommunicationMarkSentSerializer,
    CommunicationMessageCreateSerializer,
    CommunicationMessageSerializer,
    CommunicationThreadDetailSerializer,
    CommunicationThreadListSerializer,
    CommunicationThreadWriteSerializer,
    CommunicationVoidSerializer,
)
from content.services import communication_service
from content.services import communication_query_service


MAX_COMMUNICATION_TAB_COUNT_SPECS = 24


def _business_error(exc):
    detail = exc.args[0] if exc.args else str(exc)
    if isinstance(detail, dict):
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': str(detail)}, status=status.HTTP_400_BAD_REQUEST)


def _positive_int(value, *, field, default=None, maximum=None):
    if value in (None, ''):
        return default, None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, Response(
            {field: 'Debe ser un número entero.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if parsed < 1:
        return None, Response(
            {field: 'Debe ser mayor que cero.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed, None


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def communication_threads(request):
    """List filtered conversations or create a new empty thread."""
    if request.method == 'POST':
        serializer = CommunicationThreadWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            thread = communication_service.create_thread(
                actor=request.user,
                **serializer.validated_data,
            )
        except communication_service.CommunicationError as exc:
            return _business_error(exc)
        thread = get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread.pk,
        )
        return Response(
            CommunicationThreadDetailSerializer(thread).data,
            status=status.HTTP_201_CREATED,
        )

    try:
        filters = communication_query_service.parse_filters(request.query_params)
    except communication_query_service.CommunicationFilterError as exc:
        return Response(exc.errors, status=status.HTTP_400_BAD_REQUEST)

    queryset = communication_query_service.apply_filters(
        communication_query_service.thread_queryset(), filters,
    )

    page_number, error = _positive_int(
        request.query_params.get('page'), field='page', default=1,
    )
    if error:
        return error
    page_size, error = _positive_int(
        request.query_params.get('page_size'),
        field='page_size',
        default=20,
        maximum=100,
    )
    if error:
        return error
    paginator = Paginator(
        communication_query_service.order_threads(queryset, filters.order),
        page_size,
    )
    page = paginator.get_page(page_number)
    return Response({
        'results': CommunicationThreadListSerializer(page.object_list, many=True).data,
        'count': paginator.count,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'facets': communication_query_service.build_facets(filters),
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def communication_thread_tab_counts(request):
    """Return the full-dataset count for each predefined or saved filter tab."""
    specs = request.data.get('tabs')
    if not isinstance(specs, list):
        return Response(
            {'tabs': 'Debe ser una lista.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(specs) > MAX_COMMUNICATION_TAB_COUNT_SPECS:
        return Response(
            {'tabs': f'Máximo {MAX_COMMUNICATION_TAB_COUNT_SPECS} pestañas por consulta.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    aggregates = {}
    tab_keys = []
    for index, spec in enumerate(specs):
        tab_id = spec.get('id') if isinstance(spec, dict) else None
        valid_id = (
            isinstance(tab_id, int) and not isinstance(tab_id, bool)
        ) or (
            isinstance(tab_id, str) and bool(tab_id.strip())
        )
        if not valid_id:
            return Response(
                {'tabs': 'Cada pestaña debe tener un identificador.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        raw_filters = spec.get('filters', {})
        if raw_filters is None:
            raw_filters = {}
        if not isinstance(raw_filters, dict):
            return Response(
                {'tabs': 'Los filtros de cada pestaña deben ser un objeto.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            filters = communication_query_service.parse_filters(raw_filters)
        except communication_query_service.CommunicationFilterError as exc:
            return Response(exc.errors, status=status.HTTP_400_BAD_REQUEST)
        queryset = communication_query_service.apply_filters(
            CommunicationThread.objects.all(), filters,
        )
        alias = f'tab_{index}'
        aggregates[alias] = Count(
            'pk', filter=Q(pk__in=Subquery(queryset.order_by().values('pk'))),
        )
        tab_keys.append((str(tab_id), alias))

    totals = CommunicationThread.objects.aggregate(**aggregates) if aggregates else {}
    counts = {tab_id: totals[alias] for tab_id, alias in tab_keys}
    return Response({'counts': counts})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def communication_thread_detail(request, thread_id):
    thread = get_object_or_404(
        communication_query_service.thread_queryset(), pk=thread_id,
    )
    if request.method == 'PATCH':
        serializer = CommunicationThreadWriteSerializer(
            thread, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        try:
            communication_service.update_thread(
                thread,
                actor=request.user,
                **serializer.validated_data,
            )
        except communication_service.CommunicationError as exc:
            return _business_error(exc)
        thread = get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread_id,
        )
    return Response(CommunicationThreadDetailSerializer(thread).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def close_communication_thread(request, thread_id):
    thread = get_object_or_404(CommunicationThread, pk=thread_id)
    try:
        communication_service.close_thread(thread, actor=request.user)
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationThreadDetailSerializer(
        get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread_id,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def reopen_communication_thread(request, thread_id):
    thread = get_object_or_404(CommunicationThread, pk=thread_id)
    try:
        communication_service.reopen_thread(thread, actor=request.user)
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationThreadDetailSerializer(
        get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread_id,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def archive_communication_thread(request, thread_id):
    thread = get_object_or_404(CommunicationThread, pk=thread_id)
    try:
        communication_service.archive_thread(thread, actor=request.user)
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationThreadDetailSerializer(
        get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread_id,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def unarchive_communication_thread(request, thread_id):
    thread = get_object_or_404(CommunicationThread, pk=thread_id)
    try:
        communication_service.unarchive_thread(thread, actor=request.user)
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationThreadDetailSerializer(
        get_object_or_404(
            communication_query_service.thread_queryset(), pk=thread_id,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def communication_thread_messages(request, thread_id):
    thread = get_object_or_404(
        CommunicationThread.objects.select_related('client__user'),
        pk=thread_id,
    )
    serializer = CommunicationMessageCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    validated_data = dict(serializer.validated_data)
    document_ids = validated_data.pop('document_ids', [])
    try:
        message = communication_service.create_message(
            thread=thread,
            actor=request.user,
            document_ids=document_ids,
            **validated_data,
        )
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    message = get_object_or_404(
        communication_query_service.message_queryset(), pk=message.pk,
    )
    return Response(
        CommunicationMessageSerializer(message).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdminUser])
def communication_message_detail(request, message_id):
    message = get_object_or_404(
        communication_query_service.message_queryset().select_related(
            'thread__client__user',
        ),
        pk=message_id,
    )
    try:
        if request.method == 'DELETE':
            communication_service.delete_draft(message, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = CommunicationDraftUpdateSerializer(
            message, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        validated_data = dict(serializer.validated_data)
        document_ids = validated_data.pop('document_ids', None)
        message = communication_service.update_draft(
            message,
            actor=request.user,
            document_ids=document_ids,
            **validated_data,
        )
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationMessageSerializer(
        get_object_or_404(
            communication_query_service.message_queryset(), pk=message.pk,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def mark_communication_message_sent(request, message_id):
    message = get_object_or_404(
        CommunicationMessage.objects.select_related('thread'), pk=message_id,
    )
    serializer = CommunicationMarkSentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        message = communication_service.mark_sent(
            message,
            actor=request.user,
            **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationMessageSerializer(
        get_object_or_404(
            communication_query_service.message_queryset(), pk=message.pk,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def void_communication_message(request, message_id):
    message = get_object_or_404(
        CommunicationMessage.objects.select_related('thread'), pk=message_id,
    )
    serializer = CommunicationVoidSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        message = communication_service.void_message(
            message, actor=request.user, **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationMessageSerializer(
        get_object_or_404(
            communication_query_service.message_queryset(), pk=message.pk,
        ),
    ).data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def correct_communication_message_date(request, message_id):
    message = get_object_or_404(
        CommunicationMessage.objects.select_related('thread'), pk=message_id,
    )
    serializer = CommunicationDateCorrectionWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        message = communication_service.correct_message_date(
            message, actor=request.user, **serializer.validated_data,
        )
    except communication_service.CommunicationError as exc:
        return _business_error(exc)
    return Response(CommunicationMessageSerializer(
        get_object_or_404(
            communication_query_service.message_queryset(), pk=message.pk,
        ),
    ).data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def document_communication_usage(request, document_id):
    document = get_object_or_404(Document, pk=document_id)
    messages = communication_query_service.message_queryset().filter(
        documents=document,
    ).select_related(
        'thread__client__user', 'thread__project',
    )
    rows = []
    for message in messages.order_by('-occurred_at', '-id'):
        rows.append({
            'message': CommunicationMessageSerializer(message).data,
            'thread': {
                'id': message.thread_id,
                'title': message.thread.title,
                'client_id': message.thread.client_id,
                'client_name': message.thread.client.user.get_full_name()
                or message.thread.client.company_name
                or message.thread.client.user.email,
                'project_id': message.thread.project_id,
                'project_name': message.thread.project.name if message.thread.project else '',
            },
        })
    return Response({
        'document_id': document.id,
        'document_title': document.title,
        'count': len(rows),
        'results': rows,
    })
