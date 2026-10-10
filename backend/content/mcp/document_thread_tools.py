"""Thread tools for the Documents MCP connector.

Documents can be linked into a linear history — a thread — that is independent
of folders, clients and projects. v1 kept that relation panel-only; these tools
open it so the connector can read a story and build one.

Two guardrails shape the surface:

- **Membership edits are incremental.** The panel PATCH replaces the whole
  member list and dissolves the thread when one member is left. A caller that
  rebuilds that list from memory could destroy a history by forgetting an entry,
  so `update_document_thread` exposes `link` / `unlink_document_ids` instead, and
  dissolving is its own explicit tool.
- **Linking is restricted to active markdown documents**, the same rule the rest
  of this connector follows. Reading and unlinking accept any member, because a
  thread built from the panel may legitimately contain an archived document or a
  collection account.

`position` is never part of the contract: it is derived from the chronology, so
callers send dates and the server keeps the order stable.
"""
from django.db import transaction
from django.utils.dateparse import parse_date

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.models import Document, DocumentThread
from content.serializers.document_thread import (
    DocumentThreadListSerializer,
    DocumentThreadSerializer,
)
from content.services.document_thread_query import (
    THREAD_LIST_ORDERS,
    thread_detail_queryset,
    thread_for_document,
    thread_list_queryset,
)
from content.services.document_thread_service import (
    DocumentThreadError,
)
from content.services.document_thread_service import (
    create_document_thread as service_create_thread,
)
from content.services.document_thread_service import (
    dissolve_document_thread as service_dissolve_thread,
)
from content.services.document_thread_service import (
    edit_document_thread_members as service_edit_members,
)
from content.services.document_thread_service import (
    update_document_thread as service_update_thread,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _thread_error(exc):
    """Carry a service rule violation to the model with its hint attached."""
    message = str(exc)
    if exc.hint:
        message = f'{message} {exc.hint}'
    return ToolError(message)


def _thread_or_error(thread_id):
    try:
        return DocumentThread.objects.get(pk=int(thread_id))
    except (DocumentThread.DoesNotExist, TypeError, ValueError):
        raise ToolError(
            f'No existe un hilo con id={thread_id}. '
            'Usa list_document_threads para ver los disponibles.'
        )


def _linkable_document_or_error(document_id):
    """Only active markdown documents can be linked from here."""
    # Imported inside the function: `document_tools` owns the shared markdown
    # guardrail, and importing it at module level would tie the two registries
    # together in whichever order they happen to load.
    from content.mcp.document_tools import _markdown_qs

    try:
        return _markdown_qs().get(pk=int(document_id))
    except (Document.DoesNotExist, TypeError, ValueError):
        raise ToolError(
            f'No existe un documento markdown activo con id={document_id}. '
            'El conector sólo enlaza documentos markdown sin archivar; usa '
            'list_documents para ver los disponibles.'
        )


def _optional_date(value, *, field):
    if value in (None, ''):
        return None
    parsed = parse_date(str(value))
    if parsed is None:
        raise ToolError(
            f'{field}: "{value}" no es una fecha válida. Usa el formato YYYY-MM-DD.'
        )
    return parsed


def _optional_int(arguments, name):
    value = arguments.get(name)
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f'{name} debe ser un entero.')


def _page_args(arguments):
    try:
        page = max(1, int(arguments.get('page', 1) or 1))
        page_size = max(1, min(int(arguments.get('page_size', 20) or 20), 50))
    except (TypeError, ValueError):
        raise ToolError('page y page_size deben ser enteros.')
    return page, page_size


def _thread_items_or_error(raw, *, field, minimum):
    if not isinstance(raw, list) or len(raw) < minimum:
        raise ToolError(
            f'{field} debe ser una lista de al menos {minimum} documento(s), '
            'cada uno con document_id.'
        )
    items = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise ToolError(
                f'Cada elemento de {field} debe ser un objeto con document_id '
                'y, opcionalmente, occurred_on.'
            )
        document = _linkable_document_or_error(entry.get('document_id'))
        items.append({
            'document_id': document.pk,
            'occurred_on': _optional_date(
                entry.get('occurred_on'), field=f'{field}.occurred_on',
            ),
        })
    return items


def _document_ids_or_error(raw, *, field):
    if raw in (None, ''):
        return []
    if not isinstance(raw, list):
        raise ToolError(f'{field} debe ser una lista de identificadores.')
    ids = []
    for value in raw:
        try:
            document_id = int(value)
        except (TypeError, ValueError):
            raise ToolError(f'{field} sólo acepta identificadores enteros.')
        if document_id not in ids:
            ids.append(document_id)
    return ids


def _thread_payload(thread):
    hydrated = thread_detail_queryset().filter(pk=thread.pk).first()
    if hydrated is None:
        raise ToolError('El hilo dejó de existir mientras se consultaba.')
    return DocumentThreadSerializer(hydrated).data


