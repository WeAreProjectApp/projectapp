"""Authorized, exact contractual files from confirmed approval packages.

Selecting a package file never establishes a signature. Once a signature is
recorded, its private PDF is the canonical contractual copy for reads/captures.
"""
import hashlib
import mimetypes
from pathlib import PurePosixPath

from content.models import ProposalApprovalFile
from rest_framework.exceptions import NotFound

from accounts.services.delivery_access import fail, project_for_actor

SOURCE_FIELDS = ('document_id', 'proposal_document_id', 'approval_file_id')
MAX_SOURCE_BYTES = 15 * 1024 * 1024
MAX_SIGNED_BYTES = 10 * 1024 * 1024


def _confirmed_for_project(source, project):
    proposal = source.proposal
    manifest = proposal.platform_approval_manifest
    if (source.project_id != project.pk or source.deliverable.project_id != project.pk
            or proposal.deliverable_id != source.deliverable_id or not proposal.client_id
            or proposal.client.user_id != project.client_id or not isinstance(manifest, dict)
            or manifest.get('client_profile_id') != proposal.client_id):
        return False
    entries = manifest.get('files')
    return isinstance(entries, list) and any(
        isinstance(item, dict) and item.get('id') == source.pk
        and item.get('source_key') == source.source_key and item.get('sha256') == source.sha256
        and item.get('size') == source.size for item in entries
    )


def _approval_files(project):
    return ProposalApprovalFile.objects.filter(project=project).select_related(
        'proposal__client', 'deliverable',
    ).order_by('id')


def approval_file_for_project(project, source_id):
    source = _approval_files(project).filter(pk=source_id).first()
    if source is None or not _confirmed_for_project(source, project):
        fail('Selecciona un archivo del paquete confirmado de este proyecto y cliente.', 'document_context')
    return source


def file_metadata(source):
    filename = PurePosixPath(source.filename).name
    return {'id': source.pk, 'title': source.title, 'filename': filename,
            'document_type': source.document_type, 'proposal_id': source.proposal_id,
            'size': source.size, 'sha256': source.sha256,
            'content_type': mimetypes.guess_type(filename)[0] or 'application/octet-stream',
            'confirmed_at': source.created_at.isoformat()}


def approval_file_options(project):
    return [file_metadata(source) for source in _approval_files(project)
            if _confirmed_for_project(source, project)]


def _read_exact(file, *, expected_hash, max_bytes, expected_size=None):
    try:
        with file.open('rb') as stream:
            raw = stream.read(max_bytes + 1)
    except (OSError, ValueError):
        fail('La copia contractual conservada no está disponible.', 'contract_source_unavailable')
    if not raw or len(raw) > max_bytes:
        fail('La copia contractual está vacía o supera el límite permitido.', 'contract_source_invalid')
    if ((expected_size is not None and len(raw) != expected_size)
            or hashlib.sha256(raw).hexdigest() != expected_hash):
        fail('La copia contractual no coincide con la huella conservada.', 'contract_source_integrity')
    return raw


def read_approval_file(source):
    return _read_exact(source.file, expected_hash=source.sha256,
                       expected_size=source.size, max_bytes=MAX_SOURCE_BYTES)


def signed_contract_source(node):
    """Return verified private signature bytes, or None for an unsigned node."""
    evidence = node.signature_evidence.first()
    if evidence is None:
        return None
    raw = _read_exact(evidence.file, expected_hash=evidence.sha256, max_bytes=MAX_SIGNED_BYTES)
    if not raw.startswith(b'%PDF-'):
        fail('La copia firmada conservada no es un PDF válido.', 'contract_source_invalid')
    return {'raw': raw, 'filename': 'signed-contract.pdf', 'content_type': 'application/pdf',
            'sha256': evidence.sha256, 'title': evidence.title, 'evidence': evidence,
            'snapshot': evidence.source_snapshot, 'date': evidence.signed_at}


def signed_source_for_link(link):
    """Only the contractual source itself inherits its verified signature PDF.

    Other attachments at the same contract/amendment level remain independent
    documents; associating an annex must never replace it with the contract.
    """
    if link.level not in ('contract', 'amendment'):
        return None
    node = getattr(link, link.level)
    if node is None or node.document_id != link.document_id:
        return None
    return signed_contract_source(node)


def approval_contract_source(node):
    """Prefer the exact signed PDF over the unsigned confirmed package file."""
    source = approval_file_for_project(node.project, node.approval_file_id)
    signed = signed_contract_source(node)
    if signed is not None:
        return signed
    metadata = file_metadata(source)
    return {'raw': read_approval_file(source), 'filename': metadata['filename'],
            'content_type': metadata['content_type'], 'sha256': source.sha256,
            'title': source.title, 'evidence': None, 'snapshot': metadata,
            'date': source.created_at}


def contract_source_file(project_id, actor, kind, node_id):
    """Authenticated source download retaining the original unsigned format."""
    from accounts.services.delivery_workflow import _level_visible, _node

    project = project_for_actor(project_id, actor)
    if kind not in ('contracts', 'amendments'):
        fail('Tipo de documento contractual desconocido.')
    node = _node(project, kind, node_id)
    level = 'contract' if kind == 'contracts' else 'amendment'
    if not node.approval_file_id or not _level_visible(project, actor, level, node):
        raise NotFound('Fuente contractual no disponible.')
    source = approval_contract_source(node)
    return source['raw'], source['filename'], source['content_type']
