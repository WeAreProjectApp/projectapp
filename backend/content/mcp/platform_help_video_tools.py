"""Managed tutorial resources in the existing Projects connector."""
from rest_framework.exceptions import PermissionDenied

from content.mcp.actor import mcp_actor
from content.mcp.protocol import ToolError
from content.mcp.video_tools import _execute
from content.services.platform_video_service import PLATFORM_VIDEO_TOPICS


def _perform(arguments, action):
    actor = mcp_actor()
    if not actor.is_active or not actor.is_staff:
        raise PermissionDenied('Solo un administrador del panel puede administrar los videos.')
    module = PLATFORM_VIDEO_TOPICS.get(arguments.get('topic'))
    if module is None:
        raise ToolError('Tema de video inválido.', code='VALIDATION_ERROR')
    return _execute(arguments, module, False, action)


def _tools():
    result = []
    for verb, action, description in (
        ('get', 'get', 'Consulta un video de ayuda de la plataforma, su revisión y límite de carga.'),
        ('set', 'upload', 'Carga o sustituye un tutorial con un asset_id MP4 completado mediante begin_upload y complete_upload. Conserva el anterior si falla.'),
        ('remove', 'remove', 'Retira una pieza de ayuda sin restaurar el predeterminado. No modifica los interruptores de Ayuda ni activa IA.'),
        ('restore_default', 'restore-default', 'Restaura el tutorial predeterminado incluido con la aplicación sin cambiar los interruptores de Ayuda.'),
    ):
        properties = {
            'topic': {'type': 'string', 'enum': list(PLATFORM_VIDEO_TOPICS), 'description': 'Pieza de ayuda: general, chatbot o voice-reporting.'},
            'language': {'type': 'string', 'enum': ['es'], 'default': 'es', 'description': 'Los tutoriales de esta entrega están en español colombiano con subtítulos.'},
        }
        required = ['topic']
        if action != 'get':
            properties['revision'] = {'type': 'integer', 'minimum': 0, 'description': 'Revisión obtenida al consultar esta pieza antes de editar.'}
            required.append('revision')
        if action == 'upload':
            properties['asset_id'] = {'type': 'string', 'format': 'uuid', 'description': 'Identificador de una carga MP4 validada, hasta 250 MiB. Incluye los subtítulos en el video.'}
            required.append('asset_id')
        result.append({
            'name': f'{verb}_platform_help_video', 'description': description,
            'risk': 'read' if action == 'get' else 'sensitive' if action == 'remove' else 'write',
            'requires_confirmation': action == 'remove', 'confirmation_message': description,
            'input_schema': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False},
            'handler': lambda arguments, action=action: _perform(arguments, action),
        })
    return result


PLATFORM_HELP_VIDEO_TOOLS = _tools()