# La forma de la fila vive en el serializer del panel: `thread_list_queryset`
# existe para que ambas superficies lean igual, y tener dos armadores de payload
# era justamente la deriva que esa capa compartida busca evitar.
def _thread_summary(thread):
    return DocumentThreadListSerializer(thread).data


# ── Handlers ─────────────────────────────────────────────────────────────────

def get_document_thread(arguments):
    document_id = arguments.get('document_id')
    thread_id = arguments.get('thread_id')
    has_document = document_id not in (None, '')
    has_thread = thread_id not in (None, '')

    if has_document and has_thread:
        raise ToolError('Envía document_id o thread_id, no ambos.')
    if has_thread:
        return {'thread': _thread_payload(_thread_or_error(thread_id))}
    if not has_document:
        raise ToolError(
            'Envía document_id para ver el hilo de un documento, o thread_id '
            'para abrir uno que ya conoces.'
        )

    try:
        pk = int(document_id)
    except (TypeError, ValueError):
        raise ToolError('document_id debe ser un entero.')
    if not Document.objects.filter(pk=pk).exists():
        raise ToolError(f'No existe un documento con id={pk}.')

    thread = thread_for_document(pk)
    if thread is None:
        return {'thread': None}
    return {'thread': DocumentThreadSerializer(thread).data}


def list_document_threads(arguments):
    page, page_size = _page_args(arguments)
    order = str(arguments.get('order') or 'recent').strip().lower()
    if order not in THREAD_LIST_ORDERS:
        raise ToolError(
            f'order debe ser uno de: {", ".join(THREAD_LIST_ORDERS)}.'
        )

    queryset = thread_list_queryset(
        search=arguments.get('search') or '',
        client_id=_optional_int(arguments, 'client_id'),
        project_id=_optional_int(arguments, 'project_id'),
        order=order,
    )
    total = queryset.count()
    start = (page - 1) * page_size
    return {
        'count': total,
        'page': page,
        'page_size': page_size,
        'results': [_thread_summary(t) for t in queryset[start:start + page_size]],
    }


def create_document_thread(arguments):
    items = _thread_items_or_error(arguments.get('items'), field='items', minimum=2)
    try:
        thread = service_create_thread(
            title=arguments.get('title') or '',
            items=items,
            actor=mcp_actor(),
        )
    except DocumentThreadError as exc:
        raise _thread_error(exc)
    return _thread_payload(thread)


def update_document_thread(arguments):
    thread = _thread_or_error(arguments.get('thread_id'))
    title = arguments.get('title')
    raw_link = arguments.get('link')
    raw_unlink = arguments.get('unlink_document_ids')

    if title in (None, '') and not raw_link and not raw_unlink:
        raise ToolError(
            'Envía title para renombrar el hilo, link para agregar o re-fechar '
            'documentos, o unlink_document_ids para retirarlos.'
        )

    actor = mcp_actor()
    try:
        # Rename and membership travel together: a half-applied update would
        # leave the thread named for a story it no longer contains.
        with transaction.atomic():
            if raw_link or raw_unlink:
                thread, _ = service_edit_members(
                    thread=thread,
                    actor=actor,
                    link=(
                        _thread_items_or_error(raw_link, field='link', minimum=1)
                        if raw_link else []
                    ),
                    unlink=_document_ids_or_error(
                        raw_unlink, field='unlink_document_ids',
                    ),
                )
            if title not in (None, ''):
                thread, _ = service_update_thread(
                    thread=thread, actor=actor, title=title,
                )
    except DocumentThreadError as exc:
        raise _thread_error(exc)
    return _thread_payload(thread)


def dissolve_document_thread(arguments):
    thread = _thread_or_error(arguments.get('thread_id'))
    payload = _thread_payload(thread)
    released = [item['document']['id'] for item in payload['items']]
    service_dissolve_thread(thread=thread)
    return {
        'dissolved': True,
        'thread': payload,
        'released_document_ids': released,
    }


# ── Tool registry ────────────────────────────────────────────────────────────

_THREAD_ID_PROP = {
    'thread_id': {'type': 'integer', 'minimum': 1, 'description': 'ID positivo del hilo.'},
}

_LINK_ITEM_SCHEMA = {
    'type': 'object',
    'properties': {
        'document_id': {'type': 'integer', 'minimum': 1, 'description': 'ID positivo del documento markdown activo a enlazar.'},
        'occurred_on': {
            'type': ['string', 'null'],
            'format': 'date',
            'description': (
                'Fecha real del hito en formato YYYY-MM-DD. Si se omite o es null se usa '
                'la fecha del documento.'
            ),
        },
    },
    'required': ['document_id'],
    'additionalProperties': False,
}


