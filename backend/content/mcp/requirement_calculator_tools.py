"""Calculator administration and external-chat context through existing MCP catalogs."""
import json
from pathlib import Path

from content.mcp.operation_builder import _op
from content.mcp.schema_policy import closed_object


def _schema(value, field=''):
    if isinstance(value, dict):
        return closed_object({key: _schema(item, key) for key, item in value.items()}, required=list(value))
    if isinstance(value, list):
        return {'type': 'array', 'items': _schema(value[0]) if value else {'type': 'string'}, 'maxItems': 500}
    if field in {'points', 'hours_min', 'hours_max', 'standard_value_cop', 'surcharge_percent',
                 'minimum', 'maximum', 'deviation_percent', 'hourly_cost_cop'}:
        return {'type': ['number', 'string', 'null'] if field in {'minimum', 'maximum', 'standard_value_cop', 'hourly_cost_cop'} else ['number', 'string']}
    if isinstance(value, int):
        return {'type': 'integer'}
    return {'type': 'string', 'maxLength': 30000}


_SEED = json.loads((Path(__file__).resolve().parents[1] / 'data/requirement_calculator.json').read_text())
DEFINITION = _schema(_SEED)
IDENTIFIER = {'type': 'integer', 'minimum': 1}
TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 2000}
MATCH = {'type': 'string', 'minLength': 1, 'description': 'Versión/ETag devuelta por la consulta anterior.'}
PAGE = closed_object({'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50},
                      'offset': {'type': 'integer', 'minimum': 0}})
WRITE_FIELDS = {'definition': DEFINITION, 'note': TEXT, 'if_match': MATCH}


def _tool(name, description, route, *, method='GET', path=(), fields=None, required=(), sensitive=False):
    schema = closed_object(fields or {}, required=list(required))
    return _op(name, description, route, method, path=path,
               risk='sensitive' if sensitive else 'read' if method == 'GET' or 'preview' in name else 'write',
               confirm=sensitive, envelope_aliases=False,
               **({'query_schema': schema} if method == 'GET' else {'payload_schema': schema}))


