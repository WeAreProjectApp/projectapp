"""Confirmed document migrations share the same engine as reviewed adoption."""

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.document_ownership_tools import (
    CLIENT_POLICY_SCHEMA,
    DOCUMENT_DECISIONS_SCHEMA,
    PORTAL_POLICY_SCHEMA,
)
from content.mcp.protocol import ToolError
from content.models import DocumentOwnershipOperation
from content.serializers.folder_migration import (
    MigrationApplySerializer,
    MigrationUndoSerializer,
)
from content.services import folder_migration_service as service

ID = {'type': 'integer', 'minimum': 1}
REASON = {'type': 'string', 'minLength': 3, 'maxLength': 2000,
          'description': 'Motivo auditable de la operación, de 3 a 2000 caracteres.'}
REQUEST = {'type': 'string', 'minLength': 1, 'maxLength': 100,
           'description': 'Clave de idempotencia de 1 a 100 caracteres; reutilizarla devuelve el recibo del mismo plan.'}
HASH = {'type': 'string', 'pattern': '^[a-f0-9]{64}$',
        'description': 'impact_hash de preview_folder_migration_undo, con 64 caracteres hexadecimales en minúsculas; rechaza cambios posteriores.'}
MIGRATION_ID = {**ID, 'description': 'ID positivo del recibo de migración que se consulta o deshace.'}
PROJECT_FIELDS = {
    'name': {'type': 'string', 'minLength': 1, 'maxLength': 200, 'description': 'Nombre del proyecto, de 1 a 200 caracteres.'},
    'client_profile_id': {**ID, 'description': 'ID positivo del perfil de cliente del nuevo proyecto.'},
    'description': {'type': 'string', 'default': '', 'description': 'Descripción del proyecto; por defecto vacía.'},
    'state_id': {**ID, 'description': 'ID positivo de un estado activo del catálogo de proyectos; omitir usa el estado inicial.'},
}
MIGRATION_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'source_folder_id': {**ID, 'description': 'ID positivo de la carpeta fuente que se adoptará o cuyo contenido se moverá.'},
        'strategy': {'type': 'string', 'enum': ['adopt_source', 'move_contents'],
                     'description': 'adopt_source convierte la fuente en raíz; move_contents mueve sus hijos y documentos a la raíz del proyecto.'},
        'target': {'type': 'object', 'additionalProperties': False,
                   'description': 'Destino: elige exactamente project_id para un proyecto existente o create_project para crear uno.',
                   'properties': {'project_id': {**ID, 'description': 'ID positivo del proyecto destino existente.'}, 'create_project': {
                       'type': 'object', 'additionalProperties': False, 'properties': PROJECT_FIELDS,
                       'description': 'Datos del proyecto que se creará como destino; requiere nombre y perfil de cliente.',
                       'required': ['name', 'client_profile_id'],
                   }}, 'oneOf': [{'required': ['project_id']}, {'required': ['create_project']}]},
        'include_folder_ids': {'type': 'array', 'items': ID, 'maxItems': 100, 'uniqueItems': True,
                               'description': 'Hasta 100 IDs positivos de hijos directos de la fuente, sin repetidos; sólo move_contents. Omitir mueve todos los hijos.'},
        'include_document_ids': {'type': 'array', 'items': ID, 'maxItems': 100, 'uniqueItems': True,
                                 'description': 'Hasta 100 IDs positivos de documentos directos de la fuente, sin repetidos; sólo move_contents. Omitir mueve todos los documentos directos.'},
        'client_policy': CLIENT_POLICY_SCHEMA, 'portal_policy': PORTAL_POLICY_SCHEMA,
        'document_decisions': DOCUMENT_DECISIONS_SCHEMA,
        'archive_source_when_empty': {'type': 'boolean', 'default': False,
                                      'description': 'Archiva la fuente si queda vacía tras move_contents; por defecto false.'},
        'source_rename_to': {'type': 'string', 'minLength': 1, 'maxLength': 120,
                             'description': 'Nuevo nombre de la fuente, de 1 a 120 caracteres, sin duplicar hermanas; omitir conserva el nombre salvo al adoptar la raíz.'},
    }, 'required': ['source_folder_id', 'strategy', 'target'],
}
APPLY_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'plan_token': {'type': 'string', 'minLength': 1,
                                              'description': 'Token firmado de preview_folder_migration, ligado al actor y credencial; válido 30 minutos.'},
                               'reason': REASON, 'request_id': REQUEST},
                'required': ['plan_token', 'reason', 'request_id']}
