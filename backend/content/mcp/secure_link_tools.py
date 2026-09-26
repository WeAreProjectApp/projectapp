"""MCP tools for one-time secure links, exposed on the communications connector.

Security boundary (see docs/secure-links.md):
- create_secure_link is the only MCP tool that accepts plaintext secrets. It is
  a plain ``write`` tool on purpose: a ``sensitive`` tool would persist its
  arguments in McpActionIntent. No argument carrying content ends in ``_id``,
  because only ``*_id`` values are copied into McpRequestLog.
- The link URL is returned once, at creation. Reads never return the URL or
  the content, so a leaked connector credential cannot harvest live links.
- reactivate_secure_link is sensitive (one-time confirmation) and returns
  metadata only, because confirmed results are also persisted.
"""

from accounts.models import Project, UserProfile
from django.core.paginator import Paginator
from secure_links import services
from secure_links.catalog import SECRET_TYPES, CatalogError, catalog_payload, type_label
from secure_links.models import SecureLink

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError

_ALLOWED_CREATE = {
    'secret_type', 'title', 'fields', 'client_id', 'project_id', 'language', 'validity_days',
}


def _reject_unknown(arguments, allowed):
    if not isinstance(arguments, dict):
        raise ToolError('Los argumentos deben ser un objeto JSON.')
    unknown = sorted(set(arguments) - set(allowed))
    if unknown:
        raise ToolError(f'Campos no permitidos: {", ".join(unknown)}.')


def _int(value, field):
    if isinstance(value, bool):
        raise ToolError(f'{field} debe ser un número entero.')
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ToolError(f'{field} debe ser un número entero.') from exc
    if parsed < 1:
        raise ToolError(f'{field} debe ser mayor que cero.')
    return parsed


def _link_or_error(arguments):
    link_id = arguments.get('link_id')
    if link_id in (None, ''):
        raise ToolError('link_id es obligatorio.')
    link = SecureLink.objects.select_related('client__user', 'project').filter(pk=_int(link_id, 'link_id')).first()
    if link is None:
        raise ToolError(f'No existe un enlace seguro con id={link_id}.')
    return link


def _summary(link):
    """Metadata only: never the token, the URL or the content."""
    return {
        'id': link.pk,
        'title': link.title,
        'secret_type': link.secret_type,
        'type_label': type_label(link.secret_type),
        'origin': link.origin,
        'status': link.status,
        'language': link.language,
        'client_id': link.client_id,
        'project_id': link.project_id,
        'expires_at': link.expires_at.isoformat(),
        'consumed_at': link.consumed_at.isoformat() if link.consumed_at else None,
        'revoked_at': link.revoked_at.isoformat() if link.revoked_at else None,
        'activation_count': link.activation_count,
        'created_at': link.created_at.isoformat(),
    }


def list_secure_link_types(arguments):
    _reject_unknown(arguments or {}, set())
    return {'types': catalog_payload()}


def create_secure_link(arguments):
    _reject_unknown(arguments, _ALLOWED_CREATE)
    fields = arguments.get('fields')
    if not isinstance(fields, dict) or not fields:
        raise ToolError(
            'fields es obligatorio: el enlace siempre se crea con el contenido. '
            'Si no tienes el secreto, pídeselo al operador.'
        )
    title = (arguments.get('title') or '').strip()
    if not title:
        raise ToolError('title es obligatorio (etiqueta interna del enlace).')
    client = project = None
    if arguments.get('client_id') not in (None, ''):
        client = UserProfile.objects.clients().filter(pk=_int(arguments['client_id'], 'client_id')).first()
        if client is None:
            raise ToolError(f'No existe un cliente con id={arguments["client_id"]}.')
    if arguments.get('project_id') not in (None, ''):
        project = Project.objects.filter(pk=_int(arguments['project_id'], 'project_id')).first()
        if project is None:
            raise ToolError(f'No existe un proyecto con id={arguments["project_id"]}.')
    language = arguments.get('language') or SecureLink.Language.ES
    if language not in SecureLink.Language.values:
        raise ToolError('language debe ser es o en.')
    try:
        link, url = services.create_link(
            secret_type=arguments.get('secret_type'), title=title, fields=fields,
            origin=SecureLink.Origin.MCP, actor=mcp_actor(), client=client, project=project,
            language=language, validity_days=arguments.get('validity_days'),
        )
    except CatalogError as exc:
        raise ToolError(f'Contenido inválido: {exc.errors}') from exc
    except services.SecureLinkError as exc:
        raise ToolError(exc.message) from exc
    return {
        **_summary(link),
        'url': url,
        'url_notice': (
            'Única vez que se entrega la URL. Inclúyela en el borrador; '
            'el equipo puede volver a copiarla desde /panel/secure-links.'
        ),
    }


def list_secure_links(arguments):
    arguments = arguments or {}
    _reject_unknown(arguments, {'client_id', 'project_id', 'status', 'page', 'page_size'})
    query = SecureLink.objects.all()
    if arguments.get('client_id') not in (None, ''):
        query = query.filter(client_id=_int(arguments['client_id'], 'client_id'))
    if arguments.get('project_id') not in (None, ''):
        query = query.filter(project_id=_int(arguments['project_id'], 'project_id'))
    status = arguments.get('status')
    if status:
        if status not in SecureLink.STATUSES:
            raise ToolError(f'status debe ser uno de: {", ".join(SecureLink.STATUSES)}.')
        query = query.with_status(status)
    page_size = min(_int(arguments.get('page_size') or 20, 'page_size'), 50)
    paginator = Paginator(query, page_size)
    page = paginator.get_page(_int(arguments.get('page') or 1, 'page'))
    return {
        'count': paginator.count,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'results': [_summary(link) for link in page.object_list],
    }


