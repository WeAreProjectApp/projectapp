from content.mcp.confirmation import cancel_action, confirm_action
from content.mcp.context import current_mcp_context


def build_common_tools(connector_slug, tools_provider, *, include_uploads=False):
    def describe_capabilities(arguments):
        context = current_mcp_context()
        tools = [
            tool for tool in tools_provider()
            if context is None
            or context.credential is None
            or context.credential.allows(tool['name'])
        ]
        return {
            'connector': connector_slug,
            'version': '2.0.0',
            'tools': [
                {
                    'name': tool['name'],
                    'title': tool.get('title'),
                    'description': tool['description'],
                    'risk': tool.get('risk'),
                    'requires_confirmation': bool(tool.get('requires_confirmation')),
                    'input_schema': tool['input_schema'],
                    'output_schema': tool.get('output_schema', {}),
                    'annotations': tool.get('annotations', {}),
                }
                for tool in tools
                if tool['name'] != 'describe_capabilities'
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
            'input_schema': {'type': 'object', 'properties': {}},
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
        from copy import deepcopy
        from content.mcp.upload_tools import UPLOAD_TOOLS, VIDEO_CONNECTORS
        uploads = deepcopy(UPLOAD_TOOLS)
        if connector_slug not in VIDEO_CONNECTORS:
            uploads[0]['input_schema']['properties']['content_type']['enum'].remove('video/mp4')
        tools.extend(uploads)
    return tools
