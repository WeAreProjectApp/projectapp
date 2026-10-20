#!/usr/bin/env python3
"""Read local MCP configuration without printing tokens or changing clients."""
import argparse
import json
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit

ALIASES = {
    'gestor_contable': 'accounting', 'gestor_propuestas': 'proposals',
    'gestor_clientes': 'clients', 'gestor_documentos': 'documents',
    'gestor_comunicaciones': 'communications', 'gestor_blogs': 'blog',
    'linkedin_personal_content': 'linkedin-personal',
    'gestor_comercial': 'commercial', 'gestor_contenido': 'content',
    'gestor_proyectos': 'projects', 'gestor_tareas': 'tasks',
    'gestor_operaciones': 'operations',
}
CANONICAL = {
    **{slug: 'accounting' for slug in ('accounting', 'accounting-ledger', 'accounting-billing', 'accounting-cards')},
    **{slug: 'commercial' for slug in ('commercial', 'clients', 'proposals', 'diagnostics', 'additional-modules', 'partnership-program', 'building-with-us', 'building-on-demand')},
    **{slug: 'content' for slug in ('content', 'blog', 'linkedin-personal')},
    **{slug: slug for slug in ('projects', 'documents', 'communications', 'tasks', 'operations')},
}


def inspect_servers(client, servers):
    rows = []
    for name, config in servers.items():
        url = config.get('url', '')
        parsed = urlsplit(url)
        match = re.search(r'/api/mcp/([^/]+)', parsed.path)
        slug = match.group(1) if match else ALIASES.get(name, name if name in CANONICAL else None)
        if slug not in CANONICAL:
            continue
        endpoint = f'{parsed.scheme}://{parsed.hostname}/api/mcp/{slug}/' if parsed.hostname else None
        rows.append({'client': client, 'configured_name': name, 'source_slug': slug,
                     'canonical': CANONICAL[slug], 'endpoint_without_credentials': endpoint,
                     'credential_catalog': 'unverified', 'migration_verified': False})
    return rows


def audit(codex, claude):
    rows, unavailable = [], []
    if codex.is_file():
        rows.extend(inspect_servers('Codex local', tomllib.loads(codex.read_text()).get('mcp_servers', {})))
    else:
        unavailable.append('Codex local configuration')
    if claude.is_file():
        data = json.loads(claude.read_text())
        rows.extend(inspect_servers('Claude Code global', data.get('mcpServers', {})))
        for index, project in enumerate(data.get('projects', {}).values()):
            rows.extend(inspect_servers(f'Claude Code project {index + 1}', project.get('mcpServers', {})))
    else:
        unavailable.append('Claude Code local configuration')
    unavailable.append('Claude web / other hosts: not inspectable from local configuration')
    groups = {}
    for row in rows:
        groups.setdefault((row['client'], row['canonical']), []).append(row['configured_name'])
    duplicates = [{'client': client, 'canonical': canonical, 'configured_names': names}
                  for (client, canonical), names in groups.items() if len(names) > 1]
    return {'read_only': True, 'configured_consumers': rows, 'duplicate_module_configurations': duplicates,
            'unverified_surfaces': unavailable,
            'next_step': 'Publish the canonical endpoint, issue source-scoped credentials, migrate and verify each client, then evaluate retirement.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-config', type=Path, default=Path.home() / '.codex/config.toml')
    parser.add_argument('--claude-config', type=Path, default=Path.home() / '.claude.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = audit(args.codex_config, args.claude_config)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(args.check and bool(report['duplicate_module_configurations']))


if __name__ == '__main__':
    raise SystemExit(main())
