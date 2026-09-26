"""
Tool registry for the Documents MCP connector.

Lets claude.ai browse the panel's document manager (/panel/documents):
list folders, list/read markdown documents, and create/edit/delete them.
Documents are authored in Markdown; the panel turns them into branded PDFs
downstream, so producing correct Markdown is enough here.

Guardrails baked in:
- Only MARKDOWN-type documents are visible or mutable. Commercial
  collection accounts (cuentas de cobro) live in the same table and are
  deliberately out of reach.
- Published documents cannot be deleted (unpublish first or use the panel).
- Folders can be listed, created and renamed, but not deleted, so the MCP
  cannot dismantle the existing structure. Archivar una carpeta arrastra su
  contenido en cascada, así que por la misma razón tampoco se expone: es una
  acción del panel. Lo archivado simplemente deja de verse desde aquí.

Each entry: {'name', 'description', 'input_schema', 'handler'}. Handlers
receive the raw `arguments` dict, return a JSON-serializable dict, and raise
ToolError for business errors. They reuse the exact same parser and
document_type helpers as the panel so the PDF pipeline stays identical.
"""
import hashlib
import json

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from accounts.models import Project, UserProfile
from accounts.services.proposal_client_service import build_client_display_name

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.models import (
    Document,
    DocumentFolder,
    DocumentNote,
    DocumentState,
    DocumentStateEpisode,
)
from content.serializers.document import apply_client_project_association
from content.serializers.document_folder import DocumentFolderSerializer
from content.services.contract_mirror_service import (
    CONTRACT_MIRROR_BLOCKER,
    CONTRACT_MIRROR_MESSAGE,
    is_contract_mirror,
    mirror_markdown,
)
from content.services.document_content import build_content_json
from content.services.document_notes import (
    DocumentNotesValidationError, normalize_client_custom_notes,
)
from content.services.document_type_codes import MARKDOWN
from content.services.document_type_utils import get_markdown_document_type
from content.services.document_note_service import (
    DocumentNoteError,
    create_note,
    delete_notes,
    finish_note,
    restore_note,
    sync_legacy_notes,
)
from content.services.document_state_service import (
    DocumentStateError,
    close_episode,
    open_state,
)

LANGUAGE_CHOICES = {c[0] for c in Document.Language.choices}
COVER_TYPE_CHOICES = {c[0] for c in Document.CoverType.choices}


# ── Querysets & lookups ──────────────────────────────────────────────────────

def _markdown_qs():
    """Only markdown documents — never commercial collection accounts.

    Lo archivado tampoco es visible por MCP: sale de circulación para todos los
    callers, no sólo para el panel. Esto cierra de una vez list/read/update/
    append/delete, que se apoyan en este queryset.
    """
    return (
        Document.objects
        .filter(document_type__code=MARKDOWN, is_archived=False)
        .select_related('folder', 'project', 'client_user__profile', 'contract_template')
        .prefetch_related('tags')
    )


def _refuse_contract_mirror(doc):
    """The window onto the one contract is read-only for every caller."""
    if is_contract_mirror(doc):
        raise ToolError(
            CONTRACT_MIRROR_MESSAGE,
            code='NOT_EDITABLE',
            details={'edit_blockers': [CONTRACT_MIRROR_BLOCKER]},
        )


def _get_markdown_doc_or_error(document_id):
    try:
        return _markdown_qs().get(pk=int(document_id))
    except (Document.DoesNotExist, TypeError, ValueError):
        try:
            document = Document.objects.select_related('document_type').get(
                pk=int(document_id),
            )
        except (Document.DoesNotExist, TypeError, ValueError):
            document = None
        if document is not None:
            if document.is_archived:
                raise ToolError(
                    'El documento está archivado y no admite edición.',
                    code='NOT_EDITABLE',
                    details={'edit_blockers': ['archived']},
                )
            raise ToolError(
                'El documento es un snapshot generado y no contiene Markdown '
                'editable. Corrige su fuente de negocio; una cuenta emitida '
                'se anula y se vuelve a emitir.',
                code='NOT_EDITABLE',
                details={'edit_blockers': ['generated_snapshot']},
            )
        raise ToolError(
            f'No existe un documento markdown con id={document_id}. '
            'Usa list_documents para ver los disponibles.',
            code='NOT_FOUND',
        )


def _resolve_folder(folder_id):
    """Turn a folder_id argument into a DocumentFolder (or None for root).

    Rechaza carpetas archivadas: el panel sólo ofrece carpetas activas como
    destino, y el MCP no tiene UI que lo impida.
    """
    if folder_id in (None, '', 'none', 'null'):
        return None
    try:
        folder = DocumentFolder.objects.get(pk=int(folder_id))
    except (DocumentFolder.DoesNotExist, TypeError, ValueError):
        raise ToolError(
            f'No existe una carpeta con id={folder_id}. '
            'Usa list_folders para ver las disponibles.'
        )
    if folder.is_archived:
        raise ToolError(
            f'La carpeta "{folder.name}" está archivada y no admite documentos. '
            'Usa list_folders para ver las disponibles.'
        )
    if folder.is_system_managed:
        raise ToolError(
            f'La carpeta "{folder.name}" pertenece al archivado automático '
            'y no admite cambios manuales.'
        )
    return folder