UNDO_SCHEMA = {'type': 'object', 'additionalProperties': False,
               'properties': {'migration_id': MIGRATION_ID, 'expected_impact_hash': HASH, 'reason': REASON, 'request_id': REQUEST},
               'required': ['migration_id', 'expected_impact_hash', 'reason', 'request_id']}
ADOPT_SCHEMA = {'type': 'object', 'additionalProperties': False,
                'properties': {'folder_id': {**ID, 'description': 'ID positivo de la raíz manual activa que se adoptará.'},
                               'project_id': {**ID, 'description': 'ID positivo del proyecto existente sin raíz o con plantilla descartable.'},
                               'client_policy': CLIENT_POLICY_SCHEMA,
                               'portal_policy': PORTAL_POLICY_SCHEMA, 'document_decisions': DOCUMENT_DECISIONS_SCHEMA,
                               'reason': REASON, 'request_id': REQUEST},
                'required': ['folder_id', 'project_id', 'reason', 'request_id']}


def _credential():
    context = current_mcp_context()
    return context.credential if context else None


def _prepare_apply(arguments):
    serializer = MigrationApplySerializer(data=arguments)
    serializer.is_valid(raise_exception=True)
    args = dict(serializer.validated_data)
    service.decode_plan_token(args['plan_token'], actor=mcp_actor(), credential=_credential())
    return args


def _apply_preview(arguments):
    payload = service.decode_plan_token(arguments['plan_token'], actor=mcp_actor(), credential=_credential())
    replay = service._replay(arguments['request_id'], payload['plan_hash'], mcp_actor(), _credential())
    if replay is not None:
        return {'can_apply': True, 'blockers': [], 'plan_hash': payload['plan_hash'], 'replay': replay}
    _payload, plan = service.plan_from_token(arguments['plan_token'], actor=mcp_actor(), credential=_credential())
    if plan['plan_hash'] != payload['plan_hash']:
        raise ToolError('El plan cambió; vuelve a previsualizar la migración.', code='STALE_VERSION')
    if plan['blockers']:
        raise ToolError('La migración tiene bloqueos.', code='CONFLICT', details={'blockers': plan['blockers']})
    return plan


def _apply(arguments):
    args = _prepare_apply(arguments)
    return service.apply_folder_migration(**args, actor=mcp_actor(), credential=_credential())


def _prepare_undo(arguments):
    serializer = MigrationUndoSerializer(data=arguments)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


def _undo_preview(arguments):
    replay = service._replay(arguments['request_id'], arguments['expected_impact_hash'], mcp_actor(), _credential())
    if replay is not None:
        if replay.get('reverts') != arguments['migration_id']:
            raise ToolError('Este request_id pertenece a otro deshacer.', code='REQUEST_ID_CONFLICT')
        return {'can_apply': True, 'blockers': [], 'impact_hash': arguments['expected_impact_hash'], 'replay': replay}
    impact = service.preview_undo_migration(arguments['migration_id'])
    if impact['impact_hash'] != arguments['expected_impact_hash']:
        raise ToolError('El impacto cambió; vuelve a previsualizar deshacer.', code='STALE_VERSION')
    if impact['blockers']:
        raise ToolError('No se puede deshacer la migración.', code='CONFLICT', details={'blockers': impact['blockers']})
    return impact


def _undo(arguments):
    args = _prepare_undo(arguments)
    operation_id = args.pop('migration_id')
    return service.undo_migration(operation_id, **args, actor=mcp_actor(), credential=_credential())


def _adoption_input(arguments):
    return {'source_folder_id': arguments['folder_id'], 'strategy': 'adopt_source',
            'target': {'project_id': arguments['project_id']},
            **{key: arguments[key] for key in ('client_policy', 'portal_policy', 'document_decisions') if key in arguments}}


