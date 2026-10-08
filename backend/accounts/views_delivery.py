"""Thin JWT endpoints over the shared delivery services."""
from django.db import transaction
from django.http import HttpResponse
from django.utils.text import slugify
from django.utils.http import content_disposition_header
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.authentication import SessionJWTAuthentication

from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_access import fail
from accounts.services.delivery_review_evidence import list_review_evidence, review_evidence_pdf
from accounts.services import delivery_authoring as authoring
from accounts.services import delivery_closure_email as closure_email
from accounts.serializers_delivery import VersionedSerializer
from accounts.services._platform_authority import platform_role_boundary


def delivery_endpoint(methods):
    def decorate(view):
        return api_view(methods)(authentication_classes([SessionJWTAuthentication])(
            permission_classes([IsAuthenticated])(platform_role_boundary(view)),
        ))
    return decorate


@delivery_endpoint(['GET'])
def delivery_overview(request, project_id):
    return Response(delivery.overview(project_id, request.user))


@delivery_endpoint(['POST', 'PATCH', 'DELETE'])
def delivery_node(request, project_id, kind, node_id=None):
    if request.method == 'POST' and node_id is not None:
        fail('Usa PATCH para editar el elemento.')
    if request.method != 'POST' and node_id is None:
        fail('Indica el elemento que quieres modificar.')
    result = delivery.mutate_node(project_id, request.user, kind, request.data, node_id=node_id, delete=request.method == 'DELETE')
    return Response(result, status=201 if request.method == 'POST' else 200)


@delivery_endpoint(['GET', 'POST'])
def delivery_prompt(request, project_id):
    if request.method == 'POST':
        return Response(authoring.create_prompt_context(project_id, request.user, request.data), status=201)
    return Response(authoring.prompt_options(project_id, request.user))


@delivery_endpoint(['GET'])
def delivery_prompt_options(request, project_id):
    return Response(authoring.prompt_options(project_id, request.user))


@delivery_endpoint(['GET'])
def delivery_prompt_context(request, project_id, context_id):
    return Response(authoring.get_prompt_context(project_id, request.user, context_id))


@delivery_endpoint(['GET'])
def delivery_prompt_contexts(request, project_id):
    return Response(authoring.list_prompt_contexts(project_id, request.user))


@delivery_endpoint(['GET'])
def delivery_prompt_source_download(request, project_id, context_id, source_key):
    raw, filename, content_type = authoring.prompt_source_file(project_id, request.user, context_id, source_key)
    response = HttpResponse(raw, content_type=content_type)
    response['Content-Disposition'] = content_disposition_header(True, filename)
    response['Cache-Control'] = 'private, no-store'
    return response


@delivery_endpoint(['POST'])
def delivery_reply_preview(request, project_id):
    if not isinstance(request.data, dict) or set(request.data) - {'payload', 'expected_version', 'request_id'}:
        fail('La preparación de respuesta contiene campos no permitidos.')
    serializer = VersionedSerializer(data={key: value for key, value in request.data.items() if key != 'payload'})
    serializer.is_valid(raise_exception=True)
    return Response(authoring.preview_reply(project_id, request.user, request.data.get('payload'),
                                           serializer.validated_data['expected_version']))


@delivery_endpoint(['POST'])
def delivery_import(request, project_id, apply=False):
    if not isinstance(request.data, dict):
        fail('Se esperaba un objeto JSON.')
    unknown = set(request.data) - {'payload', 'expected_version', 'request_id'}
    if unknown:
        fail('La importación contiene campos no permitidos.')
    return Response(delivery.import_payload(project_id, request.user, request.data.get('payload'),
                                           request.data.get('expected_version'), apply=apply,
                                           request_id=request.data.get('request_id')))


@delivery_endpoint(['POST'])
def delivery_publish(request, project_id, stage_id):
    return Response(delivery.publish_stage(project_id, request.user, stage_id, request.data))


@delivery_endpoint(['POST'])
def delivery_review(request, project_id, stage_id, historical=False):
    if request.auth and request.auth.get('impersonated_by'):
        raise PermissionDenied('Inicia sesión con tu propia cuenta de cliente para registrar una revisión.')
    return Response(delivery.review_stage(project_id, request.user, stage_id, request.data, historical=historical))


