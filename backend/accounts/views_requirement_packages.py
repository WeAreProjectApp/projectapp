"""Thin adapters shared by session Panel, JWT Platform and MCP administration."""
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from accounts.models import Project
from accounts.models_requirement_packages import PackageMovement, PackageOrder, PackageRequest
from accounts.serializers_requirement_packages import (
    DecisionWriteSerializer, ExampleWriteSerializer, ExternalPaymentSerializer,
    OrderCreateSerializer, PackageSettingsSerializer, PackageWriteSerializer,
    ProposalWriteSerializer, RequestCreateSerializer, RequestVersionSerializer,
    ReversalSerializer, TransactionVerifySerializer,
)
from accounts.services import package_commerce as commerce, package_examples as examples, package_requests as requests_service
from accounts.services._platform_authority import platform_role_boundary
from accounts.services.delivery_access import is_admin, project_for_actor, require_admin
from accounts.services.package_common import owned


def validated(schema, data):
    serializer = schema(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def offset(request, key='offset'):
    try:
        value = int(request.query_params.get(key, 0))
        if value < 0:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ValidationError('La paginación requiere números enteros no negativos.') from None


def language(request):
    value = request.query_params.get('language', 'es')
    if value not in ('es', 'en'):
        raise ValidationError('Usa language=es o language=en.')
    return value


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_overview(request, project_id):
    project = project_for_actor(project_id, request.user)
    language_code = language(request)
    orders = PackageOrder.objects.filter(project=project, client_id=project.client_id)
    movements = PackageMovement.objects.filter(order__project=project, order__client_id=project.client_id).select_related('order')
    rows = requests_service.request_queryset(project)
    first = offset(request, 'order_offset')
    movement_offset = offset(request, 'movement_offset')
    request_offset = offset(request, 'request_offset')
    result = {'project_id': project.pk, 'project_name': project.name, 'is_admin': is_admin(request.user),
              'catalog': commerce.catalog(project, language=language_code),
              'examples': examples.example_catalog(project.pk, language=language_code),
              'balances': commerce.balances(project),
              'orders': {'count': orders.count(), 'results': [commerce.order_payload(row) for row in orders[first:first + 20]]},
              'requests': {'count': rows.count(), 'results': [requests_service.request_payload(row, include_balance=False) for row in rows[request_offset:request_offset + 20]]},
              'movements': {'count': movements.count(), 'results': [{'id': row.pk, 'order_id': str(row.order_id),
                  'size': row.size, 'quantity': row.quantity, 'kind': row.kind, 'reason': row.reason,
                  'reverses_id': row.reverses_id, 'created_at': row.created_at.isoformat()} for row in movements[movement_offset:movement_offset + 20]]}}
    if result['is_admin']:
        result['settings'] = commerce.settings_payload(project)
    return Response(result)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_examples(request, project_id=None):
    if project_id is not None:
        project_for_actor(project_id, request.user)
    if request.method == 'GET':
        return Response(examples.example_catalog(project_id, language=language(request)))
    data = validated(ExampleWriteSerializer, request.data)
    return Response(examples.publish_examples(request.user, data,
                         project_id=project_id, language=data.get('language', language(request))), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_example_history(request, project_id=None):
    require_admin(request.user)
    if project_id is not None:
        project_for_actor(project_id, request.user)
    rows = examples.PackageExampleRevision.objects.filter(project_id=project_id, language=language(request))
    start = offset(request)
    return Response({'count': rows.count(), 'results': list(rows.values('id', 'examples', 'note', 'author_id', 'created_at')[start:start + 20])})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_order_create(request, project_id):
    return Response(commerce.create_order(project_id, request.user, validated(OrderCreateSerializer, request.data)), status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_order_action(request, project_id, order_key, action):
    order_id = order_key
    if action == 'checkout':
        result = commerce.checkout(project_id, request.user, order_id, validated(PackageWriteSerializer, request.data))
    elif action == 'confirm-external':
        result = commerce.confirm_external(project_id, request.user, order_id, validated(ExternalPaymentSerializer, request.data))
    elif action == 'verify':
        data = validated(TransactionVerifySerializer, request.data)
        project = project_for_actor(project_id, request.user)
        owned(PackageOrder.objects.all(), project, pk=order_id)
        from accounts.services.wompi import verify_transaction
        try:
            canonical = verify_transaction(data['transaction_id'])
        except Exception:
            raise ValidationError('No se pudo verificar el pago. No se acreditaron cupos.') from None
        if not isinstance(canonical, dict):
            raise ValidationError('La pasarela no devolvió una transacción válida.')
        result = commerce.apply_transaction(project_id, request.user, order_id, data, canonical)
    else:
        raise NotFound('Operación no encontrada.')
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_request_create(request, project_id):
    return Response(requests_service.create_request(project_id, request.user,
        validated(RequestCreateSerializer, request.data)), status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_request_detail(request, project_id, package_request_id):
    project = project_for_actor(project_id, request.user)
    row = owned(requests_service.request_queryset(project), project, pk=package_request_id)
    return Response(requests_service.request_payload(row, detail=True))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_request_action(request, project_id, package_request_id, action):
    request_id = package_request_id
    if action == 'evaluate':
        result = requests_service.begin_evaluation(project_id, request.user, request_id,
            validated(RequestVersionSerializer, request.data))
    elif action == 'offer':
        result = requests_service.publish_proposal(project_id, request.user, request_id,
            validated(ProposalWriteSerializer, request.data))
    elif action == 'decide':
        impersonated = bool(request.auth and getattr(request.auth, 'get', lambda key: None)('impersonated_by'))
        result = requests_service.decide(project_id, request.user, request_id,
            validated(DecisionWriteSerializer, request.data), impersonated=impersonated)
    else:
        raise NotFound('Operación no encontrada.')
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_reverse(request, project_id, movement_id):
    return Response(commerce.reverse_movement(project_id, request.user, movement_id,
        validated(ReversalSerializer, request.data)))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_settings(request, project_id):
    return Response(commerce.update_settings(project_id, request.user,
        validated(PackageSettingsSerializer, request.data)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_admin_queue(request):
    require_admin(request.user)
    rows = PackageRequest.objects.filter(ticket__is_archived=False).select_related('ticket', 'project', 'current_proposal__decision')
    state = request.query_params.get('status', '')
    if state:
        if state not in dict(PackageRequest._meta.get_field('status').choices):
            raise ValidationError('Estado de solicitud inválido.')
        rows = rows.filter(status=state)
    search = request.query_params.get('search', '').strip()[:200]
    if search:
        rows = rows.filter(Q(ticket__title__icontains=search) | Q(project__name__icontains=search))
    start = offset(request)
    return Response({'count': rows.count(), 'pending_count': rows.filter(status__in=['pending', 'evaluating', 'objected']).count(),
                     'results': [requests_service.request_payload(row, include_balance=False) for row in rows[start:start + 20]]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_admin_projects(request):
    require_admin(request.user)
    rows = Project.objects.exclude(status__in=['archived', 'decommissioned']).filter(name__icontains=request.query_params.get('search', '').strip()[:200]).order_by('name', 'pk')
    return Response({'results': list(rows.values('id', 'name')[:20])})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@platform_role_boundary
def package_evaluation_context(request, project_id):
    require_admin(request.user)
    project_for_actor(project_id, request.user)
    from content.services.requirement_calculator import calculator_context
    return Response(calculator_context(project_id=project_id))