def _resolve_client(client_id):
    if client_id in (None, '', 'none', 'null'):
        return None
    try:
        client = UserProfile.objects.clients().get(pk=int(client_id))
    except (UserProfile.DoesNotExist, TypeError, ValueError) as exc:
        raise ToolError(
            f'No existe un cliente con id={client_id}. Usa el MCP de clientes '
            'para ver los disponibles.'
        ) from exc
    return client


def _resolve_project(project_id):
    if project_id in (None, '', 'none', 'null'):
        return None
    try:
        return Project.objects.get(pk=int(project_id))
    except (Project.DoesNotExist, TypeError, ValueError) as exc:
        raise ToolError(f'No existe un proyecto con id={project_id}.') from exc


def _association_data(arguments, *, instance=None):
    """Apply the exact client/project invariant used by panel serializers."""
    attrs = {}
    if 'client_id' in arguments:
        attrs['client'] = _resolve_client(arguments.get('client_id'))
    if 'project_id' in arguments:
        attrs['project'] = _resolve_project(arguments.get('project_id'))
    if 'client_name' in arguments:
        attrs['client_name'] = arguments.get('client_name', '') or ''
    try:
        return apply_client_project_association(attrs, instance)
    except serializers.ValidationError as exc:
        raise ToolError(
            'Datos inválidos: ' + json.dumps(
                exc.detail, ensure_ascii=False, default=str,
            )
        ) from exc


# ── Payload shaping ──────────────────────────────────────────────────────────

def _folder_path(folder):
    names = [a.name for a in folder.get_ancestors()] + [folder.name]
    return ' / '.join(names)


def _folder_payload(folder):
    project_state = (
        folder.managed_project.current_state
        if folder.managed_project_id else None
    )
    return {
        'id': folder.id,
        'name': folder.name,
        'path': _folder_path(folder),
        'parent_id': folder.parent_id,
        'order': folder.order,
        'folder_kind': folder.folder_kind,
        'is_system_managed': folder.is_system_managed,
        'project_id': folder.project_id,
        'client_id': (
            getattr(folder.client_user, 'profile', None).pk
            if folder.client_user_id
            and getattr(folder.client_user, 'profile', None) is not None
            else None
        ),
        'project_state': (
            {
                'id': project_state.pk,
                'name': project_state.name,
                'system_key': project_state.system_key,
                'show_in_document_manager': (
                    project_state.show_in_document_manager
                ),
            }
            if project_state else None
        ),
        # Count only markdown docs, to match what list_documents exposes.
        'document_count': folder.documents.filter(
            document_type__code=MARKDOWN, is_archived=False,
        ).count(),
    }


def _doc_summary(doc):
    client_profile = (
        getattr(doc.client_user, 'profile', None) if doc.client_user_id else None
    )
    active_states = list(
        doc.state_episodes.filter(closed_at__isnull=True)
        .select_related('state__group')
        .order_by('state__group__order', 'state__order')
    )
    return {
        'id': doc.id,
        'title': doc.title,
        'slug': doc.slug,
        'status': doc.status,
        'is_client_visible': doc.is_client_visible,
        'client_id': client_profile.id if client_profile else None,
        'client_name': doc.client_name,
        'client_display_name': (
            build_client_display_name(client_profile) if client_profile else None
        ),
        'project_id': doc.project_id,
        'project_name': doc.project.name if doc.project else None,
        'active_states': [
            {
                'episode_id': episode.id,
                'state_id': episode.state_id,
                'name': episode.state.name,
                'system_key': episode.state.system_key,
                'color': episode.state.color,
                'group': episode.state.group.name,
                'opened_at': (
                    episode.opened_at.isoformat() if episode.opened_at else None
                ),
            }
            for episode in active_states
        ],
        'language': doc.language,
        'folder_id': doc.folder_id,
        'folder_name': doc.folder.name if doc.folder else None,
        'tags': [
            {'id': tag.id, 'name': tag.name, 'color': tag.color}
            for tag in doc.tags.all()
        ],
        'has_client_note': any((
            doc.client_email_subject.strip(),
            doc.client_email_body.strip(),
            doc.client_whatsapp_message.strip(),
            doc.client_custom_notes,
        )),
        'updated_at': doc.updated_at.isoformat() if doc.updated_at else None,
        'created_at': doc.created_at.isoformat() if doc.created_at else None,
        'etag': _document_etag(doc),
        'editable': (
            not doc.is_archived
            and doc.document_type.code == MARKDOWN
            and not is_contract_mirror(doc)
        ),
        'edit_blockers': [CONTRACT_MIRROR_BLOCKER] if is_contract_mirror(doc) else [],
        'is_contract_mirror': is_contract_mirror(doc),
    }


