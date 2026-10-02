"""MCP tools for one-time secure links, exposed on the communications connector.

Secret reads require an explicit credential grant and an ephemeral confirmation.
Create/update arguments and reveal results never enter persisted MCP payloads.
Ordinary reads remain metadata-only; URLs require creation, reactivation or an
explicit confirmed lookup.
"""

from django.core.paginator import Paginator
from django.db import connection
from secure_links import services
from secure_links.catalog import SECRET_TYPES, CatalogError, catalog_payload, type_label
from secure_links.models import SecureLink
from secure_links.serializers import PanelCreateSerializer, PanelUpdateSerializer

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError

_ALLOWED_CREATE = {
    'secret_type', 'title', 'fields', 'client_id', 'project_id', 'language', 'validity_days',
}


def _reject_unknown(arguments, allowed):
    if not isinstance(arguments, dict):
        raise ToolError('Los argumentos deben ser un objeto JSON.')
    unknown = sorted(set(arguments) - set(allowed))
    if unknown:
        raise ToolError('La solicitud contiene campos no permitidos.')


def _int(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
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
        raise ToolError('El enlace seguro no existe o fue eliminado.', code='NOT_FOUND')
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
        'lifecycle_status': link.lifecycle_status,
        'sent_at': link.sent_at.isoformat() if link.sent_at else None,
        'sent_by': link.sent_by_id,
        'language': link.language,
        'client_id': link.client_id,
        'project_id': link.project_id,
        'expires_at': link.expires_at.isoformat(),
        'consumed_at': link.consumed_at.isoformat() if link.consumed_at else None,
        'revoked_at': link.revoked_at.isoformat() if link.revoked_at else None,
        'activation_count': link.activation_count,
        'created_at': link.created_at.isoformat(),
        'updated_at': link.updated_at.isoformat(),
        'owner_id': link.owner_id,
        'audience': link.audience,
        'replaces': link.replaces_id,
        'replaced_by': getattr(getattr(link, 'replaced_by', None), 'pk', None),
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
    data = _panel_data(PanelCreateSerializer, arguments)
    try:
        link, url = services.create_link(
            origin=SecureLink.Origin.MCP, actor=mcp_actor(), **data,
        )
    except CatalogError as exc:
        raise _catalog_error(exc) from exc
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    return {
        **_summary(link),
        'url': url,
        'url_notice': (
            'Única vez que se entrega la URL. Inclúyela en el borrador; '
            'el equipo puede volver a copiarla desde /panel/secure-links.'
        ),
    }


def _catalog_error(exc):
    # Unknown keys can themselves contain secrets. Only echo catalog field names.
    known = {field['key'] for definition in SECRET_TYPES.values() for field in definition['fields']}
    names = sorted(set(exc.errors) & known)
    suffix = f" ({', '.join(names)})" if names else ''
    return ToolError(f'Contenido inválido{suffix}. Revisa los campos del tipo seleccionado.')


def _panel_data(serializer_class, arguments):
    data = {key: value for key, value in arguments.items() if key != 'link_id'}
    for source, target in (('client_id', 'client'), ('project_id', 'project')):
        if source in data:
            value = data.pop(source)
            data[target] = None if value is None else _int(value, source)
    serializer = serializer_class(data=data)
    if not serializer.is_valid():
        raise ToolError('Revisa el título, los campos y las asociaciones del enlace.')
    return serializer.validated_data


def update_secure_link(arguments):
    _reject_unknown(arguments, {'link_id', 'title', 'client_id', 'project_id', 'secret_type', 'fields'})
    link = _link_or_error(arguments)
    changes = _panel_data(PanelUpdateSerializer, arguments)
    if not changes:
        raise ToolError('Envía al menos un cambio.')
    try:
        link = services.update_link(link, actor=mcp_actor(), **changes)
    except CatalogError as exc:
        raise _catalog_error(exc) from exc
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    return _summary(link)


def _prepare_link_action(arguments):
    _reject_unknown(arguments, {'link_id'})
    return {'link_id': _link_or_error(arguments).pk}


def _link_etags(arguments):
    # During confirmation this lock lasts through the handler and receipt write.
    link = _link_or_error(arguments)
    if connection.in_atomic_block:
        try:
            link = services._locked_link(link)
        except services.SecureLinkError as exc:
            raise ToolError(exc.message, code=exc.code) from exc
    return {str(link.pk): link.updated_at.isoformat()}


def delete_secure_link(arguments):
    arguments = _prepare_link_action(arguments)
    try:
        services.delete_link(_link_or_error(arguments))
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    return {'id': arguments['link_id'], 'deleted': True}


def reveal_secure_link_content(arguments):
    context = current_mcp_context()
    if (
        context is None or context.credential is None
        or not context.credential.is_usable
        or not context.credential.allows('reveal_secure_link_content')
        or not context.confirmation_bypass
    ):
        raise ToolError('La lectura requiere permiso explícito y confirmación.', code='FORBIDDEN')
    arguments = _prepare_link_action(arguments)
    try:
        return services.mcp_content(
            _link_or_error(arguments), actor=mcp_actor(), credential_id=context.credential.pk,
        )
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc


def list_secure_links(arguments):
    arguments = arguments or {}
    _reject_unknown(arguments, {'owner_id', 'client_id', 'project_id', 'status', 'lifecycle_status', 'page', 'page_size'})
    query = SecureLink.objects.select_related('replaced_by')
    if arguments.get('client_id') not in (None, ''):
        query = query.filter(client_id=_int(arguments['client_id'], 'client_id'))
    if arguments.get('owner_id') not in (None, ''):
        query = query.filter(owner_id=_int(arguments['owner_id'], 'owner_id'))
    if arguments.get('project_id') not in (None, ''):
        query = query.filter(project_id=_int(arguments['project_id'], 'project_id'))
    status = arguments.get('status')
    if status:
        if status not in SecureLink.STATUSES:
            raise ToolError(f'status debe ser uno de: {", ".join(SecureLink.STATUSES)}.')
        query = query.with_status(status)
    lifecycle_status = arguments.get('lifecycle_status')
    if lifecycle_status:
        if lifecycle_status not in SecureLink.LIFECYCLE_STATUSES:
            raise ToolError(f'lifecycle_status debe ser uno de: {", ".join(SecureLink.LIFECYCLE_STATUSES)}.')
        query = query.with_lifecycle_status(lifecycle_status)
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


def mark_secure_link_sent(arguments):
    _reject_unknown(arguments, {'link_id'})
    try:
        return _summary(services.mark_sent(_link_or_error(arguments), actor=mcp_actor()))
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc



def _prepare_reactivation(arguments):
    _reject_unknown(arguments, {'link_id', 'validity_days', 'rotate'})
    link = _link_or_error(arguments)
    rotate = arguments.get('rotate', False)
    if not isinstance(rotate, bool):
        raise ToolError('rotate debe ser booleano.')
    try:
        days = services._validity(arguments.get('validity_days'), allowed=(
            services.PUBLIC_VALIDITY_CHOICES if link.origin == SecureLink.Origin.PLATFORM else services.VALIDITY_CHOICES
        ))
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
    return {'link_id': link.pk, 'validity_days': days, 'rotate': rotate or link.origin == SecureLink.Origin.PLATFORM}


def reactivate_secure_link(arguments):
    _reject_unknown(arguments, {'link_id', 'validity_days', 'rotate'})
    try:
        link, _url = services.reactivate(
            _link_or_error(arguments), actor=mcp_actor(),
            validity_days=arguments.get('validity_days'),
            rotate=arguments.get('rotate', False),
        )
    except services.SecureLinkError as exc:
        raise ToolError(exc.message, code=exc.code) from exc
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
                'owner_id': {'type': 'integer', 'minimum': 1},
                'project_id': {'type': 'integer', 'minimum': 1},
                'status': {'type': 'string', 'enum': list(SecureLink.STATUSES)},
                'lifecycle_status': {'type': 'string', 'enum': list(SecureLink.LIFECYCLE_STATUSES)},
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
        'name': 'update_secure_link',
        'risk': 'write',
        'description': (
            'Actualiza título, asociaciones o contenido de un enlace. Los campos omitidos se '
            'conservan; client_id/project_id aceptan null. fields reemplaza el contenido completo '
            'y es obligatorio al cambiar secret_type. No consume, reactiva ni cambia la URL. '
            'Nunca devuelve secretos ni URL.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                **_LINK_ID,
                'title': {'type': 'string', 'maxLength': 160},
                'client_id': {'type': ['integer', 'null'], 'minimum': 1},
                'project_id': {'type': ['integer', 'null'], 'minimum': 1},
                'secret_type': {'type': 'string', 'enum': list(SECRET_TYPES)},
                'fields': {'type': 'object', 'additionalProperties': {'type': 'string'}},
            },
            'required': ['link_id'], 'additionalProperties': False,
        },
        'handler': update_secure_link,
    },
    {
        'name': 'delete_secure_link',
        'risk': 'sensitive',
        'confirmation_message': 'Eliminar permanentemente el enlace, su contenido y su historial.',
        'description': 'Elimina definitivamente un enlace seguro tras confirmación. No se puede deshacer.',
        'input_schema': {'type': 'object', 'properties': _LINK_ID, 'required': ['link_id'], 'additionalProperties': False},
        'prepare_arguments': _prepare_link_action,
        'etag_resolver': _link_etags,
        'handler': delete_secure_link,
    },
    {
        'name': 'reveal_secure_link_content',
        'risk': 'sensitive',
        'ephemeral_result': True,
        'confirmation_message': 'Entregar el contenido confidencial al asistente sin consumir el enlace público.',
        'description': (
            'Consulta el secreto guardado sin consumir el enlace. Requiere habilitación explícita '
            'en la credencial y confirmación por lectura. El resultado se entrega una vez y no '
            'se persiste en la confirmación; repetirla exige una nueva solicitud. No devuelve URL.'
        ),
        'input_schema': {'type': 'object', 'properties': _LINK_ID, 'required': ['link_id'], 'additionalProperties': False},
        'prepare_arguments': _prepare_link_action,
        'etag_resolver': _link_etags,
        'handler': reveal_secure_link_content,
    },
    {
        'name': 'mark_secure_link_sent',
        'risk': 'write',
        'description': 'Registra que el equipo compartió manualmente un enlace disponible. No envía correo ni WhatsApp. Repetir conserva la fecha original; nunca devuelve contenido ni URL.',
        'input_schema': {'type': 'object', 'properties': _LINK_ID, 'required': ['link_id'], 'additionalProperties': False},
        'handler': mark_secure_link_sent,
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
            'properties': {**_LINK_ID, **_VALIDITY, 'rotate': {'type': 'boolean', 'default': False, 'description': 'Platform siempre rota; enlaces legacy permiten elegir.'}},
            'required': ['link_id'],
            'additionalProperties': False,
        },
        'prepare_arguments': _prepare_reactivation,
        'etag_resolver': _link_etags,
        'handler': reactivate_secure_link,
    },
]
