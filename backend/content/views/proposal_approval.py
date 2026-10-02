"""Session-only review and guarded private approval-package downloads."""
import json
import hashlib
import mimetypes
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from accounts.authentication import SessionJWTAuthentication
from accounts.services.archive import deliverable_visible_for_request
from content.models import ProposalApprovalFile
from content.services.proposal_approval_service import load_proposal, preview, review_proposal


def decode_payload(request):
    if 'payload' in request.data:
        try:
            value = json.loads(request.data['payload'])
        except (ValueError, TypeError) as exc:
            raise ValidationError({'payload': 'El contenido debe ser un objeto JSON válido.'}) from exc
    else:
        value = dict(request.data) if not hasattr(request.data, 'getlist') else {key: request.data.get(key) for key in request.data}
        for field in ('new_client', 'new_project', 'custom_documents', 'selected_document_ids'):
            if isinstance(value.get(field), str):
                try:
                    value[field] = json.loads(value[field])
                except ValueError as exc:
                    raise ValidationError({field: 'El contenido JSON no es válido.'}) from exc
    if not isinstance(value, dict):
        raise ValidationError({'payload': 'Se requiere un objeto JSON.'})
    return value


@api_view(['GET', 'POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def approval_review(request, proposal_id):
    from content.models import BusinessProposal
    get_object_or_404(BusinessProposal, pk=proposal_id)
    if request.method == 'GET':
        return Response(preview(load_proposal(proposal_id)))
    files = request.FILES.getlist('custom_files[]') or request.FILES.getlist('custom_files')
    return Response(review_proposal(proposal_id, decode_payload(request), actor=request.user, files=files))


def _download(row):
    try:
        stream = row.file.open('rb')
    except (OSError, ValueError):
        from rest_framework.exceptions import NotFound
        raise NotFound('El archivo no está disponible.')
    hasher, size = hashlib.sha256(), 0
    for chunk in iter(lambda: stream.read(64 * 1024), b''):
        hasher.update(chunk)
        size += len(chunk)
    if size != row.size or hasher.hexdigest() != row.sha256:
        stream.close()
        from rest_framework.exceptions import NotFound
        raise NotFound('El archivo no coincide con el paquete confirmado.')
    stream.seek(0)
    response = FileResponse(stream, as_attachment=True, filename=row.filename, content_type=mimetypes.guess_type(row.filename)[0] or 'application/octet-stream')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAdminUser])
def approval_file_download(request, proposal_id, file_id):
    return _download(get_object_or_404(ProposalApprovalFile, pk=file_id, proposal_id=proposal_id))


@api_view(['GET'])
@authentication_classes([SessionJWTAuthentication])
@permission_classes([IsAuthenticated])
def platform_approval_file_download(request, project_id, file_id):
    from accounts.views import _get_project_or_403
    project, error = _get_project_or_403(request, project_id)
    if error:
        return error
    row = get_object_or_404(ProposalApprovalFile.objects.select_related('deliverable'), pk=file_id, project=project)
    if not deliverable_visible_for_request(row.deliverable, request):
        from rest_framework.exceptions import NotFound
        raise NotFound('El archivo no está disponible.')
    return _download(row)
