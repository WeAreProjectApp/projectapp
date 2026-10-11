"""Public presentation and read-only Panel endpoints for Building on Demand."""
from django.http import HttpResponse
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from content.services import building_on_demand_program_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.services.building_on_demand_pdf_service import BuildingOnDemandPdfService


def _error_response(error):
    return Response({'message': str(error), 'code': error.code, 'details': error.details},
                    status=404 if error.code == 'NOT_FOUND' else 400)


def _public_response(request, *, pdf=False):
    language = request.query_params.get('lang', 'es')
    if language not in ('es', 'en'):
        return Response({'lang': ['Usa es o en.']}, status=400)
    try:
        if pdf:
            response = HttpResponse(BuildingOnDemandPdfService.build(language=language), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="building-on-demand-{language}.pdf"'
            response['Cache-Control'] = 'private, no-store'
            return response
        return Response(service.serialize_public_program(language), headers={'Cache-Control': 'no-store'})
    except BuildingOnDemandError as exc:
        return _error_response(exc)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_building_on_demand_program(request):
    return _public_response(request)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_building_on_demand_program_pdf(request):
    return _public_response(request, pdf=True)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def admin_building_on_demand_overview(request):
    try:
        return Response(service.admin_overview())
    except BuildingOnDemandError as exc:
        return _error_response(exc)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def admin_building_on_demand_program_versions(request):
    try:
        limit = int(request.query_params.get('limit', '20'))
        offset = int(request.query_params.get('offset', '0'))
    except (ValueError, TypeError):
        return Response({'limit': ['Usa un entero entre 1 y 50.'], 'offset': ['Usa un entero no negativo.']}, status=400)
    try:
        return Response(service.list_versions(limit=limit, offset=offset))
    except BuildingOnDemandError as exc:
        return _error_response(exc)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def admin_building_on_demand_economics(request):
    try:
        return Response(service.economics())
    except BuildingOnDemandError as exc:
        return _error_response(exc)
