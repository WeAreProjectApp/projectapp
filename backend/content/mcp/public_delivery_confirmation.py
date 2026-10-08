"""Owned, exact confirmations for public effects over the existing services.

No client is impersonated and no new receipt, grant or version counter is added.
The project lock spans the last hash check and the native service call.
"""
import hashlib
from copy import deepcopy
from pathlib import Path, PurePosixPath

from accounts.models import DeliveryDocumentLink, DeliveryPublication, DeliveryWorkspace
from accounts.services import delivery_workflow as delivery
from accounts.services import issue_reports as issues
from accounts.services.delivery_access import project_for_actor
from accounts.services.delivery_documents import (
    DeliveryDocumentIndex,
    PortalDocumentIndex,
)
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import APIException

from content.mcp.confirmation import canonical_arguments_hash
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.models import Document

SEAL = '_public_effect_hash'
MAX_FILE_BYTES = 15 * 1024 * 1024
DELIVERY_PUBLIC_TOOLS = {
    'add_delivery_message', 'create_delivery_contract', 'update_delivery_contract',
    'create_delivery_amendment', 'update_delivery_amendment',
    'link_delivery_document', 'unlink_delivery_document',
}
ISSUE_PUBLIC_TOOLS = {'evaluate_issue_report', 'comment_issue_report', 'bulk_evaluate_issue_reports'}


