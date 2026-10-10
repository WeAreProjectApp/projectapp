from copy import deepcopy

from content.mcp.schema_policy import strip_private

READ_PREFIXES = (
    'describe_', 'get_', 'list_', 'read_', 'search_', 'preview_', 'export_',
    'download_',
)
DESTRUCTIVE_PREFIXES = (
    'delete_', 'void_', 'cancel_', 'retire_', 'merge_', 'dissolve_',
)
SENSITIVE_PREFIXES = (
    'send_', 'resend_', 'publish_', 'settle_', 'liquidate_', 'finalize_',
    'launch_', 'bulk_', 'cancel_', 'retire_', 'merge_', 'delete_', 'void_',
    'dissolve_',
)


def infer_risk(name):
    if name.startswith(READ_PREFIXES):
        return 'read'
    if name.startswith(SENSITIVE_PREFIXES):
        return 'sensitive'
    return 'write'


def infer_annotations(name, risk):
    read_only = risk == 'read'
    destructive = name.startswith(DESTRUCTIVE_PREFIXES)
    idempotent = read_only or name.startswith((
        'update_', 'set_', 'archive_', 'unarchive_', 'restore_', 'close_',
        'reopen_', 'mute_', 'mark_',
    ))
    return {
        'readOnlyHint': read_only,
        'destructiveHint': destructive,
        'idempotentHint': idempotent,
        'openWorldHint': name.startswith((
            'send_', 'resend_', 'publish_', 'retry_', 'launch_',
        )),
    }


def normalize_tool(tool, connector_slug):
    normalized = deepcopy(tool)
    name = normalized['name']
    risk = normalized.get('risk', infer_risk(name))
    normalized['connector'] = connector_slug
    normalized['risk'] = risk
    normalized.setdefault('title', name.replace('_', ' ').title())
    normalized.setdefault('output_schema', {'type': 'object'})
    normalized.setdefault('annotations', infer_annotations(name, risk))
    return normalized


def normalize_tools(tools, connector_slug):
    normalized = [normalize_tool(tool, connector_slug) for tool in tools]
    names = [tool['name'] for tool in normalized]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise RuntimeError(
            f'Duplicate MCP tools for {connector_slug}: {", ".join(duplicates)}'
        )
    return normalized


def connector_version(slug, default='2.0.0'):
    from content.mcp.connectors import CONNECTORS

    connector = CONNECTORS.get(slug)
    return connector.version if connector is not None else default


def with_sensitive_confirmation(tools):
    result = []
    for source in tools:
        tool = deepcopy(source)
        risk = tool.get('risk', infer_risk(tool['name']))
        if tool['name'] in {'update_proposal_status', 'create_share_link'}:
            risk = 'sensitive'
        tool['risk'] = risk
        if risk == 'sensitive':
            tool['requires_confirmation'] = True
        result.append(tool)
    return result


def visible_tools(tools, credential):
    return [
        tool for tool in tools
        if credential is None or credential.allows(tool['name'])
    ]


def public_tool(tool):
    """The sole public schema projection for list and capabilities discovery."""
    return {
        'name': tool['name'], 'title': tool.get('title'),
        'description': tool['description'],
        'inputSchema': strip_private(tool['input_schema']),
        'outputSchema': strip_private(tool.get('output_schema', {})),
        'annotations': deepcopy(tool.get('annotations', {})),
    }


def capability_entry(tool, *, summary):
    public = public_tool(tool)
    entry = {
        'name': public['name'],
        'title': public['title'],
        'risk': tool.get('risk'),
        'requires_confirmation': bool(tool.get('requires_confirmation')),
    }
    if not summary:
        entry.update({
            'description': public['description'],
            'input_schema': public['inputSchema'],
            'output_schema': public['outputSchema'],
            'annotations': public['annotations'],
        })
    return entry