DOCUMENT_THREAD_TOOLS = [
    {
        'name': 'get_document_thread',
        'description': (
            'Devuelve el hilo cronológico completo al que pertenece un '
            'documento: sus documentos en orden, la fecha real de cada hito y '
            'quién lo enlazó. Envía document_id o thread_id; si el documento no '
            'está enlazado responde thread: null.'
        ),
        'input_schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'document_id': {
                    'type': 'integer',
                    'minimum': 1,
                    'description': 'ID positivo del documento cuyo hilo quieres consultar; envía document_id o thread_id.',
                },
                **_THREAD_ID_PROP,
            },
        },
        'handler': get_document_thread,
    },
    {
        'name': 'list_document_threads',
        'description': (
            'Lista los hilos documentales con paginación: nombre, cantidad de '
            'documentos, primer y último hito, y una vista previa de sus '
            'miembros. Filtra por cliente, proyecto o texto libre sobre el '
            'nombre del hilo y los títulos de sus documentos.'
        ),
        'input_schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'search': {
                    'type': 'string',
                    'description': (
                        'Texto libre sobre el nombre del hilo y los títulos de '
                        'sus documentos.'
                    ),
                },
                'client_id': {
                    'type': ['integer', 'null'],
                    'minimum': 1,
                    'description': 'ID positivo del cliente; filtra hilos con algún documento suyo. Omitir o null no filtra.',
                },
                'project_id': {
                    'type': ['integer', 'null'],
                    'minimum': 1,
                    'description': 'ID positivo del proyecto; filtra hilos con algún documento suyo. Omitir o null no filtra.',
                },
                'order': {
                    'type': 'string',
                    'enum': list(THREAD_LIST_ORDERS),
                    'default': 'recent',
                    'description': (
                        'recent = última edición; milestone = último hito; '
                        'title = alfabético. Por defecto recent.'
                    ),
                },
                'page': {'type': 'integer', 'default': 1, 'description': 'Página solicitada; por defecto 1. Valores menores se ajustan a 1.'},
                'page_size': {'type': 'integer', 'default': 20, 'maximum': 50, 'description': 'Hilos por página; por defecto 20, ajustados entre 1 y 50.'},
            },
        },
        'handler': list_document_threads,
    },
    {
        'name': 'create_document_thread',
        'description': (
            'Crea un hilo nuevo enlazando al menos dos documentos markdown en '
            'una sola operación atómica. Cada documento puede llevar la fecha '
            'real de su hito; si se omite se usa la del documento. Un documento '
            'sólo puede pertenecer a un hilo, y el orden se deriva de las '
            'fechas, no del orden en que se envían.'
        ),
        'input_schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'title': {
                    'type': 'string',
                    'maxLength': 255,
                    'description': (
                        'Nombre del hilo; si se omite se usa el título del '
                        'primer documento.'
                    ),
                },
                'items': {
                    'type': 'array',
                    'minItems': 2,
                    'maxItems': 50,
                    'items': _LINK_ITEM_SCHEMA,
                    'description': 'De 2 a 50 documentos markdown activos, cada uno con su ID y una fecha de hito opcional.',
                },
            },
            'required': ['items'],
        },
        'handler': create_document_thread,
    },
    {
        'name': 'update_document_thread',
        'description': (
            'Enlaza o retira documentos de un hilo existente y lo renombra. '
            'Envía link para agregar documentos nuevos o corregir la fecha de '
            'uno ya enlazado, y unlink_document_ids para retirarlos; el '
            'documento retirado no se elimina. NO reemplaza la lista completa: '
            'lo que no se menciona queda como está, y la operación se rechaza '
            'antes de dejar el hilo con menos de dos documentos.'
        ),
        'input_schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                **_THREAD_ID_PROP,
                'title': {
                    'type': 'string',
                    'maxLength': 255,
                    'description': 'Nuevo nombre del hilo (opcional).',
                },
                'link': {
                    'type': 'array',
                    'maxItems': 50,
                    'description': (
                        'Documentos a enlazar; si ya son miembros sólo se '
                        'corrige su fecha.'
                    ),
                    'items': _LINK_ITEM_SCHEMA,
                },
                'unlink_document_ids': {
                    'type': 'array',
                    'items': {'type': 'integer', 'minimum': 1},
                    'uniqueItems': True,
                    'maxItems': 50,
                    'description': (
                        'Documentos a retirar del hilo; el documento no se '
                        'elimina.'
                    ),
                },
            },
            'required': ['thread_id'],
        },
        'handler': update_document_thread,
    },
    {
        'name': 'dissolve_document_thread',
        'description': (
            'Disuelve un hilo: borra el contenedor y libera sus documentos, que '
            'quedan intactos y disponibles para otro hilo. Es irreversible y se '
            'pierde el registro de quién enlazó cada documento; la respuesta '
            'devuelve el hilo completo para poder recrearlo con '
            'create_document_thread si hizo falta.'
        ),
        'input_schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': _THREAD_ID_PROP,
            'required': ['thread_id'],
        },
        'handler': dissolve_document_thread,
    },
]
