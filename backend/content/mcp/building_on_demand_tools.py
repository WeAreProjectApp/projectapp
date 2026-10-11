"""Cell program administration through version-bound preview and confirmation."""
from functools import partial

from content.mcp.actor import mcp_actor
from content.mcp.context import current_mcp_context
from content.mcp.operation_builder import _op
from content.mcp.protocol import ToolError
from content.mcp.schema_policy import closed_object
from content.services import building_on_demand_program_service as service
from content.services.building_on_demand_content import (
    BuildingOnDemandError, card_json_schema, economics_json_schema,
    estimator_sizes_json_schema, estimator_task_json_schema, faq_json_schema,
    section_json_schema, settings_json_schema, term_json_schema, tier_json_schema,
)


def _run(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except BuildingOnDemandError as exc:
        raise ToolError(str(exc), code=exc.code, details=exc.details) from exc


def _known(arguments, fields):
    if not isinstance(arguments, dict) or set(arguments) - set(fields):
        raise ToolError('Hay argumentos desconocidos.')


def _read(arguments):
    _known(arguments, [])
    return _run(service.read_program)


def _economics(arguments):
    _known(arguments, [])
    return _run(service.economics)


def _versions(arguments):
    _known(arguments, ['limit', 'offset', 'include_content'])
    return _run(service.list_versions, **arguments)


def _preview(arguments):
    _known(arguments, ['sections', 'settings', 'if_match'])
    return _run(service.prepare_operation, 'update_program', arguments)


def resource_etags(arguments=None):
    return _run(service.resource_etags, arguments)


def _prepare_sensitive(arguments, *, operation):
    prepared = _run(service.prepare_operation, operation, arguments, require_match=True)
    return {**arguments, '_expected_etags': prepared['resource_etags']}


def _impact(arguments, *, operation):
    public = {key: value for key, value in arguments.items() if key != '_expected_etags'}
    return _run(service.prepare_operation, operation, public, require_match=True)


def _apply(arguments, *, operation):
    context = current_mcp_context()
    if context is None or not context.confirmation_bypass:
        raise ToolError('La operación requiere confirm_action.', code='CONFIRMATION_REQUIRED')
    arguments = dict(arguments)
    expected = arguments.pop('_expected_etags', None)
    if expected is None:
        raise ToolError('La confirmación no conserva la versión previsualizada.', code='STALE_VERSION')
    return _run(service.apply_operation, operation, arguments, actor=mcp_actor(),
                credential=context.credential, expected_etags=expected)


_MATCH = {'type': 'string', 'minLength': 1,
          'description': 'ETag vigente del programa obtenido en la consulta previa.'}
_NOTE = {'type': 'string', 'minLength': 1, 'maxLength': 4000,
         'description': 'Motivo del cambio o restauración, guardado en el historial.'}
_ID = {'type': 'string', 'minLength': 1, 'pattern': r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
       'description': 'Identificador estable del elemento existente que se modifica o elimina.'}
_POSITION = {'type': 'integer', 'minimum': 0,
             'description': 'Posición desde cero; si se omite, agrega el elemento al final.'}
_CARD_COLLECTIONS = ['roles', 'bag_rules', 'hosting_features', 'good_for', 'not_for']
_COLLECTION = {'type': 'string', 'enum': _CARD_COLLECTIONS,
               'description': 'Colección de tarjetas bilingües que se administra.'}
_VERSION = {'type': 'integer', 'minimum': 1,
            'description': 'Identificador de la revisión del programa que se restaura.'}
_HISTORY_SCHEMA = closed_object({
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50,
              'description': 'Cantidad máxima de versiones que se devuelven.'},
    'offset': {'type': 'integer', 'minimum': 0,
               'description': 'Cantidad de versiones que se omiten al paginar.'},
    'include_content': {'type': 'boolean',
                        'description': 'Incluye el contenido bilingüe y los datos privados de cada versión.'},
})
_READ_ANNOTATIONS = {'readOnlyHint': True, 'destructiveHint': False,
                     'idempotentHint': True, 'openWorldHint': False}
_WRITE_ANNOTATIONS = {**_READ_ANNOTATIONS, 'readOnlyHint': False}


def _published_schema(schema):
    """Declare empty fixed properties on closed slug maps for the MCP policy."""
    if isinstance(schema, dict):
        schema = {key: _published_schema(value) for key, value in schema.items()}
        if schema.get('type') == 'object' and 'patternProperties' in schema:
            schema.setdefault('properties', {})
    elif isinstance(schema, list):
        schema = [_published_schema(value) for value in schema]
    return schema


