"""Inspect MCP discovery contracts without executing business tools."""
import hashlib
import json
from pathlib import Path

import requests

from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.protocol import MODERN_PROTOCOL_VERSION, handle_message
from content.mcp.registry import public_tool
from content.mcp.schema_backlog import DEFERRED_SCHEMA_BACKLOG
from content.mcp.schema_policy import (
    OPEN_REASON_KEY,
    is_generic,
    schema_problems,
    undescribed_root_properties,
)


CONTRACTS_PATH = Path(__file__).with_name('connector_contracts.json')
SERVER_INFO_KEY = 'io.modelcontextprotocol/serverInfo'
PUBLIC_FIELDS = ('name', 'title', 'description', 'inputSchema', 'outputSchema', 'annotations')
SCHEMA_FIELDS = PUBLIC_FIELDS[1:]


class ContractReportError(ValueError):
    """A discovery request failed; messages never include credentials or bodies."""


def public_contract(slug):
    return {
        'instructions': CONNECTORS[slug].instructions,
        'tools': [
            {
                **public_tool(tool),
                'risk': tool.get('risk'),
                'requires_confirmation': bool(tool.get('requires_confirmation')),
            }
            for tool in sorted(TOOLS_BY_SLUG[slug], key=lambda tool: tool['name'])
        ],
    }


