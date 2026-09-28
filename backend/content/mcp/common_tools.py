from content.mcp.confirmation import cancel_action, confirm_action
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError


def build_common_tools(connector_slug, tools_provider, *, include_uploads=False):
    def describe_capabilities(arguments):
        requested = arguments.get('tools')
        summary = arguments.get('summary', False)
        if set(arguments) - {'tools', 'summary'} or not isinstance(summary, bool):
            raise ToolError('Usa tools (lista de nombres) y summary (booleano).')
        if 'tools' in arguments and (not isinstance(requested, list) or any(not isinstance(name, str) for name in requested)):
            raise ToolError('tools debe ser una lista de nombres.')
        context = current_mcp_context()
        tools = [
            tool for tool in tools_provider()
            if context is None
            or context.credential is None
            or context.credential.allows(tool['name'])
        ]
        return {
            'connector': connector_slug,
            'version': '3.0.0' if connector_slug == 'documents' else '2.0.0',
            'tools': [
                {
                    'name': tool['name'],
                    'title': tool.get('title'),

                    'risk': tool.get('risk'),
                    'requires_confirmation': bool(tool.get('requires_confirmation')),
                    **({} if summary else {
                        'description': tool['description'],
                        'input_schema': tool['input_schema'],
                        'output_schema': tool.get('output_schema', {}),
                        'annotations': tool.get('annotations', {}),
                    }),
                }
                for tool in tools
                if tool['name'] != 'describe_capabilities' and (requested is None or tool['name'] in requested)
            ],
        }

    tools = [
        {
            'name': 'describe_capabilities',
            'title': 'Describe Capabilities',
            'description': (
                'Describe todas las acciones disponibles, sus argumentos, '
                'riesgo y necesidad de confirmación.'
            ),
            'risk': 'read',
            'input_schema': {
                'type': 'object', 'additionalProperties': False,
                'properties': {
                    'tools': {'type': 'array', 'items': {'type': 'string'}},
                    'summary': {'type': 'boolean', 'default': False},
                },
            },
            'handler': describe_capabilities,
        },
        {
            'name': 'confirm_action',
            'title': 'Confirm Action',
            'description': (
                'Ejecuta exactamente una acción sensible previsualizada, '
                'usando su confirmation_id de un solo uso.'
            ),
            'risk': 'sensitive',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'confirmation_id': {'type': 'string', 'format': 'uuid'},
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
                    'confirmation_id': {'type': 'string', 'format': 'uuid'},
                },
                'required': ['confirmation_id'],
                'additionalProperties': False,
            },
            'handler': cancel_action,
        },
    ]
    if include_uploads:
        from content.mcp.upload_tools import UPLOAD_TOOLS
        tools.extend(UPLOAD_TOOLS)
    return tools
