from content.mcp.confirmation import cancel_action, confirm_action
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.mcp.registry import capability_entry, visible_tools


def build_common_tools(connector, tools_provider):
    def describe_capabilities(arguments):
        requested = arguments.get('tools')
        summary = arguments.get('summary', False)
        if set(arguments) - {'tools', 'summary'} or not isinstance(summary, bool):
            raise ToolError('Usa tools (lista de nombres) y summary (booleano).')
        if 'tools' in arguments and (not isinstance(requested, list) or any(not isinstance(name, str) for name in requested)):
            raise ToolError('tools debe ser una lista de nombres.')
        context = current_mcp_context()
        tools = visible_tools(
            tools_provider(), context.credential if context is not None else None,
        )
        return {
            'connector': connector.slug,
            'version': connector.version,
            'tools': [
                capability_entry(tool, summary=summary)
                for tool in tools
                if requested is None or tool['name'] in requested
            ],
        }

    tools = [
        {
            'name': 'describe_capabilities',
            'title': 'Describe Capabilities',
            'description': (
                'Describe las acciones visibles para esta credencial con el mismo '
                'esquema que tools/list: argumentos, salida, anotaciones, riesgo y '
                'si requieren confirmación. tools limita la respuesta a esos '
                'nombres; summary=true devuelve sólo name, title, risk y '
                'requires_confirmation.'
            ),
            'risk': 'read',
            'input_schema': {
                'type': 'object', 'additionalProperties': False,
                'properties': {
                    'tools': {
                        'type': 'array', 'items': {'type': 'string'},
                        'description': 'Nombres de herramientas a describir; si se omite, se describen todas.',
                    },
                    'summary': {
                        'type': 'boolean', 'default': False,
                        'description': 'true devuelve sólo name, title, risk y requires_confirmation.',
                    },
                },
            },
            'handler': describe_capabilities,
        },
        {
            'name': 'confirm_action',
            'title': 'Confirm Action',
            'description': (
                'Ejecuta una acción previsualizada por su confirmation_id. Sólo '
                'las herramientas con requires_confirmation=true generan vistas '
                'previas; cada confirmation_id es de un solo uso y vence a los '
                '10 minutos.'
            ),
            'risk': 'sensitive',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'confirmation_id': {
                        'type': 'string', 'format': 'uuid',
                        'description': 'confirmation_id devuelto por la vista previa; de un solo uso, vence a los 10 minutos.',
                    },
                },
                'required': ['confirmation_id'],
                'additionalProperties': False,
            },
            'handler': lambda arguments: confirm_action(arguments, tools_provider()),
        },
        {
            'name': 'cancel_action',
            'title': 'Cancel Action',
            'description': 'Cancela una confirmación pendiente sin ejecutar su acción.',
            'risk': 'write',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'confirmation_id': {
                        'type': 'string', 'format': 'uuid',
                        'description': 'confirmation_id devuelto por la vista previa; de un solo uso, vence a los 10 minutos.',
                    },
                },
                'required': ['confirmation_id'],
                'additionalProperties': False,
            },
            'handler': cancel_action,
        },
    ]
    if connector.uploads:
        from copy import deepcopy

        from content.mcp.upload_tools import UPLOAD_TOOLS, VIDEO_CONNECTORS
        uploads = deepcopy(UPLOAD_TOOLS)
        if connector.slug not in VIDEO_CONNECTORS:
            uploads[0]['input_schema']['properties']['content_type']['enum'].remove('video/mp4')
        if connector.slug != 'projects':
            uploads[0]['input_schema']['properties']['content_type']['enum'].remove('application/zip')
        tools.extend(uploads)
    return tools
