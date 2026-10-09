from copy import deepcopy

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


CONNECTOR_VERSIONS = {'documents': '3.1.0', 'proposals': '2.1.0', 'projects': '2.1.0', 'building-with-us': '1.0.0'}


def connector_version(slug, default='2.0.0'):
    return CONNECTOR_VERSIONS.get(slug, default)


def public_tool(tool):
    """The sole public schema projection for list and capabilities discovery."""
    return {
        'name': tool['name'], 'title': tool.get('title'),
        'description': tool['description'],
        'inputSchema': deepcopy(tool['input_schema']),
        'outputSchema': deepcopy(tool.get('output_schema', {})),
        'annotations': deepcopy(tool.get('annotations', {})),
    }


def server_info(server_name=None):
    slug = (server_name or '').removeprefix('projectapp-').removesuffix('-mcp')
    return {'name': server_name or 'projectapp-mcp',
            'version': connector_version(slug, default='1.0.0')}