def _schema(operation, *, sensitive=True):
    fields = {
        'update_program': {'sections': section_json_schema(), 'settings': settings_json_schema()},
        'restore_version': {'version_id': _VERSION},
        'create_tier': {'tier': tier_json_schema(), 'position': _POSITION},
        'update_tier': {'tier_id': _ID, 'changes': tier_json_schema(partial=True)},
        'remove_tier': {'tier_id': _ID},
        'create_term': {'term': term_json_schema()},
        'update_term': {'term_id': _ID, 'changes': term_json_schema(partial=True)},
        'remove_term': {'term_id': _ID},
        'create_estimator_task': {'task': estimator_task_json_schema(), 'position': _POSITION},
        'update_estimator_task': {'task_id': _ID, 'changes': estimator_task_json_schema(partial=True)},
        'remove_estimator_task': {'task_id': _ID},
        'create_faq': {'item': faq_json_schema(), 'position': _POSITION},
        'update_faq': {'item_id': _ID, 'changes': faq_json_schema(partial=True)},
        'remove_faq': {'item_id': _ID},
        'create_card': {'collection': _COLLECTION, 'item': card_json_schema(), 'position': _POSITION},
        'update_card': {'collection': _COLLECTION, 'item_id': _ID, 'changes': card_json_schema(partial=True)},
        'remove_card': {'collection': _COLLECTION, 'item_id': _ID},
        'reorder_items': {
            'collection': {**_COLLECTION, 'enum': ['tiers', 'terms', 'estimator_tasks', 'faq', *_CARD_COLLECTIONS],
                           'description': 'Colección que se reordena conservando sus reglas numéricas.'},
            'ids': {'type': 'array', 'minItems': 1, 'maxItems': 20, 'uniqueItems': True,
                    'items': _ID, 'description': 'Permutación exacta de los identificadores actuales en el nuevo orden.'},
        },
        'update_estimator_sizes': {'sizes': estimator_sizes_json_schema()},
        'update_economics': {'economics': economics_json_schema()},
    }[operation]
    properties = {**fields, 'if_match': _MATCH}
    required = sorted(service.OPERATIONS[operation]['required'])
    if sensitive:
        properties['change_note'] = _NOTE
        required += ['if_match', 'change_note']
    return _published_schema(closed_object(properties, required))


_DESCRIPTIONS = {
    'update_program': 'Previsualiza secciones completas ES/EN y ajustes de bolsa e IVA; conserva lo omitido. Con if_match y change_note, confirm_action publica una nueva versión.',
    'restore_version': 'Previsualiza restaurar una revisión del programa como nueva versión, sin borrar la historia. Exige if_match, change_note y confirm_action.',
    'create_tier': 'Previsualiza crear un plan con cifras, textos ES/EN y costos privados de hosting. Revalida orden, descuentos y recomendado antes de confirm_action.',
    'update_tier': 'Previsualiza actualizar cifras, textos o hosting de un plan existente; conserva los campos omitidos y sólo confirm_action publica la versión.',
    'remove_tier': 'Previsualiza eliminar un plan, sus textos ES/EN y sus costos de hosting. Las tareas que lo referencian bloquean la eliminación; protege el último plan y el recomendado. Sólo confirm_action aplica.',
    'create_term': 'Previsualiza crear un plazo con textos ES/EN y descuentos para cada plan. Valida meses y descuentos crecientes antes de confirm_action.',
    'update_term': 'Previsualiza actualizar meses, etiquetas ES/EN o descuentos de un plazo; protege las reglas del mensual y publica sólo con confirm_action.',
    'remove_term': 'Previsualiza eliminar un plazo no mensual, sus textos ES/EN y sus descuentos en cada plan. Las referencias incompatibles bloquean la eliminación antes de confirm_action.',
    'create_estimator_task': 'Previsualiza crear una tarea del estimador con textos ES/EN, tamaño y plan mínimo existentes. Sólo confirm_action publica la versión.',
    'update_estimator_task': 'Previsualiza cambiar textos ES/EN, tamaño o plan mínimo de una tarea del estimador; revalida las referencias antes de confirm_action.',
    'remove_estimator_task': 'Previsualiza eliminar una tarea del estimador y sus textos ES/EN; conserva al menos una tarea y bloquea referencias incompatibles antes de confirm_action.',
    'create_faq': 'Previsualiza agregar una pregunta frecuente con su respuesta en español e inglés, en la posición elegida. Sólo confirm_action publica.',
    'update_faq': 'Previsualiza actualizar la pregunta o respuesta ES/EN de una pregunta frecuente existente; conserva lo omitido y exige confirm_action.',
    'remove_faq': 'Previsualiza eliminar una pregunta frecuente y su respuesta ES/EN; conserva la lista mínima y bloquea referencias incompatibles antes de confirm_action.',
    'create_card': 'Previsualiza crear una tarjeta ES/EN de roles, reglas de bolsa, hosting o encaje del programa. Valida límites y publica con confirm_action.',
    'update_card': 'Previsualiza actualizar título o resumen ES/EN de una tarjeta en la colección elegida; conserva campos omitidos y publica con confirm_action.',
    'remove_card': 'Previsualiza eliminar una tarjeta y sus textos ES/EN de roles, reglas de bolsa, hosting o encaje; conserva la lista mínima y bloquea referencias incompatibles antes de confirm_action.',
    'reorder_items': 'Previsualiza reordenar los mismos identificadores de una colección en ES/EN y su oferta numérica; conserva reglas crecientes y exige confirm_action.',
    'update_estimator_sizes': 'Previsualiza actualizar los rangos de horas de xs, s, m y l sin agregar, eliminar ni reordenar tamaños. Sólo confirm_action publica.',
    'update_economics': 'Previsualiza actualizar costos internos, IVA, proveedor, fuente o hosting por plan; estos datos son privados y sólo confirm_action guarda.',
}