CALCULATOR_TOOLS = [
    _tool('get_requirement_calculator_settings', 'Consulta la definición general, sus parámetros internos, documento y versión para editar.', 'calculator-definition'),
    _tool('preview_requirement_calculator', 'Valida parámetros y previsualiza el documento sin guardar cambios.', 'calculator-preview',
          method='POST', fields={'definition': DEFINITION}, required=('definition',)),
    _tool('publish_requirement_calculator', 'Activa una revisión general y sincroniza documento y valores por talla. No modifica versiones particulares.',
          'calculator-definition', method='POST', fields={**WRITE_FIELDS, 'document_id': IDENTIFIER},
          required=('definition', 'note', 'if_match'), sensitive=True),
    _op('list_requirement_calculator_revisions', 'Lista revisiones generales conservadas con paginación.', 'calculator-revisions',
        query_schema=PAGE, envelope_aliases=False),
    _tool('get_requirement_calculator_revision', 'Consulta los parámetros de una revisión histórica. Para restaurarla, publícala como otra revisión.',
          'calculator-revision', path=('revision_id',)),
    _tool('get_requirement_calculator',
          'Invoca la calculadora desde Claude o ChatGPT: consulta instrucciones y parámetros para clasificar el requerimiento en el chat. '
          'Con project_id usa su versión aprobada; sin ella avisa y usa la general. project_version_id permite revisar un borrador explícito. '
          'Aplica las reglas, devuelve talla y explicación sin horas ni valores internos y registra el resultado con record_requirement_estimate.',
          'calculator-context', fields={'project_id': IDENTIFIER, 'project_version_id': IDENTIFIER,
                                       'requirement': {'type': 'string', 'maxLength': 30000}}),
    _op('list_requirement_estimates', 'Lista resúmenes paginados y tres cierres recientes por estimación. Usa get_requirement_estimate y list_requirement_actuals para el texto y evidencia completos.',
        'calculator-estimates', query_schema=PAGE, envelope_aliases=False),
    _tool('get_requirement_estimate', 'Consulta el requerimiento y explicación completos de una estimación interna.',
          'calculator-estimate-detail', path=('estimate_id',)),
    _op('list_requirement_actuals', 'Consulta la evidencia completa de cierres y correcciones, tres por página.',
        'calculator-actual-history', path=('estimate_id',), query_schema=closed_object({
            'limit': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'offset': {'type': 'integer', 'minimum': 0}}), envelope_aliases=False),
    _tool('record_requirement_estimate', 'Registra la clasificación realizada en el chat con su versión exacta; no aprueba documentos ni descuenta cupos.',
          'calculator-estimates', method='POST', fields={
              'request_id': {'type': 'string', 'format': 'uuid'}, 'revision_id': IDENTIFIER,
              'project_id': IDENTIFIER, 'project_version_id': IDENTIFIER,
              'definition_digest': {'type': 'string', 'minLength': 64, 'maxLength': 64},
              'requirement': {'type': 'string', 'minLength': 1, 'maxLength': 30000},
              'size': {'type': 'string', 'enum': ['XS', 'S', 'M', 'L', 'XL', 'PROJECT']},
              'signal_ids': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 100},
              'explanation': {'type': 'string', 'minLength': 1, 'maxLength': 15000},
              'expected_size': {'type': 'string', 'enum': ['XS', 'S', 'M', 'L', 'XL', 'PROJECT']},
          }, required=('request_id', 'revision_id', 'definition_digest', 'requirement', 'size', 'signal_ids', 'explanation')),
    _tool('record_requirement_actual', 'Registra esfuerzo real con evidencia y costo interno opcional. Para corregir conserva el último evento en supersedes_id.',
          'calculator-actuals', method='POST', fields={
              'estimate_id': IDENTIFIER, 'actual_hours': {'type': 'number', 'exclusiveMinimum': 0},
              'hourly_cost_cop': {'type': ['number', 'null'], 'exclusiveMinimum': 0},
              'evidence': {'type': 'string', 'minLength': 1, 'maxLength': 8000},
              'cause': {'type': 'string', 'minLength': 1, 'maxLength': 8000}, 'supersedes_id': IDENTIFIER,
          }, required=('estimate_id', 'actual_hours', 'evidence', 'cause')),
    _tool('get_requirement_calibration', 'Consulta consistencia, medianas reales y cobertura de costos por talla y definición. Nunca recalibra automáticamente.',
          'calculator-calibration', fields=PAGE['properties']),
]

PROJECT_CALCULATOR_TOOLS = [
    _tool('get_project_calculator_version', 'Consulta parámetros e historial de ajustes de una versión particular por su identificador.',
          'project-calculator-draft', path=('version_id',)),
    _tool('get_project_requirement_calculator', 'Consulta la calculadora aprobada del proyecto, su documento, borrador y versiones anteriores.',
          'project-calculator', path=('project_id',)),
    _tool('create_project_calculator_draft', 'Prepara una variante negociada desde una revisión general fija y crea su documento privado en el proyecto.',
          'project-calculator', method='POST', path=('project_id',),
          fields={'base_revision_id': IDENTIFIER, 'note': TEXT, 'if_match': MATCH}, required=('base_revision_id', 'note', 'if_match')),
    _tool('update_project_calculator_parameters', 'Modifica sólo parámetros existentes del borrador y regenera su documento; textos, estructura y fórmulas permanecen fijos.',
          'project-calculator-draft', method='PATCH', path=('version_id',), fields=WRITE_FIELDS,
          required=('definition', 'note', 'if_match')),
    _tool('approve_project_requirement_calculator', 'Registra aprobación interna, congela documento y PDF y asigna la versión al proyecto. No envía ni publica al cliente.',
          'project-calculator-approve', method='POST', path=('version_id',),
          fields={'note': TEXT, 'if_match': MATCH}, required=('note', 'if_match'), sensitive=True),
]
