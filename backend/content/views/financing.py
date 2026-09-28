from content.services.video_resource_service import public_resource
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.services.explainer_video_service import explainer_video_visible
from content.services.financing_pdf_service import FinancingPdfService
from content.services.financing_program_service import serialize_financing_program


def _language_from_query(request):
    language = request.query_params.get('lang', 'es')
    return language if language in ('es', 'en') else None


def _invalid_language_response():
    return Response(
        {'lang': ['Usa es o en.']},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_financing_program(request):
    language = _language_from_query(request)
    if language is None:
        return _invalid_language_response()
    payload = serialize_financing_program(language=language)
    payload['explainer_video'] = public_resource('financing', language)
    payload['show_explainer_video'] = explainer_video_visible('financing')
    return Response(payload)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_financing_program_pdf(request):
    language = _language_from_query(request)
    if language is None:
        return _invalid_language_response()

    pdf_bytes = FinancingPdfService.build(language=language)
    filename = (
        'partnership-program.pdf'
        if language == 'en'
        else 'programa-de-alianza.pdf'
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'private, no-store'
    return response
