"""Explicit exposure policy parity; no conversational credential revelation."""
from accounts.services.project_client_access import policy_etag

from content.mcp.actor import mcp_actor
from content.mcp.operation_builder import _op
from content.mcp.schemas.projects_bridge import PROJECTS_BRIDGE_SCHEMAS

set_policy = _op('set_project_client_access_policy',
    'Habilita o revoca datos de acceso por proyecto y campo, con confirmación y datos previsualizados vigentes.',
    'panel-client-access-policy', 'PATCH', ('project_id',), 'sensitive', True,
    **PROJECTS_BRIDGE_SCHEMAS['set_project_client_access_policy'],
)
set_policy['etag_resolver'] = lambda arguments: {
    f'project:{arguments["project_id"]}:client-access': policy_etag(arguments['project_id'], mcp_actor())}

PROJECT_CLIENT_ACCESS_TOOLS = [
    _op('get_project_client_access_policy', 'Consulta la matriz de exposición y disponibilidad sin revelar credenciales.', 'panel-client-access-policy', path=('project_id',), **PROJECTS_BRIDGE_SCHEMAS['get_project_client_access_policy']),
    set_policy,
    _op('preview_project_client_access', 'Previsualiza exclusivamente URLs y acciones autorizadas para el cliente; nunca revela credenciales.', 'panel-client-access-preview', path=('project_id',), **PROJECTS_BRIDGE_SCHEMAS['preview_project_client_access']),
    _op('list_project_client_access_events', 'Consulta habilitaciones, revocaciones y consultas sin valores sensibles.', 'panel-client-access-events', path=('project_id',), **PROJECTS_BRIDGE_SCHEMAS['list_project_client_access_events']),
]
