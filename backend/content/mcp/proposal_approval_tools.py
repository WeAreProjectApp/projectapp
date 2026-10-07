"""Confirmed approval review using the Panel contract and credential-owned assets."""
import hashlib
from copy import deepcopy
from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError

from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments, writable_schema
from content.mcp.protocol import ToolError
from content.mcp.upload_tools import consume_upload, _validate_declared_content
from content.serializers.panel_projects import CreatePanelProjectSerializer
from content.serializers.proposal_approval import ApprovalCustomDocumentSerializer, ProposalApprovalSerializer

PROJECT = writable_schema(CreatePanelProjectSerializer, exclude=('client_profile_id',))
CUSTOM_DOCUMENT = writable_schema(ApprovalCustomDocumentSerializer)
APPROVAL_SCHEMA = writable_schema(ProposalApprovalSerializer)
APPROVAL_SCHEMA['properties']['new_project'] = PROJECT
APPROVAL_SCHEMA['properties']['custom_documents']['items'] = CUSTOM_DOCUMENT
APPROVAL_SCHEMA['properties']['source_hash']['description'] = (
    'Huella vigente de get_proposal_approval; obligatoria para confirm.'
)
APPROVAL_SCHEMA['properties']['request_id']['description'] = (
    'Identificador estable y único de esta confirmación para reintentos idempotentes.'
)
APPROVAL_SCHEMA['properties']['custom_documents']['description'] = (
    'Título y tipo por adjunto, en el mismo orden que custom_asset_ids; sólo con contratos de propuesta desactivados.'
)
CONTENT_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword', 'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/jpeg', 'image/png',
}


def _safe_payload(payload):
    """Private download links require their own authorized artifact operation."""
    payload = deepcopy(payload)
    for item in payload.get('confirmed_files', []):
        item.pop('download_url', None)
    return payload


def _preview(arguments):
    tool = _op('approval_preview', 'Consulta el paquete y la vinculación antes de aprobar.',
               'proposal-approval', path=('proposal_id',))
    return _safe_payload(tool['handler']({'proposal_id': arguments['proposal_id']}))


def _prepare(tool, arguments, *, launch=False):
    check_known_fields(arguments, tool['input_schema'])
    arguments = guarded_arguments(arguments, tool)
    if isinstance(arguments.get('proposal_id'), bool) or not isinstance(arguments.get('proposal_id'), (int, str)):
        raise ToolError('proposal_id debe identificar una propuesta.')
    try:
        proposal_id = int(arguments.get('proposal_id'))
    except (TypeError, ValueError) as exc:
        raise ToolError('proposal_id debe identificar una propuesta.') from exc
    if proposal_id < 1:
        raise ToolError('proposal_id debe identificar una propuesta.')
    arguments['proposal_id'] = proposal_id
    data = arguments.pop('data', {})
    arguments.update(data)
    arguments.setdefault('action', 'confirm')
    if launch and arguments['action'] != 'retry':
        arguments.setdefault('accept_proposal', False)
    if arguments['action'] not in ('confirm', 'defer', 'retry'):
        raise ToolError('action debe ser confirm, defer o retry.')
    assets = arguments.get('custom_asset_ids', [])
    documents = arguments.get('custom_documents', [])
    if not isinstance(assets, list) or not isinstance(documents, list):
        raise ToolError('custom_asset_ids y custom_documents deben ser listas.')
    if any(not isinstance(asset_id, str) for asset_id in assets) or len(set(assets)) != len(assets):
        raise ToolError('Selecciona identificadores únicos de adjuntos completados.')
    try:
        for asset_id in assets:
            UUID(asset_id)
    except ValueError as exc:
        raise ToolError('Los identificadores de adjuntos deben ser UUID válidos.') from exc
    for document in documents:
        check_known_fields(document, CUSTOM_DOCUMENT)
    if len(assets) != len(documents):
        raise ToolError('Cada adjunto personalizado necesita sus metadatos en el mismo orden.')
    if arguments['action'] != 'confirm' and (assets or documents):
        raise ToolError('Posponer o reintentar no admite un paquete nuevo.')
    serializer = ProposalApprovalSerializer(data={
        key: value for key, value in arguments.items()
        if key in APPROVAL_SCHEMA['properties']
    })
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        raise ToolError('Revisa los datos de aprobación.', details=exc.detail) from exc
    return arguments


