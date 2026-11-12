"""Explicitly granted, confirmed project deletion over the shared domain service."""
from rest_framework import serializers

from accounts.models import Project
from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.protocol import ToolError
from content.services.project_force_deletion import (
    ProjectForceDeleteError, force_delete_project, forced_deletion_preview, require_superuser,
)


class ForceDeleteInput(serializers.Serializer):
    project_id = serializers.IntegerField(min_value=1)
    delete_keys = serializers.ListField(child=serializers.CharField(max_length=120), allow_empty=True)
    confirmation = serializers.CharField(trim_whitespace=False, required=False)
    impact_token = serializers.RegexField(r'^[0-9a-f]{64}$', required=False)


def _prepare(arguments, *, mutation=False):
    context = current_mcp_context()
    if context is None:
        raise ToolError('Esta operación requiere una credencial explícita de Proyectos.', code='FORBIDDEN')
    require_superuser(mcp_actor())
    allowed = {'project_id', 'delete_keys'} | ({'confirmation', 'impact_token'} if mutation else set())
    if not isinstance(arguments, dict) or set(arguments) - allowed:
        raise ToolError('La solicitud contiene campos no permitidos.')
    serializer = ForceDeleteInput(data=arguments)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    if mutation and (data.get('confirmation') != 'DELETE' or not data.get('impact_token')):
        raise ToolError('Revisa el impacto y escribe exactamente DELETE antes de confirmar.')
    return data


def _preview(arguments):
    project = Project.objects.filter(pk=arguments['project_id']).first()
    if project is None:
        raise ToolError('El proyecto no existe o fue eliminado.', code='NOT_FOUND')
    return forced_deletion_preview(project, actor=mcp_actor(), delete_keys=arguments['delete_keys'])


def preview_project_force_delete(arguments):
    return _preview(_prepare(arguments))


def _impact(arguments):
    data = _prepare(arguments, mutation=True)
    preview = _preview(data)
    if preview['impact_token'] != data['impact_token']:
        raise ToolError('El impacto cambió. Revisa el alcance otra vez.', code='STALE_VERSION')
    if not preview['can_delete']:
        raise ToolError('La selección tiene bloqueos.', code='CONFLICT', details={'blockers': preview['blockers']})
    return preview


def _delete(arguments):
    data = _prepare(arguments, mutation=True)
    if not current_mcp_context().confirmation_bypass:
        raise ToolError('La eliminación requiere confirmación MCP.', code='FORBIDDEN')
    try:
        force_delete_project(data['project_id'], actor=mcp_actor(), **{
            key: data[key] for key in ('confirmation', 'impact_token', 'delete_keys')
        })
    except Project.DoesNotExist as exc:
        raise ToolError('El proyecto ya fue eliminado.', code='NOT_FOUND') from exc
    except ProjectForceDeleteError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.preview) from exc
    return {'deleted': True, 'project_id': data['project_id']}


PROPERTIES = {
    'project_id': {'type': 'integer', 'minimum': 1, 'description': 'ID del proyecto que se revisa o elimina.'},
    'delete_keys': {'type': 'array', 'items': {'type': 'string', 'maxLength': 120},
                    'description': 'Categorías elegidas explícitamente para borrar; [] conserva todos los datos.'},
    'confirmation': {'type': 'string', 'const': 'DELETE', 'description': 'Confirmación exacta DELETE, sin espacios.'},
    'impact_token': {'type': 'string', 'pattern': '^[0-9a-f]{64}$',
                     'description': 'Token de la vista previa para el mismo proyecto y selección.'},
}

PROJECT_FORCE_DELETE_TOOLS = [
    {
        'name': 'preview_project_force_delete', 'risk': 'read',
        'description': 'Revisa la eliminación selectiva de un proyecto. Requiere permiso explícito de eliminación forzada; no modifica datos.',
        'input_schema': {'type': 'object', 'additionalProperties': False,
                         'properties': {key: PROPERTIES[key] for key in ('project_id', 'delete_keys')},
                         'required': ['project_id', 'delete_keys']},
        'handler': preview_project_force_delete,
    },
    {
        'name': 'force_delete_project', 'risk': 'sensitive', 'requires_confirmation': True,
        'description': 'Elimina la ficha del proyecto y sólo las categorías elegidas. Conserva el historial protegido y exige permiso explícito, impacto vigente y confirmación MCP.',
        'input_schema': {'type': 'object', 'additionalProperties': False,
                         'properties': PROPERTIES, 'required': list(PROPERTIES)},
        'annotations': {'readOnlyHint': False, 'destructiveHint': True,
                        'idempotentHint': False, 'openWorldHint': False},
        'prepare_arguments': lambda arguments: _prepare(arguments, mutation=True),
        'impact_builder': _impact,
        'etag_resolver': lambda arguments: {'project_force_delete': _impact(arguments)['impact_token']},
        'handler': _delete,
    },
]
