"""Notice adapters; delivery_notifications is the single owner of sending rules."""
import hashlib
import json
from uuid import UUID

from content.mcp.delivery_tools import (
    CONTEXT_ID,
    REQUEST_ID,
    TEXT,
    _call,
    _tool,
)
from content.mcp.issue_tools import _validate as validate_schema
from content.mcp.platform_resource_tools import _credential
from content.mcp.protocol import ToolError

NOTICE_VERSION = {'type': 'integer', 'minimum': 1,
                  'description': 'Versión del aviso obtenida con get_delivery_notification_event.'}


def _service():
    from accounts.services import delivery_notifications
    return delivery_notifications


def _impact(arguments):
    from content.mcp.actor import mcp_actor
    _credential()
    impact = _call(_service().retry_impact, arguments['project_id'], mcp_actor(),
                   arguments['event_id'], arguments['expected_version'])
    if arguments['preview_sha256'] != impact['preview_sha256']:
        raise ToolError('El aviso no coincide con la vista revisada.', code='CONFLICT')
    return impact


def _retry(arguments, actor):
    return _call(_service().retry_event, arguments['project_id'], actor, arguments['event_id'],
                 arguments['expected_version'], arguments['request_id'], arguments['preview_sha256'],
                 credential=_credential())


DELIVERY_NOTIFICATION_TOOLS = [
    _tool('list_delivery_notification_events', 'Consulta eventos e intentos de avisos de entrega con paginación y estado explícitos.',
          lambda args, actor: _call(_service().list_events, args['project_id'], actor,
                                   page=args.get('page', 1), status=args.get('status')),
          {'page': {'type': 'integer', 'minimum': 1}, 'status': {'type': 'string',
           'enum': ['pending', 'sending', 'sent', 'failed', 'unknown', 'cancelled']}}),
    _tool('get_delivery_notification_event', 'Consulta un aviso y sus intentos sin secretos, HTML ni rutas de almacenamiento.',
          lambda args, actor: _call(_service().get_event, args['project_id'], actor, args['event_id']),
          {'event_id': CONTEXT_ID}, ('event_id',)),
    _tool('preview_delivery_notification_retry', 'Muestra el contenido, destinatarios y hash de un fallo confirmado sin ejecutar SMTP.',
          lambda args, actor: _call(_service().retry_impact, args['project_id'], actor,
                                   args['event_id'], args['expected_version']),
          {'event_id': CONTEXT_ID, 'expected_version': NOTICE_VERSION}, ('event_id', 'expected_version')),
    _tool('retry_delivery_notification_event', 'Reintenta un fallo confirmado tras confirmar el aviso exacto; estados sending o unknown permanecen bloqueados.',
          _retry, {'event_id': CONTEXT_ID, 'expected_version': NOTICE_VERSION, 'request_id': REQUEST_ID,
                   'preview_sha256': {**TEXT, 'minLength': 64, 'maxLength': 64}},
          ('event_id', 'expected_version', 'request_id', 'preview_sha256'),
          risk='sensitive', durable_execution=True, impact_builder=_impact),
]


def _guard(tool):
    def validate(arguments):
        _credential()
        validate_schema(arguments, tool['input_schema'])
        if 'event_id' in arguments:
            try:
                UUID(arguments['event_id'])
            except (ValueError, TypeError, AttributeError) as exc:
                raise ToolError('event_id debe identificar un aviso válido.') from exc

    handler = tool['handler']

    def execute(arguments):
        validate(arguments)
        return handler(arguments)

    tool['handler'] = execute
    if tool.get('requires_confirmation'):
        prepare = tool['prepare_arguments']

        def prepare_arguments(arguments):
            validate(arguments)
            return prepare(arguments)

        def etag(arguments):
            from content.mcp.actor import mcp_actor
            event = _call(_service().get_event, arguments['project_id'], mcp_actor(), arguments['event_id'])
            return {f'notice:{arguments["event_id"]}': hashlib.sha256(
                json.dumps(event, sort_keys=True).encode()).hexdigest()}

        tool['prepare_arguments'] = prepare_arguments
        tool['etag_resolver'] = etag


for _notice_tool in DELIVERY_NOTIFICATION_TOOLS:
    _guard(_notice_tool)
