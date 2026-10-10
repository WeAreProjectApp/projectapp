"""Conditional project creation confirmations over the shared folder engine."""

from uuid import uuid4

from django.db import transaction

from content.mcp.actor import mcp_actor
from content.mcp.confirmation import canonical_arguments_hash
from content.mcp.context import current_mcp_context
from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError
from content.models import McpActionIntent
from content.serializers.panel_projects import CreatePanelProjectSerializer
from content.services import folder_migration_service as migration
from content.services.project_document_folder_service import (
    lock_project_root_names,
    project_root_name_decision,
)

PROJECT_FIELDS = ('name', 'client_profile_id', 'description', 'state_id')
ROOT_ADOPTION_HINT = (
    'Para decidir propietarios o exposición usa '
    'preview_folder_migration/apply_folder_migration del conector documents.'
)
CREATE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'name': {'type': 'string', 'minLength': 1, 'maxLength': 200},
        'client_profile_id': {'type': 'integer', 'minimum': 1},
        'description': {'type': 'string', 'default': ''},
        'state_id': {'type': 'integer', 'minimum': 1},
        'root_folder_id': {'type': 'integer', 'minimum': 1},
    },
    'required': ['name', 'client_profile_id'],
}

_PANEL_CREATE = _op(
    'create_project', 'Crea un proyecto con las validaciones del Panel.',
    'panel-projects-create', 'POST', risk='write',
    payload_schema={
        **CREATE_SCHEMA,
        'properties': {key: CREATE_SCHEMA['properties'][key] for key in PROJECT_FIELDS},
    },
)['handler']


def _credential():
    context = current_mcp_context()
    return context.credential if context else None


def _project_payload(arguments):
    data = {key: arguments[key] for key in PROJECT_FIELDS if key in arguments}
    serializer = CreatePanelProjectSerializer(data=data, context={'folder_migration': True})
    serializer.is_valid(raise_exception=True)
    return {
        'name': serializer.validated_data['name'],
        'client_profile_id': serializer.client_profile.pk,
        'description': serializer.validated_data['description'],
        **({'state_id': serializer.validated_data['state'].pk} if 'state' in serializer.validated_data else {}),
    }


def _needs_confirmation(arguments):
    payload = _project_payload(arguments)
    return ('root_folder_id' in arguments
            or project_root_name_decision(payload['name'])['decision'] == 'adopt')


def _preview(arguments):
    if '_plan_token' in arguments:
        _payload, plan = migration.plan_from_token(
            arguments['_plan_token'], actor=mcp_actor(), credential=_credential(),
        )
        if (plan['input']['client_policy'] != 'abort_on_conflict'
                or plan['input']['portal_policy'] != 'abort'
                or plan['input']['document_decisions']):
            raise ToolError(
                'La adopción requiere una nueva vista previa con las políticas estrictas de projects.',
                code='STALE_VERSION', details={'hint': ROOT_ADOPTION_HINT},
            )
        return plan
    payload = _project_payload(arguments)
    root_id = arguments.get('root_folder_id')
    if root_id is None:
        decision = project_root_name_decision(payload['name'])
        if decision['decision'] != 'adopt':
            raise ToolError('El proyecto no requiere adoptar una carpeta.', code='CONFLICT')
        root_id = decision['folder_id']
    return migration.preview_folder_migration({
        'source_folder_id': root_id, 'strategy': 'adopt_source',
        'target': {'create_project': payload},
        'client_policy': 'abort_on_conflict', 'portal_policy': 'abort',
    }, actor=mcp_actor(), credential=_credential())


def _impact(arguments):
    plan = _preview(arguments)
    if not plan['can_apply']:
        raise ToolError(
            'La raíz no se puede adoptar con las políticas estrictas de projects.', code='CONFLICT',
            details={'blockers': plan['blockers'], 'hint': ROOT_ADOPTION_HINT},
        )
    return plan


def _prepare(arguments):
    arguments = dict(arguments)
    plan = _impact(arguments)
    arguments['_plan_token'] = plan['plan_token']
    # A nonce binds the receipt to exactly one persisted confirmation intent.
    arguments['_request_nonce'] = str(uuid4())
    return arguments


def _etags(arguments):
    return {'project_create': _preview(arguments)['plan_hash']}


@transaction.atomic
def _create(arguments):
    context = current_mcp_context()
    if '_plan_token' not in arguments:
        if 'root_folder_id' in arguments:
            raise ToolError('Revisa y confirma la adopción antes de crear.', code='FORBIDDEN')
        return _PANEL_CREATE(_project_payload(arguments))
    if not context or not context.confirmation_bypass:
        raise ToolError('La adopción requiere una confirmación vigente.', code='FORBIDDEN')
    lock_project_root_names()
    payload, current = migration.plan_from_token(
        arguments['_plan_token'], actor=mcp_actor(), credential=_credential(),
    )
    if current['plan_hash'] != payload['plan_hash']:
        raise ToolError('La raíz cambió desde la vista previa.', code='STALE_VERSION')
    _impact(arguments)
    if 'root_folder_id' not in arguments:
        return _PANEL_CREATE(_project_payload(arguments))
    intent = McpActionIntent.objects.get(
        connector=context.connector, credential=context.credential,
        tool_name='create_project', status=McpActionIntent.STATUS_PENDING,
        arguments_hash=canonical_arguments_hash(arguments),
    )
    report = migration.apply_folder_migration(
        arguments['_plan_token'], 'create_project con raíz adoptada',
        f'project-create:{intent.pk}', actor=mcp_actor(), credential=_credential(), origin='mcp',
    )
    from content.views.panel_projects import _annotated_row

    return {
        **_annotated_row(report['project_id']),
        'document_root': {
            'folder_id': report['root_folder_id'], 'adopted': True,
            'migration_id': report['migration_id'],
        },
    }


CREATE_PROJECT = {
    'name': 'create_project',
    'description': (
        'Crea un proyecto sin duplicar nunca una raíz manual homónima. '
        'root_folder_id adopta una raíz revisada mediante confirm_action; '
        'la adopción siempre usa abort_on_conflict para la propiedad y abort para el portal, '
        'incluida la exposición de documentos archivados al restaurarse. '
        'Para decidir propietarios o exposición usa preview_folder_migration/apply_folder_migration '
        'del conector documents. '
        'Una raíz homónima segura también requiere confirmación; sin adopción el alta es inmediata.'
    ),
    'input_schema': CREATE_SCHEMA, 'output_schema': {'type': 'object'},
    'strict_arguments': True, 'risk': 'sensitive', 'requires_confirmation': True,
    'annotations': {
        'readOnlyHint': False, 'destructiveHint': True,
        'idempotentHint': False, 'openWorldHint': False,
    },
    'confirmation_predicate': _needs_confirmation, 'prepare_arguments': _prepare,
    'impact_builder': _impact, 'etag_resolver': _etags, 'handler': _create,
}
