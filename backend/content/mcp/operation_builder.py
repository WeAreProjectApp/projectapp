"""Build a named MCP adapter over an existing Panel endpoint."""
from content.mcp.panel_bridge import panel_operation


def _op(
    name,
    description,
    route,
    method='GET',
    path=(),
    risk='read',
    confirm=False,
    assets=None,
    payload_schema=None,
):
    return panel_operation(
        name,
        description,
        route,
        method=method,
        path_params=path,
        risk=risk,
        requires_confirmation=confirm,
        confirmation_message=description,
        asset_fields=assets,
        payload_schema=payload_schema,
    )