def _write_tool(operation):
    names = {'update_program': 'update_building_on_demand_program',
             'restore_version': 'restore_building_on_demand_program_version'}
    verb, subject = operation.split('_', 1)
    return {
        'name': names.get(operation, f'{verb}_building_on_demand_{subject}'),
        'description': _DESCRIPTIONS[operation], 'input_schema': _schema(operation),
        'risk': 'sensitive', 'requires_confirmation': True, 'strict_arguments': True,
        'annotations': {**_WRITE_ANNOTATIONS, 'destructiveHint': verb == 'remove',
                        'idempotentHint': verb != 'create'},
        'handler': partial(_apply, operation=operation),
        'prepare_arguments': partial(_prepare_sensitive, operation=operation),
        'impact_builder': partial(_impact, operation=operation), 'etag_resolver': resource_etags,
    }


_RENDER = _op(
    'render_building_on_demand_program_pdf',
    'Genera el PDF público vigente de Building on Demand en es o en como artefacto temporal firmado, sin costos internos ni contrato.',
    'public-building-on-demand-program-pdf', 'GET', risk='read',
)
_RENDER['input_schema'] = closed_object({
    'lang': {'type': 'string', 'enum': ['es', 'en'], 'default': 'es',
             'description': 'Idioma del PDF público de la presentación.'},
})
_RENDER['annotations'] = dict(_READ_ANNOTATIONS)
_RENDER['strict_arguments'] = True
_render_handler = _RENDER['handler']


def _render(arguments):
    _known(arguments, ['lang'])
    if arguments.get('lang', 'es') not in ('es', 'en'):
        raise ToolError('Usa es o en.', code='INVALID_LANGUAGE', details={'path': 'lang'})
    return _render_handler(arguments)


_RENDER['handler'] = _render
BUILDING_ON_DEMAND_TOOLS = [
    {'name': 'get_building_on_demand_program', 'risk': 'read', 'strict_arguments': True,
     'description': 'Lee el programa completo ES/EN, oferta, datos internos, cifras derivadas, autor, motivo, versión y etag vigente.',
     'input_schema': closed_object({}), 'handler': _read, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'get_building_on_demand_economics', 'risk': 'read', 'strict_arguments': True,
     'description': 'Lee la economía privada por plan y plazo: costos, alojamiento, ingreso neto y horas de equilibrio calculadas por el servidor.',
     'input_schema': closed_object({}), 'handler': _economics, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'list_building_on_demand_program_versions', 'risk': 'read', 'strict_arguments': True,
     'description': 'Lista revisiones inmutables del programa con autor, fecha, motivo y origen de restauración; include_content añade los datos completos.',
     'input_schema': _HISTORY_SCHEMA, 'handler': _versions, 'annotations': dict(_READ_ANNOTATIONS)},
    {'name': 'preview_building_on_demand_program_update', 'risk': 'read', 'strict_arguments': True,
     'description': 'Valida secciones completas ES/EN o ajustes de bolsa e IVA y muestra el diff y advertencias sin guardar; conserva las secciones omitidas.',
     'input_schema': _schema('update_program', sensitive=False), 'handler': _preview,
     'annotations': dict(_READ_ANNOTATIONS)},
    _RENDER,
    *[_write_tool(operation) for operation in service.OPERATIONS],
]