@transaction.atomic
def _resource_versions(arguments):
    preview = _preview(arguments)
    versions = {'source_hash': preview['source_hash'], 'assets': []}
    for asset_id in arguments.get('custom_asset_ids', []):
        upload = consume_upload(asset_id, allowed_content_types=CONTENT_TYPES)
        try:
            with upload.file.open('rb') as source:
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: source.read(64 * 1024), b''):
                    digest.update(chunk)
                    size += len(chunk)
            _validate_declared_content(upload)
        except (OSError, ValueError) as exc:
            raise ToolError('El adjunto ya no está disponible.', code='ATTACHMENT_CHANGED') from exc
        if digest.hexdigest() != upload.expected_sha256 or size != upload.expected_size:
            raise ToolError('El contenido del adjunto cambió.', code='ATTACHMENT_CHANGED')
        versions['assets'].append({
            'asset_id': str(upload.pk), 'sha256': digest.hexdigest(), 'size': size,
            'filename': upload.filename, 'content_type': upload.content_type,
        })
    return versions


def _impact(arguments):
    preview = _preview(arguments)
    if arguments['action'] != 'defer' and preview.get('project_reassignment_required'):
        # Fail before a confirmation exists: the review can never bind a
        # deliverable retained from a deleted project.
        raise ToolError(
            'El entregable de esta propuesta quedó conservado de un proyecto eliminado; '
            'la revisión de aprobación no puede vincularlo.',
            code='RETAINED_PROJECT',
            details={'linked_project': preview.get('linked_project')},
        )
    versions = _resource_versions(arguments)
    if arguments['action'] == 'confirm' and arguments.get('source_hash') != versions['source_hash']:
        raise ToolError('La propuesta cambió. Consulta la revisión actual antes de confirmar.',
                        code='STALE_VERSION')
    return {
        'summary': 'Confirmar exactamente la revisión sin sustituir datos de un proyecto operativo.',
        'action': arguments['action'], 'proposal_id': arguments['proposal_id'],
        'review': preview,
        'selection': {key: value for key, value in arguments.items()
                      if key not in {'proposal_id', 'query', 'if_match', 'custom_asset_ids'}},
        'custom_assets': versions['assets'],
    }


def _mutation(name, description, *, launch=False):
    tool = _op(name, description, 'proposal-approval', 'POST', ('proposal_id',),
               'sensitive', True, payload_schema=deepcopy(APPROVAL_SCHEMA), assets={
                   'custom_asset_ids': {'field': 'custom_files[]', 'many': True,
                                        'content_types': sorted(CONTENT_TYPES)},
               })
    if launch:
        tool['input_schema']['properties']['accept_proposal']['default'] = False
    tool['input_schema']['properties']['custom_asset_ids']['description'] = (
        'Assets completados de esta credencial, en el mismo orden que custom_documents; no URLs ni base64.'
    )
    bridge = tool['handler']
    tool['prepare_arguments'] = lambda arguments: _prepare(tool, arguments, launch=launch)
    tool['handler'] = lambda arguments: _safe_payload(bridge(_prepare(tool, arguments, launch=launch)))
    tool['impact_builder'] = _impact
    tool['etag_resolver'] = _resource_versions
    return tool


PREVIEW_TOOL = _op('get_proposal_approval',
                   'Consulta cliente, proyecto y archivos del cierre sin crear ningún registro.',
                   'proposal-approval', path=('proposal_id',))
_preview_bridge = PREVIEW_TOOL['handler']
PREVIEW_TOOL['handler'] = lambda arguments: _safe_payload(_preview_bridge(arguments))

PROPOSAL_APPROVAL_TOOLS = [
    PREVIEW_TOOL,
    _mutation('review_proposal_approval',
              'Revisa y confirma cliente, proyecto y documentos usando source_hash de get_proposal_approval y request_id estable. '
              'action=defer acepta sin proyecto; retry conserva el paquete. confirm_action aplica la selección exacta.'),
    _mutation('launch_proposal_to_platform',
              'Vincula explícitamente cliente y proyecto o reintenta el mismo paquete; nunca recrea ni purga un proyecto operativo.',
              launch=True),
    _op('download_proposal_approval_file',
        'Descarga un archivo privado del cierre autorizado como asset temporal de esta credencial.',
        'proposal-approval-file-download', path=('proposal_id', 'file_id')),
]