def fingerprint(slug):
    serialized = json.dumps(public_contract(slug), sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _discovery_requests():
    requests_by_channel = (
        ('initialize', 'initialize', {'protocolVersion': '2025-11-25'}),
        ('discover', 'server/discover', {}),
        ('tools_list', 'tools/list', {}),
        ('capabilities', 'tools/call', {'name': 'describe_capabilities', 'arguments': {}}),
    )
    for index, (channel, method, params) in enumerate(requests_by_channel, start=1):
        headers = {}
        if channel != 'initialize':
            params['_meta'] = {
                'io.modelcontextprotocol/protocolVersion': MODERN_PROTOCOL_VERSION,
                'io.modelcontextprotocol/clientCapabilities': {},
                'io.modelcontextprotocol/clientInfo': {'name': 'mcp-schema-report', 'version': '1.0.0'},
            }
            headers = {'MCP-Protocol-Version': MODERN_PROTOCOL_VERSION, 'Mcp-Method': method}
            if method == 'tools/call':
                headers['Mcp-Name'] = params['name']
        yield channel, {'jsonrpc': '2.0', 'id': index, 'method': method, 'params': params}, headers


def _channel_result(body, channel):
    if not isinstance(body, dict) or 'error' in body or not isinstance(body.get('result'), dict):
        raise ContractReportError(f'Respuesta MCP inválida en {channel}.')
    result = body['result']
    if channel != 'capabilities':
        return result
    if result.get('isError'):
        raise ContractReportError('describe_capabilities devolvió un error.')
    structured = result.get('structuredContent')
    if isinstance(structured, dict):
        return structured
    try:
        structured = json.loads(result['content'][0]['text'])
    except (KeyError, IndexError, TypeError, ValueError):
        raise ContractReportError('Respuesta inválida de describe_capabilities.') from None
    if not isinstance(structured, dict):
        raise ContractReportError('Respuesta inválida de describe_capabilities.')
    return structured


def local_snapshot(slug):
    snapshot = {'slug': slug, 'local': True}
    for channel, message, _ in _discovery_requests():
        _, body = handle_message(message, TOOLS_BY_SLUG[slug], connector=CONNECTORS[slug])
        snapshot[channel] = _channel_result(body, channel)
    return snapshot


def _redact(value, token):
    if isinstance(value, str):
        return value.replace(token, '[REDACTADO]')
    if isinstance(value, dict):
        return {_redact(key, token): _redact(child, token) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact(child, token) for child in value]
    return value


def remote_snapshot(base_url, slug, token, *, session):
    if not token:
        raise ContractReportError('Falta el token del conector.')
    url = f'{base_url.rstrip("/")}/api/mcp/{slug}/'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    snapshot = {'slug': slug, 'local': False}
    for channel, message, protocol_headers in _discovery_requests():
        try:
            response = session.post(
                url, json=message, headers={**headers, **protocol_headers},
                timeout=20, allow_redirects=False,
            )
        except requests.RequestException:
            raise ContractReportError(f'No se pudo consultar {channel}.') from None
        if response.status_code == 404:
            raise ContractReportError('conector inactivo o token inválido')
        if response.status_code != 200:
            raise ContractReportError(f'HTTP {response.status_code} en {channel}.')
        try:
            body = response.json()
        except ValueError:
            raise ContractReportError(f'Respuesta JSON inválida en {channel}.') from None
        snapshot[channel] = _channel_result(_redact(body, token), channel)
    return snapshot


def _described_tool(tool):
    return {
        'name': tool['name'], 'title': tool.get('title'),
        'description': tool.get('description'),
        'inputSchema': tool.get('input_schema'),
        'outputSchema': tool.get('output_schema'),
        'annotations': tool.get('annotations'),
    }


def _open_nodes(value):
    if isinstance(value, dict):
        return int(OPEN_REASON_KEY in value) + sum(_open_nodes(child) for child in value.values())
    if isinstance(value, list):
        return sum(_open_nodes(child) for child in value)
    return 0


def compare(snapshot, slug=None):
    slug = slug or snapshot['slug']
    local = snapshot.get('local', False)
    listed = snapshot['tools_list'].get('tools', [])
    described = snapshot['capabilities'].get('tools', [])
    list_by_name = {tool['name']: tool for tool in listed}
    describe_by_name = {tool['name']: _described_tool(tool) for tool in described}
    only_list = sorted(list_by_name.keys() - describe_by_name.keys())
    only_describe = sorted(describe_by_name.keys() - list_by_name.keys())
    differences = []
    for name in sorted(list_by_name.keys() & describe_by_name.keys()):
        fields = [field for field in SCHEMA_FIELDS if list_by_name[name].get(field) != describe_by_name[name].get(field)]
        if fields:
            differences.append({'name': name, 'fields': fields})

    server_infos = {
        'initialize': snapshot['initialize'].get('serverInfo', {}),
        'discover': snapshot['discover'].get('_meta', {}).get(SERVER_INFO_KEY, {}),
    }
    list_info = snapshot['tools_list'].get('_meta', {}).get(SERVER_INFO_KEY)
    if list_info is not None:
        server_infos['tools_list'] = list_info
    versions = {channel: info.get('version') for channel, info in server_infos.items()}
    versions['capabilities'] = snapshot['capabilities'].get('version')
    if local:
        versions['registry'] = CONNECTORS[slug].version
    version_ok = all(isinstance(version, str) and version for version in versions.values()) and len(set(versions.values())) == 1
    identity_differences = [channel for channel, info in server_infos.items() if info.get('name') != f'projectapp-{slug}-mcp']
    instructions = snapshot['initialize'].get('instructions')
    instruction_ok = isinstance(instructions, str) and instructions == snapshot['discover'].get('instructions')
    if local:
        instruction_ok = instruction_ok and instructions == CONNECTORS[slug].instructions
    duplicate_names = len(listed) != len(list_by_name) or len(described) != len(describe_by_name)
    complete = 'tools' in snapshot['tools_list'] and 'tools' in snapshot['capabilities'] and snapshot['capabilities'].get('connector') == slug
    tools = TOOLS_BY_SLUG[slug] if local else []
    return {
        'slug': slug, 'versions': versions,
        'tools_list_count': len(listed), 'describe_count': len(described),
        'only_tools_list': only_list, 'only_describe': only_describe,
        'differences': differences, 'identity_differences': identity_differences,
        'instructions_match': instruction_ok, 'versions_match': version_ok,
        'duplicate_names': duplicate_names, 'complete': complete,
        'generic_pending': sum(is_generic(tool) for tool in tools) if local else None,
        'documented_open_nodes': sum(
            _open_nodes(tool.get(schema, {})) for tool in tools
            for schema in ('input_schema', 'output_schema')
        ) if local else None,
        'fingerprint': fingerprint(slug) if local else None,
        'ok': bool(complete and version_ok and instruction_ok and not (
            only_list or only_describe or differences or identity_differences or duplicate_names
        )),
    }


def _cell(value):
    return '—' if value is None else str(value).replace('|', '\\|').replace('\n', ' ')


def render_markdown(results):
    columns = (
        'Conector', 'serverInfo (initialize)', 'serverInfo (discover)', 'capabilities',
        'registro', 'tools/list', 'describe', 'nombres distintos', 'esquemas distintos',
        'genéricas pendientes', 'abiertos documentados', 'huella',
    )
    lines = ['| ' + ' | '.join(columns) + ' |', '| ' + ' | '.join('---' for _ in columns) + ' |']
    details = []
    for result in results:
        versions = result['versions']
        row = (
            result['slug'], versions.get('initialize'), versions.get('discover'),
            versions.get('capabilities'), versions.get('registry'), result['tools_list_count'],
            result['describe_count'], len(result['only_tools_list']) + len(result['only_describe']),
            len(result['differences']), result['generic_pending'], result['documented_open_nodes'],
            result['fingerprint'][:12] if result['fingerprint'] else None,
        )
        lines.append('| ' + ' | '.join(_cell(value) for value in row) + ' |')
        if result['ok']:
            continue
        details.append(f'### {_cell(result["slug"])}')
        for side, label in (('only_tools_list', 'Sólo en tools/list'), ('only_describe', 'Sólo en describe_capabilities')):
            details.extend(f'- `{_cell(name)}`: {label}.' for name in result[side])
        details.extend(f'- `{_cell(tool["name"])}`: {", ".join(tool["fields"])}.' for tool in result['differences'])
        if not result['versions_match']:
            details.append('- Las versiones anunciadas difieren o faltan: ' + ', '.join(f'{channel}={_cell(version)}' for channel, version in versions.items()) + '.')
        if result['identity_differences']:
            details.append('- Identidad incorrecta: ' + ', '.join(result['identity_differences']) + '.')
        if not result['instructions_match']:
            details.append('- Las instrucciones difieren o faltan.')
        if result['duplicate_names']:
            details.append('- Hay nombres de herramientas duplicados.')
        if not result['complete']:
            details.append('- Falta una lista de herramientas o la identidad de capabilities es incorrecta.')
        details.append('')
    return '\n'.join([*lines, '', '## Diferencias', '', *(details or ['Ninguna.'])]).rstrip() + '\n'


def _grouped_names(names):
    remaining = set(names)
    groups = {}
    for slug in sorted(CONNECTORS, key=lambda slug: (CONNECTORS[slug].compatibility, slug)):
        owned = remaining & {tool['name'] for tool in TOOLS_BY_SLUG[slug]}
        if owned:
            groups[slug] = sorted(owned)
            remaining -= owned
    return sorted(groups.items())


def backlog_literals():
    tools = [tool for group in TOOLS_BY_SLUG.values() for tool in group]
    backlogs = {
        'GENERIC_ADAPTER_BACKLOG': {tool['name'] for tool in tools if is_generic(tool)},
        'UNDESCRIBED_ARGUMENT_BACKLOG': {tool['name'] for tool in tools if not is_generic(tool) and undescribed_root_properties(tool)},
        'DEFERRED_SCHEMA_BACKLOG': {tool['name'] for tool in tools if not is_generic(tool) and schema_problems(tool, undescribed_ok=True)},
    }
    lines = []
    for label, names in backlogs.items():
        deferred = label == 'DEFERRED_SCHEMA_BACKLOG'
        lines.append(f'{label} = ' + ('{' if deferred else 'frozenset({'))
        for slug, owned in _grouped_names(names):
            lines.append(f'    # {slug}')
            for name in owned:
                if deferred:
                    reason = DEFERRED_SCHEMA_BACKLOG.get(name, 'Esquema estructural pendiente; requiere un contrato explícito.')
                    lines.append(f'    {name!r}: {reason!r},')
                else:
                    lines.append(f'    {name!r},')
        lines.extend(['}' if deferred else '})', ''])
    return '\n'.join(lines)
