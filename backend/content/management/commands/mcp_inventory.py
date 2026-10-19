"""Reproducible connector/tool ownership inventory, without issuing credentials."""
import json
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError

from content.mcp.connectors import CONNECTORS, LEGACY_TOOLS_BY_SLUG, TOOLS_BY_SLUG
from content.mcp.consolidation import operation_id
from content.mcp.module_catalog import CANONICAL_FOR, FINANCIAL_PROJECT_TOOLS, INFRASTRUCTURE_TOOLS, canonical_name, catalog_problems


def inventory(*, include_usage=False):
    by_name = defaultdict(list)
    for slug, tools in LEGACY_TOOLS_BY_SLUG.items():
        for tool in tools:
            by_name[tool['name']].append(slug)
    connectors = []
    for slug, spec in sorted(CONNECTORS.items()):
        canonical = CANONICAL_FOR[slug]
        rows = []
        for tool in LEGACY_TOOLS_BY_SLUG[slug]:
            name = tool['name']
            owner = 'accounting' if name in FINANCIAL_PROJECT_TOOLS else canonical
            replacement = canonical_name(name, owner)
            replacement = {
                'list_expected_incomes': 'list_incomes', 'get_expected_income': 'get_income',
                'get_income_detail': 'get_income', 'create_expected_income': 'create_income',
                'update_expected_income': 'update_income', 'duplicate_expected_income': 'duplicate_income',
                'launch_proposal_to_platform': 'review_proposal_approval',
            }.get(name, replacement)
            destination_names = {item['name'] for item in TOOLS_BY_SLUG[owner]}
            rows.append({
                'name': name, 'operation_id': operation_id(tool),
                'owner': owner, 'replacement': replacement,
                'decision': 'infrastructure' if name in INFRASTRUCTURE_TOOLS else
                    'adapt' if spec.compatibility else 'move' if owner != slug else
                    'rename' if replacement != name else 'keep',
                'replacement_registered': replacement in destination_names,
                'also_registered_in': [other for other in by_name[name] if other != slug],
                'risk': tool['risk'], 'requires_confirmation': bool(tool.get('requires_confirmation')),
                'usage': 'not_observed',
                'obsolescence': 'replacement_candidate' if replacement != name or owner != slug else 'not_proven',
            })
        connectors.append({
            'slug': slug, 'name': spec.server_name, 'module': spec.module_id,
            'endpoint': f'/api/mcp/{slug}/', 'version': spec.version,
            'lifecycle': 'deprecated' if spec.compatibility else 'canonical',
            'replacement': canonical, 'tools': rows,
            'published_tools': [tool['name'] for tool in TOOLS_BY_SLUG[slug]],
        })
    report = {'environment': 'local registry; deployment and cloud clients unverified',
              'canonical_count': sum(not spec.compatibility for spec in CONNECTORS.values()),
              'connectors': connectors, 'problems': catalog_problems(CONNECTORS, TOOLS_BY_SLUG)}
    if include_usage:
        from content.models import McpConnector, McpUsageDaily
        from content.mcp.migration import retirement_status
        observed = {(row.connector.slug, row.tool_name): row.last_used_at.isoformat()
                    for row in McpUsageDaily.objects.select_related('connector').order_by('last_used_at')}
        states = {row.slug: row for row in McpConnector.objects.prefetch_related('credentials')}
        for row in connectors:
            connector = states.get(row['slug'])
            row['configured'] = connector is not None
            if connector:
                row['is_active'] = connector.is_active
                row['retirement'] = retirement_status(connector)
                row['consumers'] = [
                    {'credential_id': item.pk, 'label': item.label, 'catalog': item.catalog,
                     'migrated': item.migrated_at is not None, 'revoked': item.revoked_at is not None}
                    for item in connector.credentials.all()
                ]
            for tool in row['tools']:
                tool['usage'] = observed.get((row['slug'], tool['name']), 'not_observed')
    return report


def markdown(report):
    lines = ['# Inventario MCP por módulo', '', report['environment'], '',
             '| Conector | Módulo | Versión | Estado | Dirección | Destino | Herramientas |',
             '|---|---|---|---|---|---|---|']
    for row in report['connectors']:
        lines.append(f"| {row['slug']} | {row['module']} | {row['version']} | {row['lifecycle']} | {row['endpoint']} | {row['replacement']} | {len(row['published_tools'])} |")
    lines += ['', '| Conector / herramienta | Decisión | Destino | Uso |', '|---|---|---|---|']
    for row in report['connectors']:
        for tool in row['tools']:
            lines.append(f"| {row['slug']} / {tool['name']} | {tool['decision']} | {tool['owner']} / {tool['replacement']} | {tool['usage']} |")
    return '\n'.join(lines) + '\n'


class Command(BaseCommand):
    help = 'Audita identidad, propiedad, duplicados y migración de MCP sin cambiar datos.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['json', 'md'], default='md')
        parser.add_argument('--usage', action='store_true', help='Consulta uso y consumidores de la base configurada.')
        parser.add_argument('--check', action='store_true')

    def handle(self, *args, **options):
        report = inventory(include_usage=options['usage'])
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) if options['format'] == 'json' else markdown(report))
        missing = [f"{row['slug']}/{tool['name']}" for row in report['connectors'] for tool in row['tools'] if not tool['replacement_registered']]
        if options['check'] and (report['problems'] or missing):
            raise CommandError('; '.join(report['problems'] + missing))