def _prepare_adopt(arguments):
    # Freeze a signed plan in the confirmation, rather than deciding afresh at execution.
    normalized = service._normalized(_adoption_input(arguments))
    operation = DocumentOwnershipOperation.objects.filter(request_id=arguments['request_id']).first()
    if operation:
        service._replay(arguments['request_id'], operation.plan_hash, mcp_actor(), _credential())
        if operation.kind != 'adoption' or operation.input != normalized:
            raise ToolError('Este request_id pertenece a otro plan.', code='REQUEST_ID_CONFLICT')
        token = service._sign_plan(normalized, operation.plan_hash, mcp_actor(), _credential())
    else:
        preview = service.preview_folder_migration(normalized, actor=mcp_actor(), credential=_credential())
        token = preview['plan_token']
    return _prepare_apply({'plan_token': token, 'reason': arguments['reason'], 'request_id': arguments['request_id']})


def _adopt(arguments):
    return _apply(arguments if 'plan_token' in arguments else _prepare_adopt(arguments))


def _tool(name, description, schema, handler, *, sensitive=False, **hooks):
    return {
        'name': name, 'description': description, 'input_schema': schema,
        'output_schema': {'type': 'object'}, 'handler': handler, 'strict_arguments': True,
        'risk': 'sensitive' if sensitive else 'read', 'requires_confirmation': sensitive,
        'annotations': {'readOnlyHint': not sensitive, 'destructiveHint': sensitive,
                        'idempotentHint': True, 'openWorldHint': False}, **hooks,
    }


FOLDER_MIGRATION_TOOLS = [
    _tool('preview_folder_migration',
          'Previsualiza adoptar la fuente como raíz o mover su contenido, creando un proyecto o usando uno existente. '
          'client_policy decide la propiedad y portal_policy la exposición. Los filtros y el archivado son de move_contents. '
          'Nunca agrega sufijos: los nombres repetidos bloquean. Emite un plan_token ligado a actor y credencial, válido 30 minutos.',
          MIGRATION_SCHEMA, lambda args: service.preview_folder_migration(args, actor=mcp_actor(), credential=_credential())),
    _tool('apply_folder_migration',
          'Aplica el plan_token de preview_folder_migration con confirmación, motivo y request_id idempotente. '
          'El token dura 30 minutos; revalida propiedad, portal y nombres bajo candados, sin sufijos silenciosos. '
          'Devuelve un recibo auditable que permite deshacer mientras sus registros no hayan cambiado.',
          APPLY_SCHEMA, _apply, sensitive=True, prepare_arguments=_prepare_apply,
          impact_builder=_apply_preview, etag_resolver=lambda args: {'folder_migration': _apply_preview(args)['plan_hash']}),
    _tool('get_folder_migration',
          'Consulta el recibo de una migración: registros trasladados, carpetas creadas o archivadas y elementos pendientes con su motivo.',
          {'type': 'object', 'additionalProperties': False, 'properties': {'migration_id': MIGRATION_ID}, 'required': ['migration_id']},
          lambda args: service.get_folder_migration(args['migration_id'])),
    _tool('preview_folder_migration_undo',
          'Previsualiza deshacer exactamente una migración: muestra cambios posteriores, contenido nuevo, uso del proyecto y el orden de deshacer requerido.',
          {'type': 'object', 'additionalProperties': False, 'properties': {'migration_id': MIGRATION_ID}, 'required': ['migration_id']},
          lambda args: service.preview_undo_migration(args['migration_id'])),
    _tool('undo_folder_migration',
          'Deshace con confirmación y expected_impact_hash una migración sin pisar cambios posteriores. '
          'Restaura propiedad, ubicación y archivado exactos; elimina sólo plantillas vacías y el proyecto creado si sigue sin uso.',
          UNDO_SCHEMA, _undo, sensitive=True, prepare_arguments=_prepare_undo,
          impact_builder=_undo_preview, etag_resolver=lambda args: {'folder_migration_undo': _undo_preview(args)['impact_hash']}),
    _tool('adopt_folder_as_project_root',
          'Adopta una raíz manual activa como raíz de un proyecto existente sin raíz o con plantilla descartable. '
          'Usa el mismo motor, políticas de cliente y portal, plan firmado de 30 minutos, auditoría y deshacer. '
          'La confirmación muestra el plan completo y nunca agrega sufijos a los nombres.',
          ADOPT_SCHEMA, _adopt, sensitive=True, prepare_arguments=_prepare_adopt,
          impact_builder=_apply_preview, etag_resolver=lambda args: {'folder_migration': _apply_preview(args)['plan_hash']}),
]
