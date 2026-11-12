from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from .authentication import IngestAuthentication
from .models import CapacityAllocation, Case, CaseActivity, Report, Resource, Source
from .serializers import (
    ActivitySerializer, CaseSerializer, DeliverySerializer, FilterSerializer,
    IngestSerializer, NoteSerializer, ReportSerializer, ResourceLinkSerializer, ResourceSerializer,
    SourceSerializer, StateSerializer,
    CapacitySerializer, CapacityChangeSerializer, SeriesFilterSerializer,
)
from .services import change_state, ingest, link_resource
from .dashboard import frozen_page, host_status, revision, save_capacity, series


def admin_api(methods):
    def decorate(view):
        return api_view(methods)(authentication_classes([SessionAuthentication])(permission_classes([IsAdminUser])(view)))
    return decorate


def validated(serializer_class, data):
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def paginated(queryset, serializer_class, page):
    size = 25
    total = queryset.count()
    return {'results': serializer_class(queryset[(page - 1) * size:page * size], many=True).data, 'count': total, 'page': page, 'page_size': size}


@api_view(['POST'])
@authentication_classes([IngestAuthentication])
@permission_classes([AllowAny])
def receive(request):
    if len(request.body) > 128 * 1024:
        return Response({'detail': 'Registro demasiado extenso.'}, status=413)
    receipt, created = ingest(request.auth, validated(IngestSerializer, request.data))
    return Response({'id': receipt.pk, 'case_id': receipt.case_id, 'report_id': receipt.report_id, 'duplicate': not created}, status=201 if created else 200)


@admin_api(['GET'])
def catalog(request):
    return Response({'resources': ResourceSerializer(Resource.objects.all(), many=True).data, 'sources': SourceSerializer(Source.objects.select_related('resource'), many=True).data})


def filtered(request, model):
    data = validated(FilterSerializer, request.query_params)
    query = model.objects.select_related('source__resource__server')
    # Large evidence/report bodies belong to the detail endpoint, not a list.
    query = query.defer('evidence' if model is Case else 'text')
    for parameter, field in [('resource', 'source__resource_id'), ('source', 'source_id'), ('kind', 'source__resource__kind')]:
        if parameter in data:
            query = query.filter(**{field: data[parameter]})
    if model is Case:
        for parameter in ['state', 'severity']:
            if parameter in data:
                query = query.filter(**{parameter: data[parameter]})
    if data.get('search'):
        query = query.filter(title__icontains=data['search'])
    date_field = 'last_seen_at' if model is Case else 'observed_at'
    for parameter, lookup in [('since', 'gte'), ('until', 'lt')]:
        if parameter in data:
            day = data[parameter]
            # Retain the date lookup at the representable limits: adding a day
            # or converting a boundary to UTC can overflow there.
            if day in (date.min, date.max):
                inclusive_lookup = 'gte' if parameter == 'since' else 'lte'
                query = query.filter(**{f'{date_field}__date__{inclusive_lookup}': day})
                continue
            boundary_day = day if parameter == 'since' else day + timedelta(days=1)
            boundary = datetime.combine(boundary_day, time.min)
            if settings.USE_TZ:
                boundary = timezone.make_aware(boundary, timezone.get_current_timezone())
            query = query.filter(**{f'{date_field}__{lookup}': boundary})
    return query, data['page']


@admin_api(['GET'])
def cases(request):
    query, page = filtered(request, Case)
    data = validated(FilterSerializer, request.query_params)
    if data.get('snapshot'):
        return Response(frozen_page(query, data, request.user))
    return Response(paginated(query, CaseSerializer, page))


@admin_api(['GET'])
def case_detail(request, pk):
    case = get_object_or_404(Case.objects.select_related('source__resource__server'), pk=pk)
    data = validated(FilterSerializer, request.query_params)
    return Response({**CaseSerializer(case).data, 'evidence': case.evidence,
                     'activities': paginated(case.activities.all(), ActivitySerializer, data.get('activities_page', data['page'])),
                     'deliveries': paginated(case.deliveries.all(), DeliverySerializer, data.get('deliveries_page', data['page']))})


@admin_api(['POST'])
def case_state(request, pk):
    case = change_state(pk, request.user, validated(StateSerializer, request.data))
    return Response(CaseSerializer(case).data)


@admin_api(['POST'])
def case_note(request, pk):
    case = get_object_or_404(Case, pk=pk)
    data = validated(NoteSerializer, request.data)
    activity = CaseActivity.objects.create(case=case, actor=request.user, actor_name=request.user.get_username(), kind='note', text=data['text'])
    return Response(ActivitySerializer(activity).data, status=201)


@admin_api(['GET'])
def reports(request):
    query, page = filtered(request, Report)
    data = validated(FilterSerializer, request.query_params)
    if data.get('snapshot'):
        return Response(frozen_page(query, data, request.user, reports=True))
    return Response(paginated(query, ReportSerializer, page))


@admin_api(['GET'])
def report_detail(request, pk):
    report = get_object_or_404(Report.objects.select_related('source__resource__server'), pk=pk)
    return Response({**ReportSerializer(report).data, 'text': report.text})


@admin_api(['PATCH'])
def resource_link(request, pk):
    data = validated(ResourceLinkSerializer, request.data)
    resource = link_resource(pk, data['project'])
    return Response(ResourceSerializer(resource).data)


@admin_api(['GET'])
def dashboard_status(request):
    data = validated(FilterSerializer, request.query_params)
    return Response({'revision': revision(), 'hosts': host_status(data), 'checked_at': timezone.now()})


@admin_api(['GET'])
def server_series(request, pk):
    resource = get_object_or_404(Resource, pk=pk, kind='server')
    data = validated(SeriesFilterSerializer, request.query_params)
    return Response(series(resource, data['period']))


@admin_api(['GET', 'PUT'])
def resource_capacity(request, pk):
    resource = get_object_or_404(Resource.objects.select_related('server'), pk=pk, kind='project')
    if request.method == 'PUT':
        data = validated(CapacitySerializer, request.data)
        allocation = save_capacity(resource, request.user, data)
    else:
        allocation = CapacityAllocation.objects.filter(resource=resource).first()
    return Response({'resource': ResourceSerializer(resource).data,
                     'server_name': resource.server.name if resource.server else None,
                     'allocation': CapacitySerializer(allocation).data if allocation else None,
                     'consumption': None, 'consumption_status': 'unavailable'})


@admin_api(['GET'])
def capacity_history(request, pk):
    resource = get_object_or_404(Resource, pk=pk, kind='project')
    allocation = get_object_or_404(CapacityAllocation, resource=resource)
    page = validated(FilterSerializer, request.query_params)['page']
    return Response(paginated(allocation.changes.all(), CapacityChangeSerializer, page))