def _doc_detail(doc):
    normalized_notes = list(
        doc.document_notes.filter(deleted_at__isnull=True)
        .select_related('episode')
        .order_by('order', 'id')
    )
    # The contract window stores a pointer; callers read the contract itself.
    markdown = (mirror_markdown() or '') if is_contract_mirror(doc) else doc.content_markdown
    return {
        **_doc_summary(doc),
        'markdown': markdown,
        'content_markdown': markdown,
        'client_email_subject': doc.client_email_subject,
        'client_email_body': doc.client_email_body,
        'client_whatsapp_message': doc.client_whatsapp_message,
        # Preserve the established MCP payload for existing callers. Rich
        # workflow metadata lives under `notes`, matching the document API.
        'client_custom_notes': doc.client_custom_notes,
        'notes': [
            {
                'id': note.id,
                'title': note.title,
                'content': note.content,
                'status': note.status,
                'episode_id': note.episode_id,
                'resolution_note': note.resolution_note,
            }
            for note in normalized_notes
        ],
        # Las tres deciden qué páginas trae el PDF: sin exponerlas, quien crea
        # por MCP no tiene cómo saber con qué configuración quedó el documento.
        'include_portada': doc.include_portada,
        'include_subportada': doc.include_subportada,
        'include_contraportada': doc.include_contraportada,
    }


def _document_etag(doc):
    source = f'document:{doc.pk}:{doc.updated_at.isoformat() if doc.updated_at else ""}'
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def _check_document_etag(doc, arguments):
    expected = arguments.get('if_match')
    if expected and expected != _document_etag(doc):
        raise ToolError(
            'El documento cambió desde la última lectura.',
            code='STALE_VERSION',
            details={
                'expected': expected,
                'current': _document_etag(doc),
            },
        )


COVER_FLAGS = ('include_portada', 'include_subportada', 'include_contraportada')
CLIENT_NOTE_FIELDS = (
    'client_email_subject', 'client_email_body', 'client_whatsapp_message',
)

_COVER_FLAG_PROPS = {
    'include_portada': {
        'type': 'boolean',
        'description': 'Incluir la portada de marca (por defecto true).',
    },
    'include_subportada': {
        'type': 'boolean',
        'description': 'Incluir la subportada con título, cliente y fecha (por defecto true).',
    },
    'include_contraportada': {
        'type': 'boolean',
        'description': 'Incluir la contraportada de marca (por defecto true).',
    },
}

_CLIENT_NOTE_PROPS = {
    'client_email_subject': {
        'type': 'string',
        'maxLength': 255,
        'description': 'Asunto del correo preparado para el cliente (opcional).',
    },
    'client_email_body': {
        'type': 'string',
        'description': 'Cuerpo del correo preparado para el cliente (opcional).',
    },
    'client_whatsapp_message': {
        'type': 'string',
        'description': 'Mensaje de WhatsApp preparado para el cliente (opcional).',
    },
    'client_custom_notes': {
        'type': 'array',
        'description': 'Notas privadas adicionales, en su orden de creación.',
        'items': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string', 'maxLength': 255},
                'content': {'type': 'string'},
            },
            'required': ['title', 'content'],
            'additionalProperties': False,
        },
    },
}


def _cover_flag(arguments, name):
    """Lee una casilla de portada de los argumentos MCP.

    Sólo booleanos: un `'false'` de texto colado como True dejaría al caller
    creyendo que configuró el PDF cuando no lo hizo.
    """
    value = arguments.get(name)
    if not isinstance(value, bool):
        raise ToolError(f'{name} debe ser true o false.')
    return value


def _client_note_value(arguments, name):
    """Validate one private client-note field from an MCP payload."""
    value = arguments.get(name)
    if not isinstance(value, str):
        raise ToolError(f'{name} debe ser texto.')
    value = value.strip()
    if name == 'client_email_subject' and len(value) > 255:
        raise ToolError('client_email_subject no puede superar 255 caracteres.')
    return value


def _client_custom_notes_value(arguments):
    """Validate and normalize the ordered custom-note collection."""
    try:
        return normalize_client_custom_notes(arguments.get('client_custom_notes'))
    except DocumentNotesValidationError as exc:
        raise ToolError(f'client_custom_notes: {exc}') from exc


# ── Handlers ─────────────────────────────────────────────────────────────────

def list_folders(arguments):
    folders = DocumentFolder.objects.filter(is_archived=False).select_related(
        'parent', 'project', 'client_user__profile',
        'managed_project__current_state',
    )
    return {'folders': [_folder_payload(f) for f in folders]}


def create_folder(arguments):
    name = (arguments.get('name') or '').strip()
    if not name:
        raise ToolError('El nombre de la carpeta es obligatorio.')
    parent = _resolve_folder(arguments.get('parent_id'))
    serializer = DocumentFolderSerializer(data={
        'name': name,
        'parent': parent.pk if parent else None,
    })
    if not serializer.is_valid():
        raise ToolError(
            'Datos inválidos: ' + json.dumps(
                serializer.errors, ensure_ascii=False, default=str,
            )
        )
    folder = serializer.save()
    return _folder_payload(folder)


