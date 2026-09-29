"""Administrative endpoints for formal proposal documents and delivery review."""
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import BusinessProposal, ProposalFormalization
from content.serializers.formalization import FormalizationPrepareSerializer
from content.services import proposal_formalization_service as service
from content.services.formalization_content import FormalizationError
from content.services.pdf_utils import safe_pdf_filename


def _proposal(pk):
    get_object_or_404(BusinessProposal, pk=pk)
    return service.load_proposal(pk)


def _preparation(request, proposal_id, preparation_id):
    return get_object_or_404(
        ProposalFormalization.objects.select_related('proposal__client').prefetch_related('files'),
        pk=preparation_id, proposal_id=proposal_id, created_by=request.user,
        mcp_credential__isnull=True,
    )


def _response(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


def _error(exc):
    return _response({'error': str(exc), 'code': exc.code}, exc.status)


def _payload(preparation):
    root = f'/api/proposals/{preparation.proposal_id}/formalization/preparations/{preparation.pk}/'
    return {
        'id': str(preparation.pk), 'status': preparation.status,
        'error': preparation.error, 'expires_at': preparation.expires_at,
        'subject': preparation.payload['subject'],
        'recipient_emails': preparation.payload['recipient_emails'],
        'cc_emails': preparation.payload['cc_emails'],
        'html_preview': preparation.html_body,
        'files': [{'key': f.key, 'filename': f.filename, 'description': f.description, 'mime_type': f.mime_type, 'size': f.size, 'sha256': f.sha256, 'url': f'{root}files/{f.pk}/'} for f in preparation.files.all()],
    }


@api_view(['GET'])
@permission_classes([IsAdminUser])
def formalization_options(request, proposal_id):
    proposal = _proposal(proposal_id)
    return _response({'defaults': service.defaults(proposal), 'documents': service.availability(proposal)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def formalization_pdf(request, proposal_id, kind):
    proposal = _proposal(proposal_id)
    try:
        data = service.document_bytes(proposal, kind)
    except FormalizationError as exc:
        return _error(exc)
    name = safe_pdf_filename(service.DOCUMENTS[kind][0], proposal.title, timezone.now().strftime('%Y-%m-%d'))
    response = HttpResponse(data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    response['Cache-Control'] = 'private, no-store'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
def prepare_formalization(request, proposal_id):
    proposal = _proposal(proposal_id)
    serializer = FormalizationPrepareSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        preparation = service.prepare(proposal, request.user, serializer.validated_data)
    except FormalizationError as exc:
        return _error(exc)
    return _response(_payload(preparation), 201)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def retrieve_formalization(request, proposal_id, preparation_id):
    preparation = _preparation(request, proposal_id, preparation_id)
    if preparation.expires_at <= timezone.now():
        return _response({'error': 'La preparación venció. Prepara nuevamente el correo.', 'code': 'expired_preparation'}, 410)
    return _response(_payload(preparation))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def formalization_attachment(request, proposal_id, preparation_id, file_id):
    preparation = _preparation(request, proposal_id, preparation_id)
    if preparation.expires_at <= timezone.now():
        return _response({'error': 'La preparación venció.'}, 410)
    attachment = get_object_or_404(preparation.files, pk=file_id)
    response = FileResponse(attachment.file.open('rb'), as_attachment=True, filename=attachment.filename, content_type=attachment.mime_type)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['POST'])
@permission_classes([IsAdminUser])
def send_formalization(request, proposal_id, preparation_id):
    preparation = _preparation(request, proposal_id, preparation_id)
    try:
        service.send_preparation(preparation)
    except FormalizationError as exc:
        return _error(exc)
    return _response(_payload(preparation), 200 if preparation.status == 'sent' else 502)
