"""MCP administration uses the same Panel FBVs and domain validators."""
from content.mcp.operation_builder import _op
from content.mcp.schemas.projects_bridge import PROJECTS_BRIDGE_SCHEMAS

PROJECT_IDEA_TOOLS = [
    _op('list_project_ideas', 'Consulta sugerencias de un proyecto; una idea no cambia el alcance contractual.', 'panel-ideas', path=('project_id',), envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['list_project_ideas']),
    _op('get_project_idea', 'Consulta una sugerencia conservando su autoría original.', 'panel-idea-detail', path=('project_id', 'idea_id'), envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['get_project_idea']),
    _op('list_project_idea_revisions', 'Consulta el texto conservado de las revisiones de una idea.', 'panel-idea-revisions', path=('project_id', 'idea_id'), envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['list_project_idea_revisions']),
    _op('create_project_idea', 'Registra una idea atribuida al equipo sin crear contratos ni requerimientos.', 'panel-ideas', 'POST', ('project_id',), 'write', envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['create_project_idea']),
    _op('update_project_idea', 'Corrige una idea del equipo conservando las revisiones; no reescribe ideas del cliente.', 'panel-idea-detail', 'PATCH', ('project_id', 'idea_id'), 'write', envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['update_project_idea']),
    _op('archive_project_idea', 'Archiva una idea de forma reversible sin borrar su texto.', 'panel-idea-archive', 'POST', ('project_id', 'idea_id'), 'write', envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['archive_project_idea']),
    _op('restore_project_idea', 'Restaura una idea archivada conservando su autoría e historial.', 'panel-idea-restore', 'POST', ('project_id', 'idea_id'), 'write', envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['restore_project_idea']),
    _op('list_project_idea_collections', 'Consulta recopilaciones internas para considerar contratos futuros.', 'panel-idea-collections', path=('project_id',), envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['list_project_idea_collections']),
    _op('get_project_idea_collection', 'Consulta las copias exactas de una recopilación interna.', 'panel-idea-collection-detail', path=('project_id', 'collection_id'), envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['get_project_idea_collection']),
    _op('create_project_idea_collection', 'Conserva una selección explícita de ideas del proyecto y cliente actual sin crear un contrato.', 'panel-idea-collections', 'POST', ('project_id',), 'write', envelope_aliases=False, **PROJECTS_BRIDGE_SCHEMAS['create_project_idea_collection']),
]