def rename_folder(arguments):
    folder_id = arguments.get('folder_id')
    if folder_id in (None, '', 'none', 'null'):
        raise ToolError('folder_id es obligatorio para renombrar una carpeta.')
    folder = _resolve_folder(folder_id)
    if folder.managed_project_id:
        raise ToolError(
            'La raíz de un proyecto se renombra desde el módulo Proyectos.'
        )
    name = (arguments.get('name') or '').strip()
    if not name:
        raise ToolError('El nuevo nombre de la carpeta es obligatorio.')
    # The slug is set once on creation and left untouched, so links and PDF
    # references stay stable when only the display name changes.
    folder.name = name
    folder.save(update_fields=['name', 'updated_at'])
    return _folder_payload(folder)


def list_documents(arguments):
    try:
        page = max(1, int(arguments.get('page', 1) or 1))
        page_size = max(1, min(int(arguments.get('page_size', 20) or 20), 50))
    except (TypeError, ValueError):
        raise ToolError('page y page_size deben ser enteros.')

    qs = _markdown_qs()
    folder_arg = arguments.get('folder_id')
    if folder_arg == 'none':
        qs = qs.filter(folder__isnull=True)
    elif folder_arg not in (None, '', 'all'):
        folder = _resolve_folder(folder_arg)
        qs = qs.filter(folder=folder)

    for argument_name, lookup in (
        ('client_id', 'client_user__profile__id'),
        ('project_id', 'project_id'),
    ):
        value = arguments.get(argument_name)
        if value == 'none':
            qs = qs.filter(**{f'{lookup}__isnull': True})
        elif value not in (None, '', 'all'):
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise ToolError(
                    f'{argument_name} debe ser un ID, "none" o "all".'
                ) from exc
            qs = qs.filter(**{lookup: value})

    total = qs.count()
    start = (page - 1) * page_size
    page_docs = list(qs[start:start + page_size])
    return {
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': [_doc_summary(d) for d in page_docs],
    }


