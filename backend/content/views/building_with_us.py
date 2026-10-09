"""Public presentation and read-only Panel endpoints."""
from django.http import HttpResponse
from django.views.decorators.clickjacking import xframe_options_sameorigin
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from content.services import building_with_us_program_service as service
from content.services import building_with_us_contract_service as contract_service
from content.services.building_with_us_content import BuildingWithUsError
from content.services.building_with_us_pdf_service import BuildingWithUsPdfService


def _error_response(error):
    return Response({'message': str(error), 'code': error.code, 'details': error.details},
                    status=404 if error.code == 'NOT_FOUND' else 400)


def _public_response(request, *, pdf=False):
    language = request.query_params.get('lang', 'es')
    if language not in ('es', 'en'):
        return Response({'lang': ['Usa es o en.']}, status=400)
    try:
        if pdf:
            response = HttpResponse(BuildingWithUsPdfService.build(language=language), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="building-with-us-{language}.pdf"'
            response['Cache-Control'] = 'private, no-store'
            return response
        return Response(service.serialize_public_program(language), headers={'Cache-Control': 'no-store'})
    except BuildingWithUsError as exc:
        return _error_response(exc)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_building_with_us_program(request):
    return _public_response(request)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_building_with_us_program_pdf(request):
    return _public_response(request, pdf=True)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_building_with_us_overview(request):
    try:
        return Response(service.admin_overview())
    except BuildingWithUsError as exc:
        return _error_response(exc)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_building_with_us_program_versions(request):
    try:
        limit = int(request.query_params.get('limit', '20'))
        offset = int(request.query_params.get('offset', '0'))
    except (ValueError, TypeError):
        return Response({'limit': ['Usa un entero entre 1 y 50.'], 'offset': ['Usa un entero no negativo.']}, status=400)
    try:
        return Response(service.list_versions(limit=limit, offset=offset))
    except BuildingWithUsError as exc:
        return _error_response(exc)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_building_with_us_contract(request):
    try:
        return Response(contract_service.read_contract())
    except BuildingWithUsError as exc:
        return _error_response(exc)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_building_with_us_contract_versions(request):
    try:
        limit = int(request.query_params.get('limit', '20'))
        offset = int(request.query_params.get('offset', '0'))
    except (ValueError, TypeError):
        return Response({'limit': ['Usa un entero entre 1 y 50.'], 'offset': ['Usa un entero no negativo.']}, status=400)
    try:
        return Response(contract_service.list_versions(limit=limit, offset=offset))
    except BuildingWithUsError as exc:
        return _error_response(exc)


@xframe_options_sameorigin
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_building_with_us_contract_pdf(request):
    try:
        pdf, version = contract_service.current_pdf()
    except BuildingWithUsError as exc:
        return _error_response(exc)
    disposition = 'inline' if request.query_params.get('inline') == '1' else 'attachment'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'{disposition}; filename="contrato-building-with-us-v{version}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response