def get_secure_link(arguments):
    _reject_unknown(arguments, {'link_id'})
    link = _link_or_error(arguments)
    events = [
        {'kind': event.kind, 'created_at': event.created_at.isoformat()}
        for event in link.events.all()[:50]
    ]
    return {**_summary(link), 'events': events}


def revoke_secure_link(arguments):
    _reject_unknown(arguments, {'link_id'})
    link = services.revoke(_link_or_error(arguments), actor=mcp_actor())
    return _summary(link)


def reactivate_secure_link(arguments):
    _reject_unknown(arguments, {'link_id', 'validity_days'})
    try:
        link, _url = services.reactivate(
            _link_or_error(arguments), actor=mcp_actor(),
            validity_days=arguments.get('validity_days'),
        )
    except services.SecureLinkError as exc:
        raise ToolError(exc.message) from exc
    # The URL is deliberately omitted: confirmed results are persisted.
    return _summary(link)


_LINK_ID = {'link_id': {'type': 'integer', 'minimum': 1, 'description': 'ID del enlace seguro.'}}
_VALIDITY = {
    'validity_days': {
        'type': 'integer', 'enum': list(services.VALIDITY_CHOICES),
        'description': 'Días de vigencia desde ahora (1, 3, 7 o 30). Por defecto 7.',
    },
}

SECURE_LINK_TOOLS = [
    {
        'name': 'list_secure_link_types',
        'description': (
            'Lista los tipos de información sensible que admite un enlace seguro de un '
            'solo uso y los campos (key, obligatorio, longitud) de cada tipo.'
        ),
        'input_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
        'handler': list_secure_link_types,
    },
    {
        'name': 'create_secure_link',
        'description': (
            'Crea un enlace seguro de un solo uso con información sensible (credenciales, '
            'llaves, datos bancarios, comunicados) y devuelve su URL una sola vez. Úsalo en '
            'lugar de pegar secretos en correos o WhatsApp. Exige el contenido en fields; '
            'nunca inventes valores: si no los tienes, pídeselos al operador.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'secret_type': {'type': 'string', 'enum': list(SECRET_TYPES), 'description': 'Tipo del catálogo (list_secure_link_types).'},
                'title': {'type': 'string', 'maxLength': 160, 'description': 'Etiqueta interna; no se muestra antes de abrir el enlace.'},
                'fields': {'type': 'object', 'description': 'Valores por key del tipo elegido.', 'additionalProperties': {'type': 'string'}},
                'client_id': {'type': 'integer', 'minimum': 1, 'description': 'Cliente (UserProfile) asociado.'},
                'project_id': {'type': 'integer', 'minimum': 1, 'description': 'Proyecto del mismo cliente.'},
                'language': {'type': 'string', 'enum': ['es', 'en'], 'description': 'Idioma de la página que verá el destinatario.'},
                **_VALIDITY,
            },
            'required': ['secret_type', 'title', 'fields'],
            'additionalProperties': False,
        },
        'handler': create_secure_link,
    },
    {
        'name': 'list_secure_links',
        'description': (
            'Lista enlaces seguros con su estado (active, consumed, expired, revoked) por '
            'cliente o proyecto. Nunca devuelve la URL ni el contenido.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'client_id': {'type': 'integer', 'minimum': 1},
                'project_id': {'type': 'integer', 'minimum': 1},
                'status': {'type': 'string', 'enum': list(SecureLink.STATUSES)},
                'page': {'type': 'integer', 'minimum': 1},
                'page_size': {'type': 'integer', 'minimum': 1, 'maximum': 50},
            },
            'additionalProperties': False,
        },
        'handler': list_secure_links,
    },
    {
        'name': 'get_secure_link',
        'description': (
            'Muestra el estado y el historial de un enlace seguro (creado, abierto, '
            'reactivado, revocado). Nunca devuelve la URL ni el contenido.'
        ),
        'input_schema': {'type': 'object', 'properties': _LINK_ID, 'required': ['link_id'], 'additionalProperties': False},
        'handler': get_secure_link,
    },
    {
        'name': 'revoke_secure_link',
        'description': (
            'Desactiva un enlace seguro para que nadie más pueda abrirlo. El contenido '
            'queda guardado y el equipo puede reactivarlo desde el panel.'
        ),
        'input_schema': {'type': 'object', 'properties': _LINK_ID, 'required': ['link_id'], 'additionalProperties': False},
        'handler': revoke_secure_link,
    },
    {
        'name': 'reactivate_secure_link',
        'risk': 'sensitive',
        'confirmation_message': 'Reactivar el mismo enlace seguro para que pueda abrirse una vez más.',
        'description': (
            'Reactiva el mismo enlace seguro (por ejemplo, si el cliente lo abrió por error) '
            'y reinicia su vigencia. Requiere confirmación; no devuelve la URL.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {**_LINK_ID, **_VALIDITY},
            'required': ['link_id'],
            'additionalProperties': False,
        },
        'handler': reactivate_secure_link,
    },
]