def _file(file, *, filename=None):
    """Read one canonical file; previews never render, save or replace sources."""
    if not file:
        raise ToolError('Prepara la copia original del documento antes de confirmar su publicación.', code='SOURCE_UNAVAILABLE')
    try:
        with file.open('rb') as stream:
            body = stream.read(MAX_FILE_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ToolError('La copia original no está disponible.', code='SOURCE_UNAVAILABLE') from exc
    if not body or len(body) > MAX_FILE_BYTES:
        raise ToolError('La copia original está vacía o supera 15 MB.', code='SOURCE_UNAVAILABLE')
    return {'filename': filename or PurePosixPath(file.name).name,
            'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def _document(project, identifier, *, lock=False):
    query = Document.objects.filter(pk=identifier, is_archived=False).filter(
        Q(project=project) | Q(project__isnull=True, client_user_id=project.client_id),
    ).filter(Q(client_user__isnull=True) | Q(client_user_id=project.client_id))
    if lock:
        query = query.select_for_update()
    doc = query.first()
    if doc is None:
        raise ToolError('El documento no pertenece al cliente y proyecto seleccionados.', code='NOT_FOUND')
    return doc


def _renderer_provenance():
    """Bind unsigned render inputs to the existing renderer without producing PDF."""
    from content.services import (
        document_content,
        document_pdf_service,
        pdf_theme,
        pdf_utils,
    )
    digest = hashlib.sha256()
    for module in (document_pdf_service, document_content, pdf_theme, pdf_utils):
        digest.update(Path(module.__file__).read_bytes())
    for source in (pdf_utils.COVER_PDF, pdf_utils.BACK_COVER_PDF):
        path = Path(source)
        if path.is_file():
            digest.update(path.read_bytes())
    return {'renderer': 'DocumentPdfService', 'sha256': digest.hexdigest()}


def _document_state(doc, project):
    snapshot = _client_portal(project, doc).snapshot(doc)
    if snapshot is not None:
        file = _file(snapshot.file)
        if file['sha256'] != snapshot.sha256:
            raise ToolError('La copia publicada no coincide con su huella conservada.', code='SOURCE_INTEGRITY')
        return {'document_id': doc.pk, 'source_mode': 'published_snapshot',
                'snapshot_id': snapshot.pk, 'title': snapshot.title, 'file': file}
    state = {'document_id': doc.pk, 'title': doc.title,
            'content_markdown': doc.content_markdown, 'content_json': doc.content_json,
            'language': doc.language, 'template_style': doc.template_style,
            'client_visible': doc.is_client_visible, 'requires_signature': doc.requires_signature,
            'signed_at': str(doc.signed_at or ''), 'signed_by_id': doc.signed_by_id,
            'include_portada': doc.include_portada, 'include_subportada': doc.include_subportada,
            'include_contraportada': doc.include_contraportada, 'client_name': doc.client_name}
    if doc.generated_file:
        state['file'] = _file(doc.generated_file)
        state['source_mode'] = 'canonical_file'
    else:
        state['source_mode'] = 'render_on_read'
        state['renderer_provenance'] = _renderer_provenance()
        state['content_sha256'] = canonical_arguments_hash(state)
        state['file'] = None
        state['preparation'] = ('Se publica el contenido revisado; el portal genera su PDF al descargarlo. '
            'Para revisar una copia binaria exacta, prepara y conserva el PDF antes de volver a solicitar confirmación.')
    return state


def _contract_files(project, kind, arguments, node, *, lock=False):
    from accounts.services import delivery_contract_sources as sources
    data = arguments.get('data', {})
    result = []
    if node is not None:
        signed = sources.signed_contract_source(node)
        if signed:
            result.append({'kind': 'signed_contract', 'node_id': node.pk, 'title': signed['title'],
                'filename': signed['filename'], 'size': len(signed['raw']), 'sha256': signed['sha256']})
            return result
    for field in sources.SOURCE_FIELDS:
        identifier = data.get(field, getattr(node, field, None) if node is not None else None)
        if not identifier:
            continue
        if field == 'document_id':
            result.append(_document_state(_document(project, identifier, lock=lock), project))
        elif field == 'approval_file_id':
            source = sources.approval_file_for_project(project, identifier)
            raw = sources.read_approval_file(source)
            result.append({'approval_file_id': source.pk, 'title': source.title,
                'filename': source.filename, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        else:
            from content.models import ProposalDocument
            source = ProposalDocument.objects.filter(pk=identifier).filter(
                Q(proposal__project_phases__project=project) | Q(proposal__deliverable__project=project),
            ).distinct().first()
            if source is None:
                raise ToolError('La fuente de propuesta no pertenece al proyecto.', code='NOT_FOUND')
            result.append({'proposal_document_id': source.pk, 'title': source.title, **_file(source.file)})
    return result


def _client_portal(project, doc):
    """Restrict this read-only projection without changing a user or auth scope."""
    index = PortalDocumentIndex(project.client, [doc])
    index.index.admin = False
    return index


def _client_level_visible(project, level, target):
    """Use the real client's publication rules without an admin shortcut."""
    publications = list(DeliveryPublication.objects.filter(
        stage__phase__scope__contract__project=project).select_related('stage__phase__scope'))
    index = DeliveryDocumentIndex(project, project.client, document_ids=[], publications=publications)
    index.admin = False
    fields = {'project': project, 'level': level}
    if level != 'project':
        fields[level] = target
    return index.target_visible(DeliveryDocumentLink(**fields))


def _link_effect(project, arguments, *, unlink=False, lock=False):
    if unlink:
        link = DeliveryDocumentLink.objects.filter(project=project, pk=arguments['link_id']).first()
        if link is None:
            raise ToolError('Asociación no encontrada.', code='NOT_FOUND')
        doc = _document(project, link.document_id, lock=lock)
    else:
        doc = _document(project, arguments['document_id'], lock=lock)
        target = delivery._target(project, arguments['level'], arguments['target_id'])
        fields = {'project': project, 'document': doc, 'level': arguments['level']}
        if arguments['level'] != 'project':
            fields[arguments['level']] = target
        link = DeliveryDocumentLink(**fields)
    before = _client_portal(project, doc)
    after = _client_portal(project, doc)
    existing = list(before.index.by_document[doc.pk])
    if unlink:
        remaining = [entry for entry in existing if entry.pk != link.pk]
        after.index.links = [entry for entry in after.index.links if entry.pk != link.pk]
        after.index.by_document[doc.pk] = remaining
        public = before.index.visible(link) or before.visible(doc) != after.visible(doc)
    else:
        after.index.links.append(link)
        after.index.by_document[doc.pk].append(link)
        public = after.index.visible(link) or before.visible(doc) != after.visible(doc)
    state = {'level': link.level, 'target_id': project.pk if link.level == 'project' else getattr(link, f'{link.level}_id'),
             'document_id': doc.pk, 'link_id': link.pk,
             'before_visible': before.visible(doc), 'after_visible': after.visible(doc)}
    return public, state, [_document_state(doc, project)] if public else []


def _issue_effect(project, actor, name, arguments, *, lock=False):
    items = arguments['items'] if name == 'bulk_evaluate_issue_reports' else [{
        'id': arguments['ticket_id'], **arguments['payload']}]
    states, files, public = [], [], False
    for index, item in enumerate(items):
        try:
            ticket = issues.get_ticket(project.pk, actor, arguments['kind'], item['id'], lock=lock)
        except APIException as exc:
            states.append({'index': index, 'id': item['id'], 'error': str(exc.detail)})
            continue
        changed = any(key in item and str(item[key]) != str(getattr(ticket, key, None))
                      for key in ('status', 'estimated_cost', 'estimated_time', 'linked_bug_id'))
        if item.get('expected_version') != ticket.version:
            if name != 'bulk_evaluate_issue_reports':
                raise ToolError('El ticket cambió. Actualiza antes de responder.', code='STALE_VERSION')
            states.append({'index': index, 'id': ticket.pk, 'error': 'STALE_VERSION', 'version': ticket.version})
            continue
        if item.get('contract_reply') is not None:
            from accounts.services.issue_contract_reply import validate_reply
            validate_reply(project, actor, arguments['kind'], ticket, item)
        visible = not item.get('is_internal', False) or changed or bool(item.get('reopen'))
        public = public or visible
        states.append({'index': index, 'id': ticket.pk, 'version': ticket.version,
            'status': ticket.status, 'admin_response': ticket.admin_response,
            'is_archived': ticket.is_archived, 'public_effect': visible})
        if visible:
            for identifier in item.get('document_ids', []):
                files.append(_document_state(_document(project, identifier, lock=lock), project))
    return public, states, files


def _snapshot(tool_name, arguments, actor, *, lock=False):
    project = project_for_actor(arguments['project_id'], actor, lock=lock)
    if lock:
        list(get_user_model().objects.select_for_update().filter(pk=project.client_id))
        project.client.refresh_from_db()
    workspace_version = DeliveryWorkspace.objects.filter(project=project).values_list('version', flat=True).first() or 0
    if tool_name not in ISSUE_PUBLIC_TOOLS and arguments['expected_version'] != workspace_version:
        raise ToolError('El seguimiento cambió. Actualiza antes de continuar.', code='STALE_VERSION')
    files, states = [], []
    if tool_name == 'add_delivery_message':
        public = not arguments.get('is_internal', False)
        target = delivery._target(project, arguments['level'], arguments['target_id'])
        published = _client_level_visible(project, arguments['level'], target)
        states = {'level': arguments['level'], 'target_id': target.pk, 'published': published}
        if public and not published:
            raise ToolError('Publica este contenido antes de responder al cliente.', code='TARGET_UNPUBLISHED')
        if public:
            files = [_document_state(_document(project, identifier, lock=lock), project)
                     for identifier in arguments.get('document_ids', [])]
    elif tool_name in {'link_delivery_document', 'unlink_delivery_document'}:
        public, states, files = _link_effect(project, arguments,
            unlink=tool_name == 'unlink_delivery_document', lock=lock)
    elif tool_name in ISSUE_PUBLIC_TOOLS:
        public, states, files = _issue_effect(project, actor, tool_name, arguments, lock=lock)
    else:
        kind = 'amendments' if tool_name.endswith('_amendment') else 'contracts'
        node = delivery._node(project, kind, arguments['node_id']) if 'node_id' in arguments else None
        public = bool((node and node.client_visible) or arguments.get('data', {}).get('client_visible', False))
        states = {'kind': kind, 'node_id': getattr(node, 'pk', None),
                  'current_visible': bool(node and node.client_visible),
                  'title': getattr(node, 'title', None), 'key': getattr(node, 'key', None)}
        if public:
            files = _contract_files(project, kind, arguments, node, lock=lock)
    context = current_mcp_context()
    return {'operation': tool_name, 'project_id': project.pk, 'public_effect': public,
        'recipient': {'user_id': project.client_id, 'email': project.client.email,
                      'name': project.client.get_full_name() or project.client.email},
        'actor_id': actor.pk, 'credential_id': str(context.credential.pk) if context and context.credential else None,
        'workspace_version': workspace_version,
        'selection': deepcopy(arguments), 'state': states, 'files': files}


def configure_public_tool(tool, actor_resolver):
    """Keep dynamic sensitivity local to these native tools and their services."""
    native = tool['handler']
    name, schema = tool['name'], tool['input_schema']

    def validate(arguments):
        from content.mcp.issue_tools import _validate
        _validate(arguments, schema)

    def predicate(arguments):
        validate(arguments)
        return _snapshot(name, arguments, actor_resolver())['public_effect']

    def prepare(arguments):
        validate(arguments)
        snapshot = _snapshot(name, arguments, actor_resolver())
        return {**deepcopy(arguments), SEAL: canonical_arguments_hash(snapshot)}

    def impact(arguments):
        arguments = {key: value for key, value in arguments.items() if key != SEAL}
        snapshot = _snapshot(name, arguments, actor_resolver())
        return {'summary': tool['description'], **{key: snapshot[key] for key in (
            'operation', 'project_id', 'recipient', 'workspace_version', 'selection', 'state', 'files',
        )}, 'effect_sha256': canonical_arguments_hash(snapshot)}

    def etags(arguments):
        arguments = {key: value for key, value in arguments.items() if key != SEAL}
        return {'public_effect': canonical_arguments_hash(_snapshot(name, arguments, actor_resolver()))}

    def execute(arguments):
        arguments = deepcopy(arguments)
        expected = arguments.pop(SEAL, None)
        context = current_mcp_context()
        confirmed = bool(context and context.confirmation_bypass)
        if expected is not None and not confirmed:
            raise ToolError('La confirmación pertenece al servidor.', code='FORBIDDEN')
        validate(arguments)
        actor = actor_resolver()
        with transaction.atomic():
            snapshot = _snapshot(name, arguments, actor, lock=True)
            if snapshot['public_effect'] and (not confirmed or expected is None):
                raise ToolError('Confirma el contenido y destinatario públicos antes de continuar.', code='CONFIRMATION_REQUIRED')
            if expected is not None and canonical_arguments_hash(snapshot) != expected:
                raise ToolError('El contenido o destinatario cambió desde la revisión.', code='STALE_VERSION')
            return native(arguments)

    tool.update(risk='sensitive', requires_confirmation=True,
        confirmation_predicate=predicate, prepare_arguments=prepare,
        impact_builder=impact, etag_resolver=etags, handler=execute)
    tool['description'] += (' Los efectos visibles al cliente muestran contenido y destinatario '
        'para confirmación; los borradores y notas exclusivamente internos se ejecutan directamente.')