@delivery_endpoint(['POST'])
def delivery_messages(request, project_id):
    return Response(delivery.add_message(project_id, request.user, request.data), status=201)


@delivery_endpoint(['GET', 'POST'])
def delivery_documents(request, project_id):
    if request.method == 'POST':
        return Response(delivery.link_document(project_id, request.user, request.data), status=201)
    target_id = request.query_params.get('target_id')
    if target_id is not None:
        try:
            target_id = int(target_id)
        except (ValueError, TypeError):
            fail('El identificador documental debe ser un entero.')
    return Response(delivery.list_documents(project_id, request.user, request.query_params.get('level'), target_id))


@delivery_endpoint(['DELETE'])
def delivery_document_delete(request, project_id, link_id):
    return Response(delivery.unlink_document(project_id, request.user, link_id, request.data))


@delivery_endpoint(['GET'])
def delivery_document_options(request, project_id):
    return Response(delivery.document_options(project_id, request.user))


@delivery_endpoint(['GET'])
def delivery_evidence_options(request, project_id):
    return Response(delivery.evidence_options(project_id, request.user))


def _pdf_response(result):
    pdf, title = result
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = slugify(title) or 'documento'
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    return response


@delivery_endpoint(['GET'])
def delivery_document_pdf(request, project_id, link_id):
    return _pdf_response(delivery.document_pdf(project_id, request.user, link_id))


@delivery_endpoint(['GET'])
def delivery_review_evidence_list(request, project_id, review_id):
    return Response(list_review_evidence(project_id, request.user, review_id))


@delivery_endpoint(['GET'])
def delivery_review_evidence_pdf(request, project_id, review_id, evidence_id):
    return _pdf_response(review_evidence_pdf(project_id, request.user, review_id, evidence_id))


@delivery_endpoint(['GET'])
def delivery_contract_pdf(request, project_id, kind, node_id):
    return _pdf_response(delivery.contract_pdf(project_id, request.user, kind, node_id))


@delivery_endpoint(['GET'])
def contract_source_download(request, project_id, kind, node_id):
    from accounts.services.delivery_contract_sources import contract_source_file

    raw, filename, content_type = contract_source_file(project_id, request.user, kind, node_id)
    response = HttpResponse(raw, content_type=content_type)
    response['Content-Disposition'] = content_disposition_header(True, filename)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@delivery_endpoint(['POST'])
def delivery_signature(request, project_id, kind, node_id):
    data = {key: request.data.get(key) for key in request.data if key != 'file'}
    return Response(delivery.attest_signature(project_id, request.user, kind, node_id, data, request.FILES.get('file')))


def _closure_response(data, *, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


@delivery_endpoint(['POST'])
def delivery_closure_email_prepare(request, project_id, stage_id):
    return _closure_response(closure_email.prepare_stage_email(
        project_id, request.user, stage_id, request.data,
    ), status=201)


@delivery_endpoint(['GET'])
def delivery_closure_email_history(request, project_id, stage_id):
    return _closure_response(closure_email.list_stage_emails(project_id, request.user, stage_id))


@delivery_endpoint(['GET'])
def delivery_closure_email_detail(request, project_id, preparation_id):
    return _closure_response(closure_email.get_preparation(project_id, request.user, preparation_id))


@transaction.non_atomic_requests
@delivery_endpoint(['POST'])
def delivery_closure_email_send(request, project_id, preparation_id):
    return _closure_response(closure_email.send_stage_email(
        project_id, request.user, preparation_id, request.data,
    ))


@delivery_endpoint(['POST'])
def delivery_closure_email_resend_prepare(request, project_id, preparation_id):
    return _closure_response(closure_email.prepare_stage_email_resend(
        project_id, request.user, preparation_id, request.data,
    ), status=201)


@delivery_endpoint(['GET'])
def delivery_closure_email_attachment(request, project_id, preparation_id, file_id):
    raw, filename, content_type = closure_email.download_attachment(
        project_id, request.user, preparation_id, file_id,
    )
    response = HttpResponse(raw, content_type=content_type)
    response['Content-Disposition'] = content_disposition_header(True, filename)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
