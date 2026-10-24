"""Session/CSRF administration and strictly JWT-authenticated client AI jobs."""
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from accounts.authentication import SessionJWTAuthentication
from accounts.models import UserProfile
from accounts.models_ai import PlatformAIEvent, PlatformAITemplate
from accounts.serializers_ai import (CredentialSerializer, TemplateSerializer, TemplateRestoreSerializer,
    TranscriptionSerializer, ReportDraftSerializer, validated)
from accounts.services import platform_ai as service
from accounts.services import platform_ai_templates as templates
from accounts.services import platform_ai_jobs as jobs


def private_response(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'no-store'
    return response


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def settings_view(request):
    data = service.update_settings(request.user, request.data) if request.method == 'PATCH' else service.admin_settings(request.user)
    return private_response(data)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def clients_view(request):
    from django.core.paginator import Paginator
    try:
        page = int(request.query_params.get('page', 1))
        if page < 1:
            raise ValueError
    except ValueError:
        raise ValidationError('Página no válida.') from None
    query = request.query_params.get('search', '')[:200]
    rows = UserProfile.objects.clients().select_related('user').filter(
        Q(user__email__icontains=query) | Q(user__first_name__icontains=query) | Q(company_name__icontains=query)).order_by('user_id')
    pager = Paginator(rows, 20)
    result = pager.get_page(page)
    return private_response({'results': [service.client_data(row) for row in result], 'count': pager.count, 'page': result.number})


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def client_view(request, user_id):
    return private_response(service.client_flags(request.user, user_id, request.data if request.method == 'PATCH' else None))


@api_view(['PUT', 'DELETE'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def credential_view(request, provider):
    if request.method == 'DELETE':
        try:
            expected = int(request.data['expected_version'])
        except (KeyError, ValueError, TypeError):
            raise ValidationError('Indica la versión de la credencial.') from None
        return private_response(service.set_credential(request.user, provider, expected_version=expected, remove=True))
    values = validated(CredentialSerializer, request.data)
    try:
        return private_response(service.set_credential(request.user, provider, **values))
    except ImproperlyConfigured:
        raise service.AIUnavailable('La llave de cifrado de IA no está configurada en el servidor.') from None


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def credential_test_view(request, provider):
    from accounts.services.platform_ai_providers import test_credential
    return private_response(test_credential(request.user, provider))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def templates_view(request):
    return private_response([templates.template_data(item) for item in PlatformAITemplate.objects.order_by('family', 'scenario', 'language')])


@api_view(['GET', 'PATCH'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def template_view(request, template_id):
    if request.method == 'PATCH':
        return private_response(templates.update_template(template_id, request.user, **validated(TemplateSerializer, request.data)))
    item = PlatformAITemplate.objects.filter(pk=template_id).first()
    if not item:
        raise NotFound('Plantilla no encontrada.')
    return private_response(templates.template_data(item))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def template_versions_view(request, template_id):
    item = PlatformAITemplate.objects.filter(pk=template_id).first()
    if not item:
        raise NotFound('Plantilla no encontrada.')
    return private_response(list(item.revisions.order_by('-version').values('version', 'content', 'created_at')[:50]))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def template_restore_view(request, template_id):
    values = validated(TemplateRestoreSerializer, request.data)
    return private_response(templates.update_template(template_id, request.user, '', values['expected_version'], restore_version=values['version']))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def template_preview_view(request, template_id):
    item = PlatformAITemplate.objects.filter(pk=template_id).first()
    if not item:
        raise NotFound('Plantilla no encontrada.')
    values = validated(TemplateSerializer, request.data)
    service.check_version(item.version, values['expected_version'])
    content = templates.validate_content(item.family, item.scenario, values['content'])
    sample = {name: name.replace('_', ' ') for name in templates.CHAT_SLOTS.get(item.scenario, set())} if item.family == 'chatbot' else {}
    return private_response({'preview': content.format(**sample), 'provider_called': False})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def usage_view(request):
    return private_response(service.usage_summary(request.user))


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def events_view(request):
    return private_response(list(PlatformAIEvent.objects.order_by('-id').values('id', 'action', 'target', 'metadata', 'created_at')[:50]))


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def invalidate_view(request):
    return private_response(service.invalidate_cache(request.user, request.data.get('function')))


@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def capabilities_view(request):
    return private_response(service.ai_capabilities(request.user))


@api_view(['GET', 'POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def transcriptions_view(request):
    if request.method == 'GET':
        from django.utils import timezone
        from accounts.models_ai import PlatformAIJob
        purpose = request.query_params.get('purpose')
        if purpose not in ('chatbot', 'voice_report'):
            raise ValidationError('Propósito no válido.')
        project_id = request.query_params.get('project_id')
        project = service.require_ai_feature(request.user, jobs._feature(purpose), project_id)
        rows = PlatformAIJob.objects.filter(actor=request.user, project=project, purpose=purpose, status='ready', expires_at__gt=timezone.now()).order_by('-created_at')[:10]
        return private_response([{'id': str(item.pk), 'operation': item.operation, 'scenario': item.payload.get('scenario'), 'created_at': item.created_at} for item in rows])
    item = jobs.create_transcription(request.user, validated(TranscriptionSerializer, request.data))
    item.refresh_from_db()
    return private_response(jobs.job_data(item), 202)


@api_view(['GET', 'DELETE'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def job_view(request, job_id):
    if request.method == 'DELETE':
        jobs.discard_job(request.user, job_id)
        return private_response({'discarded': True})
    return private_response(jobs.job_data(jobs.owned_job(request.user, job_id)))


@api_view(['POST'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def report_drafts_view(request, project_id):
    item = jobs.create_report_draft(request.user, project_id, validated(ReportDraftSerializer, request.data))
    item.refresh_from_db()
    return private_response(jobs.job_data(item), 202)
