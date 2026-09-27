"""Admin-only read endpoints for copying and downloading proposal documents."""
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from content.models import BusinessProposal, ProposalDocument
from content.services.attachment_markdown import extract_attachment_markdown
from content.services.contract_variants import contract_document
from content.services.formalization_content import FormalContent, FormalizationError
from content.services.formalization_markdown import generate_formal_markdown
from content.services.markdown_export import MarkdownExportError, export_payload
from content.services.proposal_formalization_service import load_proposal


def private_response(data, status=200):
    response = Response(data, status=status)
    response['Cache-Control'] = 'private, no-store'
    return response


def markdown_response(operation):
    try:
        return private_response(operation())
    except (MarkdownExportError, FormalizationError) as exc:
        return private_response({'error': str(exc), 'code': exc.code}, exc.status)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def contract_markdown(request, proposal_id):
    from content.views.proposal import _requested_variant

    proposal = get_object_or_404(BusinessProposal, pk=proposal_id)
    variant, error = _requested_variant(proposal, request.query_params.get('variant'))
    if error:
        return private_response(error.data, error.status_code)
    document = contract_document(proposal, variant)
    if document is None:
        return private_response({'error': 'Genera el contrato primero.', 'code': 'contract_missing'}, 404)
    if not document.file or not document.file.storage.exists(document.file.name):
        return private_response({'error': 'El archivo ya no está disponible.', 'code': 'file_missing'}, 404)
    if document.content_markdown:
        return markdown_response(lambda: export_payload(document.title, document.content_markdown))
    return markdown_response(lambda: extract_attachment_markdown(document))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def formalization_markdown(request, proposal_id, kind):
    get_object_or_404(BusinessProposal, pk=proposal_id)
    return markdown_response(lambda: generate_formal_markdown(
        FormalContent(load_proposal(proposal_id)), kind, timezone.now(), f'PROP-{proposal_id}',
    ))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def attachment_markdown(request, proposal_id, doc_id):
    document = get_object_or_404(ProposalDocument, proposal_id=proposal_id, pk=doc_id)
    return markdown_response(lambda: extract_attachment_markdown(document))


@api_view(['GET'])
@permission_classes([IsAdminUser])
def attachment_download(request, proposal_id, doc_id):
    document = get_object_or_404(ProposalDocument, proposal_id=proposal_id, pk=doc_id)
    try:
        source = document.file.open('rb')
    except (OSError, ValueError):
        return private_response({'error': 'El archivo ya no está disponible.', 'code': 'file_missing'}, 404)
    response = FileResponse(source, as_attachment=True)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