def read_document(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    return _doc_detail(doc)


def create_document(arguments):
    title = (arguments.get('title') or '').strip()
    markdown_text = arguments.get('markdown')
    if not title:
        raise ToolError('title es obligatorio.')
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        raise ToolError('markdown es obligatorio y debe ser texto.')

    language = arguments.get('language', 'es')
    if language not in LANGUAGE_CHOICES:
        raise ToolError(f'language inválido: usa uno de {sorted(LANGUAGE_CHOICES)}.')

    folder = _resolve_folder(arguments.get('folder_id'))
    association_data = _association_data(arguments)
    covers = {
        name: _cover_flag(arguments, name)
        for name in COVER_FLAGS if name in arguments
    }
    client_note = {
        name: _client_note_value(arguments, name)
        for name in CLIENT_NOTE_FIELDS if name in arguments
    }
    if 'client_custom_notes' in arguments:
        client_note['client_custom_notes'] = _client_custom_notes_value(arguments)

    actor = mcp_actor()
    doc = Document(
        title=title,
        document_type=get_markdown_document_type(),
        folder=folder,
        language=language,
        content_markdown=markdown_text,
        **covers,
        **client_note,
        created_by=actor,
        updated_by=actor,
        **association_data,
    )
    doc.content_json = build_content_json(doc, markdown_text)
    doc.save()
    return _doc_detail(doc)


def update_document(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    _refuse_contract_mirror(doc)
    _check_document_etag(doc, arguments)

    if 'markdown' in arguments and 'content_markdown' in arguments:
        if arguments['markdown'] != arguments['content_markdown']:
            raise ToolError(
                'markdown y content_markdown no pueden contener valores distintos.'
            )
    if 'content_markdown' in arguments and 'markdown' not in arguments:
        arguments = {**arguments, 'markdown': arguments['content_markdown']}

    update_fields = set()
    if 'title' in arguments:
        title = (arguments.get('title') or '').strip()
        if not title:
            raise ToolError('title no puede quedar vacío.')
        doc.title = title
        update_fields.add('title')

    if 'language' in arguments:
        language = arguments.get('language')
        if language not in LANGUAGE_CHOICES:
            raise ToolError(f'language inválido: usa uno de {sorted(LANGUAGE_CHOICES)}.')
        doc.language = language
        update_fields.add('language')

    if 'is_client_visible' in arguments:
        if not isinstance(arguments.get('is_client_visible'), bool):
            raise ToolError('is_client_visible debe ser true o false.')
        doc.is_client_visible = arguments['is_client_visible']
        update_fields.add('is_client_visible')

    if 'folder_id' in arguments:
        doc.folder = _resolve_folder(arguments.get('folder_id'))
        update_fields.add('folder')

    if any(
        field in arguments for field in ('client_id', 'project_id', 'client_name')
    ):
        association_data = _association_data(arguments, instance=doc)
        for field, value in association_data.items():
            setattr(doc, field, value)
            update_fields.add(field)

    for flag in COVER_FLAGS:
        if flag in arguments:
            setattr(doc, flag, _cover_flag(arguments, flag))
            update_fields.add(flag)

    for field in CLIENT_NOTE_FIELDS:
        if field in arguments:
            setattr(doc, field, _client_note_value(arguments, field))
            update_fields.add(field)

    if 'client_custom_notes' in arguments:
        doc.client_custom_notes = _client_custom_notes_value(arguments)
        update_fields.add('client_custom_notes')

    markdown_changed = 'markdown' in arguments
    if markdown_changed:
        markdown_text = arguments.get('markdown')
        if not isinstance(markdown_text, str) or not markdown_text.strip():
            raise ToolError('markdown debe ser texto no vacío.')
        doc.content_markdown = markdown_text
        update_fields.add('content_markdown')

    if not update_fields:
        raise ToolError(
            'No se indicó ningún campo para actualizar. Envía al menos uno de: '
            'title, markdown, folder_id, is_client_visible, client_id, project_id, '
            'client_name, language, '
            'include_portada, include_subportada, include_contraportada, '
            'client_email_subject, client_email_body, client_whatsapp_message, '
            'client_custom_notes.'
        )

    # content_json must always reflect the current title/meta + markdown, so
    # rebuild it whenever the markdown or any meta field changed.
    doc.content_json = build_content_json(doc, doc.content_markdown)
    update_fields.add('content_json')
    doc.updated_by = mcp_actor()
    update_fields.add('updated_by')
    doc.save(update_fields=list(update_fields) + ['updated_at'])
    if 'client_custom_notes' in arguments:
        sync_legacy_notes(doc, actor=doc.updated_by)
    return _doc_detail(doc)


def append_document(arguments):
    """Append a markdown chunk to an existing document.

    A single MCP call cannot carry very large documents, so big uploads are
    done as create_document + N append_document calls. The chunk is joined
    with a separator (default blank line) and content_json is rebuilt from
    the full markdown.
    """
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    _refuse_contract_mirror(doc)
    _check_document_etag(doc, arguments)

    markdown_text = arguments.get('markdown')
    if not isinstance(markdown_text, str) or not markdown_text.strip():
        raise ToolError('markdown es obligatorio y debe ser texto no vacío.')

    separator = arguments.get('separator')
    if separator is None:
        separator = '\n\n'
    if not isinstance(separator, str):
        raise ToolError('separator debe ser texto (por ejemplo "\\n\\n" o "\\n").')

    doc.content_markdown = (
        (doc.content_markdown or '').rstrip('\n') + separator + markdown_text
    )
    doc.content_json = build_content_json(doc, doc.content_markdown)
    doc.save(update_fields=['content_markdown', 'content_json', 'updated_at'])
    return _doc_detail(doc)


def delete_document(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    _refuse_contract_mirror(doc)
    if doc.is_client_visible:
        raise ToolError(
            'Este documento está visible en el portal. Desactiva '
            'is_client_visible antes de eliminarlo, o bórralo desde el panel.'
        )
    doc_id = doc.id
    doc.delete()
    return {'deleted': True, 'id': doc_id}


def list_document_states(arguments):
    states = DocumentState.objects.filter(
        is_active=True, merged_into__isnull=True,
    ).select_related('group').order_by('group__order', 'order', 'name')
    return {'states': [
        {
            'id': item.id,
            'name': item.name,
            'system_key': item.system_key,
            'color': item.color,
            'group': item.group.name,
            'selection_mode': item.group.selection_mode,
        }
        for item in states
    ]}


def set_document_state(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    state_id = arguments.get('state_id')
    try:
        state = DocumentState.objects.get(
            pk=int(state_id), is_active=True, merged_into__isnull=True,
        )
    except (DocumentState.DoesNotExist, TypeError, ValueError):
        raise ToolError(
            f'No existe un estado activo con id={state_id}. '
            'Usa list_document_states para ver los disponibles.'
        )
    opened_at = None
    if arguments.get('opened_at'):
        if not isinstance(arguments['opened_at'], str):
            raise ToolError('opened_at debe ser una fecha y hora ISO 8601.')
        opened_at = parse_datetime(arguments['opened_at'])
        if opened_at is None:
            raise ToolError('opened_at debe ser una fecha y hora ISO 8601.')
        if timezone.is_naive(opened_at):
            opened_at = timezone.make_aware(opened_at)
    try:
        episode, _ = open_state(
            doc,
            state,
            actor=mcp_actor(),
            opened_at=opened_at,
            origin=DocumentStateEpisode.Origin.MCP,
        )
    except DocumentStateError as exc:
        raise ToolError(str(exc)) from exc
    return _doc_summary(doc) | {'opened_episode_id': episode.id}


def close_document_state(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    try:
        episode = doc.state_episodes.get(
            pk=int(arguments.get('episode_id')), closed_at__isnull=True,
        )
    except (DocumentStateEpisode.DoesNotExist, TypeError, ValueError):
        raise ToolError('No existe ese episodio abierto para el documento.')
    outcome = arguments.get('outcome', DocumentStateEpisode.Outcome.COMPLETED)
    if outcome not in {
        DocumentStateEpisode.Outcome.COMPLETED,
        DocumentStateEpisode.Outcome.REMOVED,
    }:
        raise ToolError('outcome debe ser completed o removed.')
    note = arguments.get('note', '')
    if not isinstance(note, str) or len(note.strip()) > 500:
        raise ToolError('note debe ser texto de máximo 500 caracteres.')
    try:
        episode = close_episode(
            episode,
            actor=mcp_actor(),
            outcome=outcome,
            close_note=note,
        )
    except DocumentStateError as exc:
        raise ToolError(str(exc)) from exc
    return {
        'episode_id': episode.id,
        'state': episode.state.name,
        'outcome': episode.outcome,
        'closed_at': episode.closed_at.isoformat(),
    }


def _note_payload(note):
    deleted_by_name = None
    if note.deleted_by_id:
        deleted_by_name = (
            note.deleted_by.get_full_name().strip()
            or note.deleted_by.get_username()
        )
    return {
        'id': note.id,
        'document_id': note.document_id,
        'episode_id': note.episode_id,
        'title': note.title,
        'content': note.content,
        'status': note.status,
        'resolution_note': note.resolution_note,
        'resolved_at': (
            note.resolved_at.isoformat() if note.resolved_at else None
        ),
        'deleted_at': (
            note.deleted_at.isoformat() if note.deleted_at else None
        ),
        'deleted_by_name': deleted_by_name,
    }


def add_document_note(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    content = arguments.get('content')
    if not isinstance(content, str) or not content.strip():
        raise ToolError('content es obligatorio y debe ser texto no vacío.')
    title = arguments.get('title', '')
    if not isinstance(title, str) or len(title.strip()) > 120:
        raise ToolError('title debe ser texto de máximo 120 caracteres.')
    mark_needs_fix = arguments.get('mark_needs_fix', False)
    if not isinstance(mark_needs_fix, bool):
        raise ToolError('mark_needs_fix debe ser true o false.')
    try:
        note = create_note(
            doc,
            title=title,
            content=content,
            actor=mcp_actor(),
            mark_needs_fix=mark_needs_fix,
        )
    except (DocumentNoteError, DocumentStateError) as exc:
        raise ToolError(str(exc)) from exc
    return _note_payload(note)


def finish_document_note(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    try:
        note = doc.document_notes.get(
            pk=int(arguments.get('note_id')),
            deleted_at__isnull=True,
        )
    except (DocumentNote.DoesNotExist, TypeError, ValueError):
        raise ToolError('No existe esa observación para el documento.')
    outcome = arguments.get('outcome', DocumentNote.Status.RESOLVED)
    if outcome not in {DocumentNote.Status.RESOLVED, DocumentNote.Status.DISCARDED}:
        raise ToolError('outcome debe ser resolved o discarded.')
    close_linked_state = arguments.get('close_linked_state', False)
    move_cycle = arguments.get('move_cycle_to_bug_attended', False)
    if not isinstance(close_linked_state, bool) or not isinstance(move_cycle, bool):
        raise ToolError(
            'close_linked_state y move_cycle_to_bug_attended deben ser booleanos.'
        )
    resolution_note = arguments.get('resolution_note', '')
    if not isinstance(resolution_note, str) or len(resolution_note.strip()) > 500:
        raise ToolError(
            'resolution_note debe ser texto de máximo 500 caracteres.'
        )
    try:
        note, transitions = finish_note(
            note,
            actor=mcp_actor(),
            outcome=outcome,
            resolution_note=resolution_note,
            close_linked_state=close_linked_state,
            move_cycle_to_bug_attended=move_cycle,
        )
    except (DocumentNoteError, DocumentStateError) as exc:
        raise ToolError(str(exc)) from exc
    return {'note': _note_payload(note), **transitions}


def delete_document_notes(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    note_ids = arguments.get('note_ids')
    if (
        not isinstance(note_ids, list)
        or not note_ids
        or len(note_ids) > 100
        or any(isinstance(note_id, bool) or not isinstance(note_id, int)
               for note_id in note_ids)
    ):
        raise ToolError('note_ids debe ser una lista de 1 a 100 enteros.')
    try:
        return delete_notes(doc, note_ids=note_ids, actor=mcp_actor())
    except (DocumentNoteError, DocumentStateError) as exc:
        raise ToolError(str(exc)) from exc


def list_deleted_document_notes(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    notes = (
        doc.document_notes.filter(deleted_at__isnull=False)
        .select_related('deleted_by')
        .order_by('-deleted_at', '-id')
    )
    return {'notes': [_note_payload(note) for note in notes]}


def restore_document_note(arguments):
    doc = _get_markdown_doc_or_error(arguments.get('document_id'))
    note_id = arguments.get('note_id')
    if isinstance(note_id, bool):
        raise ToolError('note_id debe ser un entero.')
    try:
        note = doc.document_notes.select_related('deleted_by').get(pk=int(note_id))
    except (DocumentNote.DoesNotExist, TypeError, ValueError):
        raise ToolError('No existe esa observación para el documento.')
    try:
        note, transitions = restore_note(note, actor=mcp_actor())
    except (DocumentNoteError, DocumentStateError) as exc:
        raise ToolError(str(exc)) from exc
    return {'note': _note_payload(note), **transitions}


# ── Registry ─────────────────────────────────────────────────────────────────

_DOCUMENT_ID_PROP = {
    'document_id': {'type': 'integer', 'description': 'ID del documento markdown.'},
}

_CLIENT_PROJECT_PROPS = {
    'client_id': {
        'type': ['integer', 'null'],
        'description': (
            'ID del perfil de cliente; null desvincula. Usa el MCP de clientes '
            'para localizarlo.'
        ),
    },
    'project_id': {
        'type': ['integer', 'null'],
        'description': (
            'ID del proyecto; debe pertenecer al cliente seleccionado. Si se '
            'envía sin client_id, el cliente se deriva del proyecto.'
        ),
    },
}

DOCUMENT_TOOLS = [
    {
        'name': 'list_folders',
        'description': (
            'Lista todas las carpetas activas con su ruta, naturaleza '
            '(project/client/manual), proyecto, estado y conteo directo.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': list_folders,
    },
    {
        'name': 'create_folder',
        'description': (
            'Crea una carpeta nueva para organizar documentos. Opcionalmente '
            'anídala bajo otra con parent_id; dentro de un proyecto hereda '
            'automáticamente su proyecto y cliente.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string', 'description': 'Nombre de la carpeta.'},
                'parent_id': {
                    'type': 'integer',
                    'description': 'ID de la carpeta padre (omitir para raíz).',
                },
            },
            'required': ['name'],
        },
        'handler': create_folder,
    },
    {
        'name': 'rename_folder',
        'description': (
            'Cambia el nombre de una carpeta existente. Envía folder_id (de '
            'list_folders) y el nuevo name. Las raíces automáticas de proyecto '
            'sólo se renombran desde Proyectos.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'folder_id': {'type': 'integer', 'description': 'ID de la carpeta a renombrar.'},
                'name': {'type': 'string', 'description': 'Nuevo nombre.'},
            },
            'required': ['folder_id', 'name'],
        },
        'handler': rename_folder,
    },
    {
        'name': 'list_documents',
        'description': (
            'Lista documentos markdown con paginación. Filtra por carpeta con '
            'folder_id (un id, "none" para los que están en la raíz, o "all"). '
            'También filtra por client_id o project_id con la misma gramática. '
            'Devuelve resúmenes sin el contenido; usa read_document para el markdown.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'folder_id': {
                    'type': ['integer', 'string'],
                    'description': 'ID de carpeta, "none" (raíz) o "all" (todas).',
                },
                'client_id': {
                    'type': ['integer', 'string'],
                    'description': 'ID de cliente, "none" (sin cliente) o "all".',
                },
                'project_id': {
                    'type': ['integer', 'string'],
                    'description': 'ID de proyecto, "none" (sin proyecto) o "all".',
                },
                'page': {'type': 'integer', 'default': 1},
                'page_size': {'type': 'integer', 'default': 20, 'maximum': 50},
            },
        },
        'handler': list_documents,
    },
    {
        'name': 'read_document',
        'description': (
            'Devuelve un documento markdown completo, incluida su asociación a '
            'cliente/proyecto, content_markdown, estados y notas privadas. El '
            'contrato vigente (is_contract_mirror) devuelve el borrador '
            'completo en vivo y es de solo lectura.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _DOCUMENT_ID_PROP,
            'required': ['document_id'],
        },
        'handler': read_document,
    },
    {
        'name': 'create_document',
        'description': (
            'Crea un documento nuevo a partir de markdown. El sistema lo '
            'convierte en PDF con marca luego; basta con enviar buen markdown. '
            'Opcional: folder_id, client_id, project_id, language (es/en), client_name, '
            'y las casillas include_portada / include_subportada / '
            'include_contraportada, que deciden qué páginas trae el PDF. También '
            'puede guardar asunto, correo, WhatsApp y notas personalizadas privadas.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'title': {'type': 'string'},
                'markdown': {'type': 'string', 'description': 'Contenido en Markdown.'},
                'folder_id': {'type': 'integer', 'description': 'Carpeta destino (opcional).'},
                'language': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'},
                'client_name': {'type': 'string'},
                **_CLIENT_PROJECT_PROPS,
                **_COVER_FLAG_PROPS,
                **_CLIENT_NOTE_PROPS,
            },
            'required': ['title', 'markdown'],
        },
        'handler': create_document,
    },
    {
        'name': 'update_document',
        'description': (
            'Actualiza un documento markdown existente (parcial). Envía '
            'document_id y al menos uno de: title, markdown, folder_id, '
            'is_client_visible, client_id, project_id, client_name, language, '
            'include_portada, include_subportada, include_contraportada, '
            'client_email_subject, client_email_body, client_whatsapp_message, '
            'client_custom_notes. Al '
            'cambiar el markdown se reprocesa el contenido para el PDF. El '
            'contrato vigente (is_contract_mirror) no se edita: responde '
            'NOT_EDITABLE con edit_blockers ["contract_mirror"].'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'title': {'type': 'string'},
                'markdown': {'type': 'string'},
                'content_markdown': {
                    'type': 'string',
                    'description': 'Alias compatible obsoleto de markdown.',
                },
                'if_match': {
                    'type': 'string',
                    'description': 'ETag devuelto por read_document.',
                },
                'folder_id': {
                    'type': ['integer', 'null'],
                    'description': 'Carpeta destino (null para mover a la raíz).',
                },
                'is_client_visible': {
                    'type': 'boolean',
                    'description': 'Mostrar este documento en el portal del cliente.',
                },
                'client_name': {'type': 'string'},
                **_CLIENT_PROJECT_PROPS,
                'language': {'type': 'string', 'enum': ['es', 'en']},
                **_COVER_FLAG_PROPS,
                **_CLIENT_NOTE_PROPS,
            },
            'required': ['document_id'],
        },
        'handler': update_document,
    },
    {
        'name': 'append_document',
        'description': (
            'Añade un fragmento de markdown AL FINAL de un documento '
            'existente, sin reenviar el contenido previo. Úsala para subir '
            'documentos largos por partes: create_document con el primer '
            'tramo y append_document con los siguientes. El contenido se '
            'reprocesa completo para el PDF en cada llamada. No aplica al '
            'contrato vigente (is_contract_mirror), que es de solo lectura.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'markdown': {
                    'type': 'string',
                    'description': 'Fragmento de Markdown a añadir al final.',
                },
                'separator': {
                    'type': 'string',
                    'description': (
                        'Texto entre el contenido existente y el fragmento '
                        '(default: línea en blanco "\\n\\n").'
                    ),
                },
                'if_match': {
                    'type': 'string',
                    'description': 'ETag devuelto por read_document.',
                },
            },
            'required': ['document_id', 'markdown'],
        },
        'handler': append_document,
    },
    {
        'name': 'delete_document',
        'description': (
            'Elimina un documento markdown que no esté visible en el portal. '
            'Los visibles deben ocultarse primero o eliminarse desde el panel. '
            'El contrato vigente (is_contract_mirror) no se elimina.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': _DOCUMENT_ID_PROP,
            'required': ['document_id'],
        },
        'handler': delete_document,
    },
    {
        'name': 'list_document_states',
        'description': 'Lista el catálogo activo de estados administrables.',
        'input_schema': {'type': 'object', 'properties': {}},
        'handler': list_document_states,
    },
    {
        'name': 'set_document_state',
        'description': (
            'Abre un episodio de estado en un documento. Los estados de ciclo '
            'transicionan automáticamente; las señales pueden coexistir.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'state_id': {'type': 'integer'},
                'opened_at': {
                    'type': 'string',
                    'description': 'Fecha/hora real ISO 8601 (opcional).',
                },
            },
            'required': ['document_id', 'state_id'],
        },
        'handler': set_document_state,
    },
    {
        'name': 'close_document_state',
        'description': (
            'Cierra o quita un episodio abierto. completed significa trabajo '
            'realizado; removed significa que la marca sobraba.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'episode_id': {'type': 'integer'},
                'outcome': {
                    'type': 'string',
                    'enum': ['completed', 'removed'],
                    'default': 'completed',
                },
                'note': {'type': 'string', 'maxLength': 500},
            },
            'required': ['document_id', 'episode_id'],
        },
        'handler': close_document_state,
    },
    {
        'name': 'add_document_note',
        'description': (
            'Registra una observación privada y, opcionalmente, abre o enlaza '
            'la señal Solucionar bug.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'title': {'type': 'string', 'maxLength': 120},
                'content': {'type': 'string'},
                'mark_needs_fix': {'type': 'boolean', 'default': False},
            },
            'required': ['document_id', 'content'],
        },
        'handler': add_document_note,
    },
    {
        'name': 'finish_document_note',
        'description': (
            'Resuelve o descarta una observación y reconcilia automáticamente '
            'su señal enlazada; al resolver puede abrir Bug atendido.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'note_id': {'type': 'integer'},
                'outcome': {
                    'type': 'string',
                    'enum': ['resolved', 'discarded'],
                    'default': 'resolved',
                },
                'resolution_note': {'type': 'string', 'maxLength': 500},
                'close_linked_state': {'type': 'boolean', 'default': False},
                'move_cycle_to_bug_attended': {
                    'type': 'boolean',
                    'default': False,
                },
            },
            'required': ['document_id', 'note_id'],
        },
        'handler': finish_document_note,
    },
    {
        'name': 'delete_document_notes',
        'description': (
            'Envía una o varias observaciones del mismo documento a la papelera '
            'en una operación atómica y conserva sólo la auditoría del acto.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'note_ids': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'minItems': 1,
                    'maxItems': 100,
                    'uniqueItems': True,
                },
            },
            'required': ['document_id', 'note_ids'],
        },
        'handler': delete_document_notes,
    },
    {
        'name': 'list_deleted_document_notes',
        'description': (
            'Lista la papelera recuperable de observaciones de un documento, '
            'incluyendo quién y cuándo ejecutó cada eliminación.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_DOCUMENT_ID_PROP},
            'required': ['document_id'],
        },
        'handler': list_deleted_document_notes,
    },
    {
        'name': 'restore_document_note',
        'description': (
            'Restaura una observación desde la papelera y recompone la señal '
            'pendiente originada por observaciones cuando corresponde.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_DOCUMENT_ID_PROP,
                'note_id': {'type': 'integer'},
            },
            'required': ['document_id', 'note_id'],
        },
        'handler': restore_document_note,
    },
]
