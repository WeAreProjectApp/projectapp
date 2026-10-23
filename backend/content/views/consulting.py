"""Public consulting brochure and session-authenticated editorial overview."""
from django.http import HttpResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from content.services import consulting_program_service as service
from content.services.consulting_content import ConsultingError
from content.services.consulting_pdf_service import ConsultingPdfService


def _error(error):
    return Response({'message': str(error), 'code': error.code, 'details': error.details},
                    status=404 if error.code == 'NOT_FOUND' else 400)


def _public_response(request, *, pdf=False):
    language = request.query_params.get('lang', 'es')
    if language not in ('es', 'en'):
        return Response({'lang': ['Usa es o en.']}, status=400)
    try:
        if pdf:
            response = HttpResponse(ConsultingPdfService.build(language=language), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="consulting-{language}.pdf"'
            response['Cache-Control'] = 'private, no-store'
            return response
        return Response(service.serialize_public_program(language), headers={'Cache-Control': 'no-store'})
    except ConsultingError as error:
        return _error(error)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_consulting_program(request):
    return _public_response(request)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_consulting_program_pdf(request):
    return _public_response(request, pdf=True)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_consulting_overview(request):
    try:
        return Response(service.admin_overview())
    except ConsultingError as error:
        return _error(error)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_consulting_program_versions(request):
    try:
        return Response(service.list_versions(limit=int(request.query_params.get('limit', '20')),
                                              offset=int(request.query_params.get('offset', '0'))))
    except (TypeError, ValueError) as error:
        if isinstance(error, ConsultingError):
            return _error(error)
        return Response({'message': 'Usa limit entre 1 y 50 y offset no negativo.'}, status=400)
