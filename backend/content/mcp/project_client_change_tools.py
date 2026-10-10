"""Confirmed project client transfers use the Panel's full impact preview."""

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from content.mcp.errors import normalize_error
from content.mcp.operation_builder import _op
from content.mcp.proposal_schemas import check_known_fields, guarded_arguments
from content.mcp.protocol import ToolError
from content.mcp.schemas.projects_bridge import PROJECTS_BRIDGE_SCHEMAS
from content.serializers.panel_projects import ProjectChangeClientSerializer
from content.services.diagnostic_privacy import register_mcp_domain_codes

register_mcp_domain_codes('project_client_change_blocked')

PREVIEW = _op(
    'preview_project_client_change',
    'Evalúa la historia financiera, contractual, de entregas y tickets y los efectos de mover o '
    'desvincular los registros. can_apply y blockers reflejan las mismas reglas que change_project_client. '
    'Pasa impact_hash como expected_impact_hash a change_project_client después de revisar el impacto.',
    'panel-projects-change-client-preview', path=('project_id',),
    **PROJECTS_BRIDGE_SCHEMAS['preview_project_client_change'],
)
CHANGE = _op(
    'change_project_client',
    'Cambia el propietario del proyecto tras revisar preview_project_client_change y confirmar el impacto. '
    'mode=move: los registros vinculados siguen al nuevo cliente; mode=detach: conservan su cliente '
    'y pierden el proyecto. Los ingresos con cuenta activa se desvinculan y las conversaciones '
    'conservan siempre su cliente original. '
    'Requiere expected_impact_hash vigente; la historia financiera o del cliente bloquea el traslado.',
    'panel-projects-change-client', 'POST', ('project_id',), 'sensitive', True,
    **PROJECTS_BRIDGE_SCHEMAS['change_project_client'],
)
_change_handler = CHANGE['handler']


def _prepare(arguments):
    check_known_fields(arguments, CHANGE['accepted_arguments_schema'])
    args = guarded_arguments(arguments, CHANGE)
    data = args.pop('data', {})
    args.update(data)
    payload_fields = CHANGE['_panel_operation']['payload_schema']['properties']
    serializer = ProjectChangeClientSerializer(data={key: value for key, value in args.items() if key in payload_fields})
    serializer.fields['client_profile_id'] = serializers.IntegerField(min_value=1)
    serializer.fields['mode'] = serializers.ChoiceField(choices=('move', 'detach'))
    serializer.fields['expected_impact_hash'].required = True
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError as exc:
        message, code, details = normalize_error(exc.detail)
        raise ToolError(message, code=code, details=details) from exc
    return {**args, **{key: serializer.validated_data[key] for key in payload_fields}}


def _preview(arguments):
    return PREVIEW['handler']({
        'project_id': arguments['project_id'], 'client_profile_id': arguments['client_profile_id'],
    })


def _blocked(preview, *, guard_code=None):
    details = {
        'blockers': preview['blockers'], 'blocker_counts': preview.get('blocker_counts', {}),
        'can_apply': False,
    }
    if guard_code is not None:
        details['guard_code'] = guard_code
    return ToolError('El proyecto conserva historia que impide cambiar de cliente.',
                     code='PROJECT_CLIENT_CHANGE_BLOCKED', details=details)


def _confirmed_impact(arguments):
    preview = _preview(arguments)
    if preview['impact_hash'] != arguments['expected_impact_hash']:
        raise ToolError('El impacto cambió. Vuelve a revisar la vista previa.', code='STALE_VERSION')
    if not preview['can_apply']:
        raise _blocked(preview)
    return {**preview, 'mode': arguments['mode'], 'selected_plan': preview['planned'][arguments['mode']]}


def _etags(arguments):
    preview = _preview(arguments)
    if not preview['can_apply']:
        # Confirm checks etags before the handler. Preserve the domain rejection
        # when new history appears, rather than reducing it to a stale hash.
        first_code = preview['blockers'][0]['code']
        guard_code = 'VALIDATION_ERROR' if first_code == 'client_change_financial_history' else first_code.upper()
        raise _blocked(preview, guard_code=guard_code)
    return {'project_client_change': preview['impact_hash']}


def _change(arguments):
    try:
        return _change_handler(arguments)
    except ToolError as exc:
        if exc.details.get('blockers'):
            raise _blocked(exc.details, guard_code=exc.code) from exc
        raise


PREVIEW['annotations'] = {
    'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False,
}
CHANGE['requires_confirmation'] = True
CHANGE['annotations'] = {
    'readOnlyHint': False, 'destructiveHint': True, 'idempotentHint': False, 'openWorldHint': False,
}
CHANGE['prepare_arguments'] = _prepare
CHANGE['impact_builder'] = _confirmed_impact
CHANGE['etag_resolver'] = _etags
CHANGE['handler'] = _change

PROJECT_CLIENT_CHANGE_TOOLS = [PREVIEW, CHANGE]
