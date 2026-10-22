"""Section-scoped projections of the existing shared video settings endpoint."""
from content.mcp.operation_builder import _op
from content.mcp.schema_policy import closed_object


def _video_settings(resource, field, video_module):
    tools = []
    for action, method in (('get', 'GET'), ('update', 'PATCH')):
        schema = closed_object({field: {
            'type': 'boolean', 'description': 'Muestra el video explicativo a los clientes.',
        }}, required=[field]) if action == 'update' else closed_object({})
        tool = _op(
            f'{action}_{resource}_video_settings',
            f'{"Consulta" if action == "get" else "Actualiza"} sólo la visibilidad del video de {video_module}.',
            'explainer-video-settings' if action == 'get' else 'update-explainer-video-settings',
            method, envelope_aliases=False,
            **({'payload_schema': schema} if action == 'update' else {'query_schema': schema}),
            risk='read' if action == 'get' else 'write',
        )
        handler = tool['handler']

        def project(arguments, handler=handler, field=field, video_module=video_module):
            result = handler(arguments)
            return {
                field: result[field],
                'resources': {key: value for key, value in result.get('resources', {}).items()
                              if key.startswith(f'{video_module}:')},
                'updated_at': result.get('updated_at'),
            }

        tool.update(handler=project, strict_arguments=True,
                    operation_id=f'panel:{method}:explainer-video-settings:{resource}')
        tools.append(tool)
    return tools


COMMERCIAL_SECTION_TOOLS = _video_settings('proposal', 'show_proposal_video', 'proposal')
OFFERING_SECTION_TOOLS = _video_settings('additional_modules', 'show_additional_modules_video', 'additional-modules')
PROGRAM_SECTION_TOOLS = _video_settings('partnership', 'show_financing_video', 'financing')
