"""Staff-only FBV adapters; the conversational model stays outside ProjectApp."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.serializers.requirement_calculator import (
    ActualSerializer,
    ApproveSerializer,
    DefinitionWriteSerializer,
    EstimateSerializer,
    ProjectDraftSerializer,
)
from content.services import calculator_calibration as calibration
from content.services import requirement_calculator as service


def validated(schema, data):
    serializer = schema(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def write_data(request):
    data = dict(request.data)
    match = request.headers.get('If-Match')
    if match:
        if 'if_match' in data and data['if_match'] != match:
            raise ValidationError('La versión del cuerpo y de If-Match no coinciden.')
        data['if_match'] = match
    return data


def pagination(request):
    try:
        return {'limit': int(request.query_params.get('limit', 20)), 'offset': int(request.query_params.get('offset', 0))}
    except (ValueError, TypeError) as exc:
        raise ValidationError('La paginación necesita números enteros.') from exc


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def calculator_definition(request):
    if request.method == 'GET':
        return Response(service.overview())
    return Response(service.publish(**validated(DefinitionWriteSerializer, write_data(request)), actor=request.user))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def calculator_preview(request):
    if set(request.data) != {'definition'}:
        raise ValidationError('Envía únicamente definition.')
    return Response(service.preview(request.data['definition']))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def calculator_revisions(request):
    return Response(service.list_revisions(**pagination(request)))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def calculator_revision(request, revision_id):
    return Response(service.revision_detail(revision_id))


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def project_calculator(request, project_id):
    if request.method == 'GET':
        return Response(service.project_overview(project_id))
    return Response(service.create_project_draft(project_id, **validated(ProjectDraftSerializer, write_data(request)), actor=request.user), status=201)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def project_calculator_draft(request, version_id):
    if request.method == 'GET':
        return Response(service.project_version_detail(version_id))
    values = validated(DefinitionWriteSerializer, write_data(request))
    if 'document_id' in values:
        raise ValidationError('El documento particular ya está vinculado.')
    return Response(service.update_project_draft(version_id, **values, actor=request.user))


@api_view(['POST'])
@permission_classes([IsAdminUser])
def project_calculator_approve(request, version_id):
    return Response(service.approve_project_version(version_id, **validated(ApproveSerializer, write_data(request)), actor=request.user))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def calculator_context(request):
    values = {}
    for key in ('project_id', 'project_version_id'):
        if key in request.query_params:
            try:
                values[key] = int(request.query_params[key])
            except (ValueError, TypeError) as exc:
                raise ValidationError({key: 'Indica un identificador positivo.'}) from exc
            if values[key] < 1:
                raise ValidationError({key: 'Indica un identificador positivo.'})
    requirement = request.query_params.get('requirement', '')
    if len(requirement) > 30000:
        raise ValidationError('El requerimiento supera 30000 caracteres.')
    return Response(service.calculator_context(**values, requirement=requirement))


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def calculator_estimates(request):
    if request.method == 'GET':
        return Response(calibration.estimates(**pagination(request)))
    return Response(calibration.record_estimate(validated(EstimateSerializer, request.data), actor=request.user), status=201)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def calculator_actuals(request):
    return Response(calibration.record_actual(validated(ActualSerializer, request.data), actor=request.user), status=201)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def calculator_calibration(request):
    return Response(calibration.report())
