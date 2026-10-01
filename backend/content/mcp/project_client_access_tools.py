"""Explicit exposure policy parity; no conversational credential revelation."""
from accounts.services.project_client_access import policy_etag
from content.mcp.actor import mcp_actor
from content.mcp.operation_builder import _op
from content.mcp.project_idea_tools import schema

FIELDS = schema({name: {'type': 'boolean'} for name in ('site_url', 'admin_url', 'admin_username', 'admin_password')},
                ['site_url', 'admin_url', 'admin_username', 'admin_password'])
MATRIX = schema({'production': FIELDS, 'staging': FIELDS}, ['production', 'staging'])
POLICY = schema({'expected_version': {'type': 'integer', 'minimum': 0},
                 'source_token': {'type': 'string', 'maxLength': 1000}, 'permissions': MATRIX},
                ['expected_version', 'source_token', 'permissions'])

set_policy = _op('set_project_client_access_policy',
    'Habilita o revoca datos de acceso por proyecto y campo, con confirmación y datos previsualizados vigentes.',
    'panel-client-access-policy', 'PATCH', ('project_id',), 'sensitive', True, payload_schema=POLICY)
set_policy['etag_resolver'] = lambda arguments: {
    f'project:{arguments["project_id"]}:client-access': policy_etag(arguments['project_id'], mcp_actor())}

PROJECT_CLIENT_ACCESS_TOOLS = [
    _op('get_project_client_access_policy', 'Consulta la matriz de exposición y disponibilidad sin revelar credenciales.', 'panel-client-access-policy', path=('project_id',)),
    set_policy,
    _op('preview_project_client_access', 'Previsualiza exclusivamente URLs y acciones autorizadas para el cliente; nunca revela credenciales.', 'panel-client-access-preview', path=('project_id',)),
    _op('list_project_client_access_events', 'Consulta habilitaciones, revocaciones y consultas sin valores sensibles.', 'panel-client-access-events', path=('project_id',)),
]
