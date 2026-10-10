"""Document move previews and the explicit ownership-policy contracts."""

from content.services.document_ownership_planner import (
    CLIENT_POLICIES,
    PORTAL_POLICIES,
    plan_ownership,
)

CLIENT_POLICY_SCHEMA = {
    'type': 'string', 'enum': list(CLIENT_POLICIES), 'default': 'abort_on_conflict',
    'description': 'inherit adopta cliente y proyecto; keep conserva y bloquea conflictos; abort_on_conflict hereda sólo si no hay conflicto (por defecto).',
}
PORTAL_POLICY_SCHEMA = {
    'type': 'string', 'enum': list(PORTAL_POLICIES), 'default': 'abort',
    'description': 'abort bloquea una nueva audiencia (por defecto); allow la permite; hide_new_exposure oculta documentos que ganarían audiencia, también al restaurarse.',
}
DOCUMENT_DECISIONS_SCHEMA = {
    'type': 'array', 'maxItems': 100,
    'description': 'Hasta 100 decisiones por documento, sin repetir document_id; inherit adopta la propiedad y move exige otra carpeta destino. Por defecto ninguna.',
    'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {
            'document_id': {'type': 'integer', 'minimum': 1, 'description': 'ID positivo del documento al que se aplica la decisión.'},
            'action': {'type': 'string', 'enum': ['inherit', 'move'], 'description': 'inherit adopta para este documento; move requiere otra destination_folder_id.'},
            'destination_folder_id': {'type': 'integer', 'minimum': 1, 'description': 'ID positivo de otra carpeta destino; obligatorio sólo con action=move.'},
        },
        'required': ['document_id', 'action'],
    },
}
EXPECTED_PLAN_HASH_SCHEMA = {'type': 'string', 'pattern': '^[a-f0-9]{64}$', 'description': 'plan_hash de preview_move. Rechaza la operación si cambió el plan.'}
POLICY_DESCRIPTION = (
    ' client_policy: inherit adopta cliente/proyecto sin quitar el dueño hacia un destino sin dueño; '
    'keep conserva la propiedad y bloquea conflictos; abort_on_conflict (default) hereda sólo sin conflictos. '
    'portal_policy: abort (default) bloquea nueva audiencia, allow la permite y hide_new_exposure oculta la nueva exposición. '
    'Los espejos conservan su propiedad; los registros congelados no se reasignan. '
    'Usa preview_move y su plan_hash como expected_plan_hash para revalidar la vista previa.'
)


def preview_move(arguments):
    return plan_ownership(**{'client_policy': 'abort_on_conflict', 'portal_policy': 'abort', **arguments})


DOCUMENT_OWNERSHIP_TOOLS = [
    {
        'name': 'preview_move', 'risk': 'read',
        'description': (
            'Previsualiza sin guardar el movimiento de documentos o subárboles de carpetas. '
            'Requiere document_ids o folder_ids. Muestra por documento cliente y proyecto antes→después, '
            'cambios de visibilidad en el portal, exposición latente y conflictos. '
            'plan_hash se puede pasar a move_documents o update_folder como expected_plan_hash.'
            + POLICY_DESCRIPTION
        ),
        'input_schema': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'document_ids': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'minItems': 1, 'maxItems': 100, 'uniqueItems': True,
                                 'description': 'De 1 a 100 IDs positivos de documentos, sin repetidos; envía document_ids o folder_ids.'},
                'folder_ids': {'type': 'array', 'items': {'type': 'integer', 'minimum': 1}, 'minItems': 1, 'maxItems': 100, 'uniqueItems': True,
                               'description': 'De 1 a 100 IDs positivos de carpetas con su subárbol, sin repetidos; envía folder_ids o document_ids.'},
                'destination_folder_id': {'type': ['integer', 'null'], 'minimum': 1, 'description': 'Carpeta destino; null significa raíz sólo para carpetas.'},
                'client_policy': CLIENT_POLICY_SCHEMA,
                'portal_policy': PORTAL_POLICY_SCHEMA,
                'document_decisions': DOCUMENT_DECISIONS_SCHEMA,
            },
            'required': ['destination_folder_id'],
        },
        'output_schema': {
            'type': 'object',
            'properties': {
                'destination_owner': {'type': 'object'}, 'rows': {'type': 'array', 'items': {'type': 'object'}},
                'totals': {'type': 'object'}, 'can_apply': {'type': 'boolean'},
                'blockers': {'type': 'array', 'items': {'type': 'object'}},
                'warnings': {'type': 'array', 'items': {'type': 'object'}}, 'plan_hash': {'type': 'string'},
            },
            'required': ['rows', 'totals', 'can_apply', 'blockers', 'warnings', 'plan_hash'],
        },
        'annotations': {'readOnlyHint': True, 'destructiveHint': False, 'idempotentHint': True, 'openWorldHint': False},
        'handler': preview_move,
    },
]
