"""Report discovery parity and maintain the versioned MCP contract lock."""
import json
import os

import requests
from django.core.management.base import BaseCommand, CommandError

from content.mcp.connectors import CONNECTORS
from content.mcp.contract_report import (
    CONTRACTS_PATH,
    ContractReportError,
    backlog_literals,
    compare,
    fingerprint,
    local_snapshot,
    remote_snapshot,
    render_markdown,
)


class Command(BaseCommand):
    help = 'Compara los contratos MCP publicados y genera su huella de contrato.'

    def add_arguments(self, parser):
        parser.add_argument('--slug', action='append', choices=sorted(CONNECTORS))
        parser.add_argument('--format', choices=('md', 'json'), default='md')
        parser.add_argument('--remote', metavar='BASE_URL')
        parser.add_argument('--token-env-template', default='MCP_TOKEN_{SLUG}')
        parser.add_argument('--print-backlog', action='store_true')
        parser.add_argument('--write-fingerprints', action='store_true')

    def handle(self, *args, **options):
        slugs = sorted(set(options['slug'] or CONNECTORS))
        if options['remote'] and (options['print_backlog'] or options['write_fingerprints']):
            raise CommandError('--print-backlog y --write-fingerprints requieren el modo local.')
        if options['print_backlog']:
            self.stdout.write(backlog_literals())
            return
        try:
            if options['remote']:
                tokens = self._remote_tokens(slugs, options['token_env_template'])
                with requests.Session() as session:
                    snapshots = [remote_snapshot(options['remote'], slug, tokens[slug], session=session) for slug in slugs]
            else:
                snapshots = [local_snapshot(slug) for slug in slugs]
            results = [compare(snapshot) for snapshot in snapshots]
        except ContractReportError as exc:
            raise CommandError(str(exc), returncode=1) from None
        report = json.dumps(results, ensure_ascii=False, sort_keys=True, indent=2) if options['format'] == 'json' else render_markdown(results)
        self.stdout.write(report)
        failed = [result['slug'] for result in results if not result['ok']]
        if failed:
            raise CommandError('Contratos MCP distintos: ' + ', '.join(failed), returncode=1)
        if options['write_fingerprints']:
            self._write_fingerprints(slugs)

    def _remote_tokens(self, slugs, template):
        try:
            env_names = {slug: template.format(SLUG=slug.upper().replace('-', '_')) for slug in slugs}
        except (KeyError, ValueError):
            raise CommandError('Plantilla de tokens inválida; usa {SLUG}.') from None
        missing = [name for name in env_names.values() if not os.environ.get(name)]
        if missing:
            raise CommandError('Faltan variables de entorno: ' + ', '.join(missing))
        return {slug: os.environ[name] for slug, name in env_names.items()}

    def _write_fingerprints(self, slugs):
        try:
            existing = json.loads(CONTRACTS_PATH.read_text()) if CONTRACTS_PATH.exists() else {}
        except (OSError, ValueError):
            raise CommandError('No se pudo leer el archivo de huellas MCP.') from None
        if not isinstance(existing, dict) or any(not isinstance(entry, dict) for entry in existing.values()):
            raise CommandError('El archivo de huellas MCP tiene un formato inválido.')
        entries = {slug: {'version': CONNECTORS[slug].version, 'sha256': fingerprint(slug)} for slug in slugs}
        unchanged_version = [
            slug for slug, entry in entries.items()
            if slug in existing and existing[slug].get('sha256') != entry['sha256']
            and existing[slug].get('version') == entry['version']
        ]
        if unchanged_version:
            raise CommandError('La huella cambió sin incrementar la versión: ' + ', '.join(unchanged_version), returncode=1)
        try:
            CONTRACTS_PATH.write_text(json.dumps({**existing, **entries}, sort_keys=True, indent=2) + '\n')
        except OSError:
            raise CommandError('No se pudo escribir el archivo de huellas MCP.') from None
