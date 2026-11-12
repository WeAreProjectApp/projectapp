"""Hosting operations use the same private views, validation and version checks as Panel."""
from content.mcp.operation_builder import _op
from content.mcp.schema_policy import closed_object

VERSION = {'type': 'integer', 'minimum': 0, 'description': 'Versión vigente obtenida al consultar el control.'}
MODE = {'type': 'string', 'enum': ['normal', 'suspended', 'banner'], 'description': 'Modo visual: normal, pantalla de suspensión o banner de pago pendiente.'}
LIST_QUERY = closed_object({
    'search': {'type': 'string', 'maxLength': 200, 'description': 'Busca producción por nombre o dominio.'},
    'project_id': {'type': 'integer', 'minimum': 1, 'description': 'Filtra por proyecto comercial vinculado.'},
    'page': {'type': 'integer', 'minimum': 1, 'description': 'Página de hasta veinte resultados.'},
})

HOSTING_CONTROL_TOOLS = [
    _op('list_hosting_controls', 'Lista producciones y sus controles de hosting, incluidos destinos sin vínculo comercial. Distingue configuración de aplicación confirmada.',
        'hosting-controls', query_schema=LIST_QUERY, envelope_aliases=False),
    _op('get_hosting_control', 'Consulta ambos mensajes, modo configurado, destinos y recibos efectivos de producción. No expone credenciales.',
        'hosting-control-detail', path=('control_id',), envelope_aliases=False),
    _op('set_hosting_control_mode', 'Cambia manualmente el modo visual de una producción. Sustituye el modo anterior en una operación; normal retira el aviso. No detiene servicios ni altera datos.',
        'hosting-control-mode', 'PATCH', ('control_id',), 'sensitive', True, envelope_aliases=False,
        payload_schema=closed_object({'expected_version': VERSION, 'mode': MODE}, ['expected_version', 'mode'])),
    _op('update_hosting_control_message', 'Edita sólo el título y texto del modo indicado. Conserva el otro mensaje y el modo activo; un texto activo queda pendiente hasta el recibo del sitio.',
        'hosting-control-message', 'PATCH', ('control_id',), 'sensitive', True, envelope_aliases=False,
        payload_schema=closed_object({
            'expected_version': VERSION,
            'message_mode': {'type': 'string', 'enum': ['suspended', 'banner'], 'description': 'Mensaje de suspensión o de pago pendiente que se edita.'},
            'title': {'type': 'string', 'minLength': 1, 'maxLength': 200, 'description': 'Título en texto plano, independiente por modo.'},
            'text': {'type': 'string', 'minLength': 1, 'maxLength': 2000, 'description': 'Mensaje en texto plano; admite saltos de línea.'},
        }, ['expected_version', 'message_mode', 'title', 'text'])),
    _op('list_hosting_control_events', 'Consulta el historial de cambios de modo y mensajes con actor, origen, fecha y antes/después.',
        'hosting-control-events', path=('control_id',), envelope_aliases=False,
        query_schema=closed_object({'page': LIST_QUERY['properties']['page']})),
]
