"""Panel API of the data-integrity engine; the projects MCP connector adapts it.

Admin session only. Reads answer ``no-store``: findings and the operation log
describe client data. Writes go through the engine, which records them.
"""
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import DataIntegrityOperation, DataIntegrityScan, DataIntegrityFinding, DataIntegrityReview
from content.serializers.data_integrity import (
    FindingsQuerySerializer, FixApplySerializer, FixPreviewSerializer, OperationsQuerySerializer, UndoSerializer,
)
from content.services.data_integrity import catalog, engine, observations
from content.services.data_integrity.scope import resolve_scope, scope_candidates


def _private_response(data):
    response = Response(data)
    response['Cache-Control'] = 'no-store'
    return response


def _scope(data):
    return resolve_scope(data['kind'], data.get('id'))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_rules(request):
    """The versioned rule catalog: what is checked and how each finding is fixed."""
    return _private_response(catalog.catalog_payload())


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_findings(request):
    """Findings inside a scope; a free-text scope returns candidates unless exactly one matches."""
    serializer = FindingsQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    scope_id = data.get('scope_id')
    if data.get('scope_query'):
        candidates = scope_candidates(data['scope_kind'], data['scope_query'])
        if len(candidates) != 1:
            return _private_response({'scope_candidates': candidates, 'count': 0, 'results': []})
        scope_id = candidates[0]['id']
    if data.get('scan_id') or data.get('status') or data.get('fingerprint'):
        if data.get('scan_id'):
            get_object_or_404(DataIntegrityScan, pk=data['scan_id'])
        return _private_response(observations.list_findings(
            scan_id=data.get('scan_id'), status=data.get('status', 'pending'), page=data['page'],
            **{key: data[key] for key in ('domains', 'rule_ids', 'severity', 'fingerprint') if key in data}))
    scope = resolve_scope(data['scope_kind'], scope_id)
    return _private_response(engine.findings_payload(
        scope, page=data['page'], domains=data.get('domains'), rule_ids=data.get('rule_ids'),
        severity=data.get('severity'),
    ))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_fix_preview(request):
    """What a batch would change, its blockers and the hash apply must confirm. Writes nothing."""
    serializer = FixPreviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return _private_response(engine.preview_fixes(_scope(data['scope']), data['fixes'], actor=request.user))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_fix_apply(request):
    serializer = FixApplySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    return _private_response(engine.apply_fixes(
        _scope(data['scope']), data['fixes'], actor=request.user, reason=data['reason'],
        request_id=data['request_id'], expected_impact_hash=data['expected_impact_hash'], source='panel',
    ))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_operations(request):
    """The log of applied fixes and undos, newest first."""
    serializer = OperationsQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return _private_response(engine.operations_payload(**serializer.validated_data))


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_operation_undo(request, operation_id):
    """Preview (GET) or apply (POST) the exact undo of an operation."""
    get_object_or_404(DataIntegrityOperation, pk=operation_id)
    if request.method == 'GET':
        return _private_response(engine.preview_undo(operation_id))
    serializer = UndoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return _private_response(engine.undo_operation(operation_id, actor=request.user, source='panel',
                                          **serializer.validated_data))


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_scans(request):
    from content.serializers.data_integrity import ScanStartSerializer
    if request.method == 'GET':
        rows = DataIntegrityScan.objects.order_by('-id')[:20]
        latest = DataIntegrityScan.objects.filter(status='completed').first()
        return _private_response({'results': [observations.scan_payload(row) for row in rows],
            'last_completed': observations.scan_payload(latest) if latest else None})
    serializer = ScanStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    scan = observations.start_scan(_scope(data['scope']), actor=request.user,
        source=engine.current_source('panel'), request_id=data['request_id'],
        filters={key: data[key] for key in ('domains', 'rule_ids', 'severity') if key in data})
    scan.refresh_from_db()
    return _private_response(observations.scan_payload(scan))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_scan(request, scan_id):
    return _private_response(observations.scan_payload(get_object_or_404(DataIntegrityScan, pk=scan_id)))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_review(request):
    from content.serializers.data_integrity import FindingReviewSerializer
    serializer = FindingReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    get_object_or_404(DataIntegrityFinding, fingerprint=data['fingerprint'])
    return _private_response(observations.review_finding(**data, actor=request.user, source=engine.current_source('panel')))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def data_integrity_reviews(request):
    rows = DataIntegrityReview.objects.select_related('actor', 'finding').order_by('-id')[:50]
    return _private_response({'results': [{'id': row.pk, 'fingerprint': row.finding.fingerprint,
        'action': row.action, 'reason': row.reason, 'actor': row.actor.get_username(),
        'source': row.source, 'created_at': row.created_at} for row in rows]})
