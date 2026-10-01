"""MCP administration uses the same Panel FBVs and domain validators."""
from content.mcp.operation_builder import _op

TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 10000}
VERSION = {'type': 'integer', 'minimum': 1}
REQUEST = {'type': 'string', 'format': 'uuid'}

def schema(properties, required):
    return {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}

CREATE = schema({'text': TEXT, 'request_id': REQUEST}, ['text', 'request_id'])
EDIT = schema({'text': TEXT, 'expected_version': VERSION}, ['text', 'expected_version'])
ARCHIVE = schema({'expected_version': VERSION}, ['expected_version'])
COLLECT = schema({'title': {'type': 'string', 'minLength': 1, 'maxLength': 255}, 'request_id': REQUEST,
                  'items': {'type': 'array', 'minItems': 1, 'maxItems': 100,
                            'items': schema({'idea_id': {'type': 'integer', 'minimum': 1}, 'expected_version': VERSION}, ['idea_id', 'expected_version'])}},
                 ['title', 'items', 'request_id'])

PROJECT_IDEA_TOOLS = [
    _op('list_project_ideas', 'Consulta sugerencias de un proyecto; una idea no cambia el alcance contractual.', 'panel-ideas', path=('project_id',)),
    _op('get_project_idea', 'Consulta una sugerencia conservando su autoría original.', 'panel-idea-detail', path=('project_id', 'idea_id')),
    _op('list_project_idea_revisions', 'Consulta el texto conservado de las revisiones de una idea.', 'panel-idea-revisions', path=('project_id', 'idea_id')),
    _op('create_project_idea', 'Registra una idea atribuida al equipo sin crear contratos ni requerimientos.', 'panel-ideas', 'POST', ('project_id',), 'write', payload_schema=CREATE),
    _op('update_project_idea', 'Corrige una idea del equipo conservando las revisiones; no reescribe ideas del cliente.', 'panel-idea-detail', 'PATCH', ('project_id', 'idea_id'), 'write', payload_schema=EDIT),
    _op('archive_project_idea', 'Archiva una idea de forma reversible sin borrar su texto.', 'panel-idea-archive', 'POST', ('project_id', 'idea_id'), 'write', payload_schema=ARCHIVE),
    _op('restore_project_idea', 'Restaura una idea archivada conservando su autoría e historial.', 'panel-idea-restore', 'POST', ('project_id', 'idea_id'), 'write', payload_schema=ARCHIVE),
    _op('list_project_idea_collections', 'Consulta recopilaciones internas para considerar contratos futuros.', 'panel-idea-collections', path=('project_id',)),
    _op('get_project_idea_collection', 'Consulta las copias exactas de una recopilación interna.', 'panel-idea-collection-detail', path=('project_id', 'collection_id')),
    _op('create_project_idea_collection', 'Conserva una selección explícita de ideas del proyecto y cliente actual sin crear un contrato.', 'panel-idea-collections', 'POST', ('project_id',), 'write', payload_schema=COLLECT),
]
