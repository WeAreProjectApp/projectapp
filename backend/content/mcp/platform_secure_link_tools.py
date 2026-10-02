"""Administrative parity for client-owned links, on communications MCP only."""

from django.core.paginator import Paginator
from secure_links import platform_services, services
from secure_links.catalog import SECRET_TYPES, CatalogError
from secure_links.platform_serializers import CreateInput, EventMetadata

from .actor import mcp_actor
from .context import current_mcp_context
from .protocol import ToolError
from .secure_link_tools import _catalog_error, _int, _link_etags, _link_or_error, _prepare_link_action, _reject_unknown, _summary


def create_platform_secure_link(arguments):
    _reject_unknown(arguments, {
        'owner_id', 'project_id', 'request_id', 'title', 'secret_type', 'fields', 'language', 'validity_days', 'replaces',
    })
    owner_id = _int(arguments.get('owner_id'), 'owner_id')
    project_id = _int(arguments.get('project_id'), 'project_id')
    serializer = CreateInput(data={key: value for key, value in arguments.items() if key not in ('owner_id', 'project_id')})
    if not serializer.is_valid():
        raise ToolError('Revisa los datos del enlace seguro.')
    try:
        link, url, replayed = platform_services.create_owned_link(
            owner_id=owner_id, project_id=project_id, actor=mcp_actor(), **serializer.validated_data,
        )
    except CatalogError as exc:
        raise _catalog_error(exc) from exc
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    data = {**_summary(link), 'replayed': replayed}
    if url is not None:
        data['url'] = url
    return data


def list_secure_link_events(arguments):
    _reject_unknown(arguments, {'link_id', 'page', 'page_size'})
    link = _link_or_error(arguments)
    paginator = Paginator(link.events.all(), min(_int(arguments.get('page_size', 20), 'page_size'), 50))
    page = paginator.get_page(_int(arguments.get('page', 1), 'page'))
    return {
        'count': paginator.count, 'page': page.number,
        'results': EventMetadata(page.object_list, many=True, context={
            'owner_user_id': link.owner.user_id if link.owner_id else None,
        }).data,
    }


def get_secure_link_url(arguments):
    context = current_mcp_context()
    if (
        context is None or context.credential is None or not context.credential.is_usable
        or not context.credential.allows('get_secure_link_url') or not context.confirmation_bypass
    ):
        raise ToolError('La URL requiere permiso explícito y confirmación.', code='FORBIDDEN')
    arguments = _prepare_link_action(arguments)
    try:
        url = services.audited_link_url(
            _link_or_error(arguments), actor=mcp_actor(), channel='mcp', credential_id=context.credential.pk,
        )
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    return {'url': url}


PLATFORM_SECURE_LINK_TOOLS = [
    {
        'name': 'create_platform_secure_link', 'risk': 'write',
        'description': 'Crea para un cliente activo un enlace ligado a SU proyecto y destinado sólo al equipo. Catálogo texto/credenciales; no archivos, terceros ni accesos internos. request_id reutilizado con otros datos es conflicto. Repetición idéntica no devuelve URL.',
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'owner_id': {'type': 'integer', 'minimum': 1, 'description': 'UserProfile del cliente propietario.'},
                'project_id': {'type': 'integer', 'minimum': 1},
                'request_id': {'type': 'string', 'format': 'uuid'},
                'title': {'type': 'string', 'maxLength': 160},
                'secret_type': {'type': 'string', 'enum': list(SECRET_TYPES)},
                'fields': {'type': 'object', 'additionalProperties': {'type': 'string'}},
                'language': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es'},
                'validity_days': {'type': 'integer', 'enum': [1, 3, 7], 'default': 7},
                'replaces': {'type': ['integer', 'null'], 'minimum': 1},
            },
            'required': ['owner_id', 'project_id', 'request_id', 'title', 'secret_type', 'fields'],
        },
        'handler': create_platform_secure_link,
    },
    {
        'name': 'list_secure_link_events',
        'description': 'Historia paginada por enlace, sin secretos, URL, IP, navegador ni detalles sensibles.',
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {'link_id': {'type': 'integer', 'minimum': 1}, 'page': {'type': 'integer', 'minimum': 1}, 'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 50}},
            'required': ['link_id'],
        },
        'handler': list_secure_link_events,
    },
    {
        'name': 'get_secure_link_url', 'risk': 'sensitive', 'ephemeral_result': True,
        'description': 'Consulta explícitamente la URL sin leer contenido. Exige grant específico y confirmación. Resultado efímero: no se guarda en logs ni recibos; Platform debe estar activo.',
        'confirmation_message': 'Entregar al asistente la URL que permite al destinatario autorizado abrir el enlace.',
        'input_schema': {'type': 'object', 'additionalProperties': False, 'properties': {'link_id': {'type': 'integer', 'minimum': 1}}, 'required': ['link_id']},
        'prepare_arguments': _prepare_link_action, 'etag_resolver': _link_etags, 'handler': get_secure_link_url,
    },
]
