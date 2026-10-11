"""Read-only data-integrity scan for the operator: rule ids, counts and record ids, nothing else.

It runs the same catalog the panel and the MCP connector run, without going
through MCP (so it leaves no ``McpRequestLog`` row), and it never writes: there
is no ``--apply``, no lock and no audit row. Its output carries no labels,
messages or evidence — only ``model:id`` references — so a report can be kept
or handed over without client data. Corrections stay with the reviewed tools:
the data-integrity skill, the panel and their previews.

``--output`` writes the JSON report to a new private file (0600). It refuses
paths inside the repository, ``STATIC_ROOT``, ``MEDIA_ROOT`` and the private
media root, so a report can never be served or committed by accident.
"""
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from content.services.data_integrity import catalog, engine, relation_inventory
from content.services.data_integrity.scope import resolve_scope
from content.services.data_integrity.types import DOMAINS

RECORDS_PER_RULE = 50


def _forbidden_roots():
    roots = [Path(settings.BASE_DIR).resolve().parent]  # the repository checkout
    for name in ('STATIC_ROOT', 'MEDIA_ROOT', 'PRIVATE_MEDIA_ROOT'):
        value = getattr(settings, name, None)
        if value:
            roots.append(Path(value).resolve())
    return roots


def private_target(raw):
    """The resolved output path, or ``CommandError`` when it could be served or committed."""
    path = Path(raw).expanduser().resolve()
    for root in _forbidden_roots():
        if path == root or root in path.parents:
            raise CommandError(f'--output must live outside {root}: the report would be served or committed.')
    return path


def build_report(*, domains=None, rule_ids=None):
    """Findings per rule as counts and ``model:id`` references, in catalog order."""
    rules = {}
    for item, finding in engine.scan(resolve_scope('all'), domains=domains or None, rule_ids=rule_ids or None):
        entry = rules.setdefault(item.id, {'rule_id': item.id, 'domain': item.domain, 'severity': item.severity,
                                           'count': 0, 'records': []})
        entry['count'] += 1
        for subject in finding.subjects:
            reference = f'{subject.model}:{subject.pk}'
            if reference not in entry['records'] and len(entry['records']) < RECORDS_PER_RULE:
                entry['records'].append(reference)
    return {
        'catalog_version': catalog.CATALOG_VERSION,
        'generated_at': timezone.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': sum(entry['count'] for entry in rules.values()),
        'rules': list(rules.values()),
    }


def coverage_report():
    """The relation inventory: per anchor, how many relations are covered, exempt or a known gap."""
    return {
        'anchors': relation_inventory.summary(),
        'gaps': {key: relation_inventory.decision_for(key).reason
                 for key in sorted(relation_inventory.discover())
                 if relation_inventory.decision_for(key).status == relation_inventory.GAP},
    }


class Command(BaseCommand):
    help = ('Read-only data-integrity scan. Prints findings per rule as counts and record ids, never client '
            'data, and never writes to the database.')

    def add_arguments(self, parser):
        parser.add_argument('--domain', action='append', choices=DOMAINS, default=[],
                            help='Only rules of this domain (repeatable).')
        parser.add_argument('--rule', action='append', default=[], help='Only this rule id (repeatable).')
        parser.add_argument('--format', choices=('text', 'json'), default='text')
        parser.add_argument('--output', help='New private file (0600) for the JSON report, outside repo/static/media.')
        parser.add_argument('--coverage', action='store_true',
                            help='Add the relation inventory: covered, exempt and known gaps per anchor.')

    def handle(self, *args, **options):
        unknown = sorted(set(options['rule']) - {item.id for item in catalog.rules()})
        if unknown:
            raise CommandError(f'Unknown rule ids: {", ".join(unknown)}')
        target = private_target(options['output']) if options['output'] else None
        report = build_report(domains=options['domain'], rule_ids=options['rule'])
        if options['coverage']:
            report['coverage'] = coverage_report()
        if target is not None:
            self._write_private(target, report)
        if options['format'] == 'json':
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            self._write_text(report)

    def _write_private(self, target, report):
        try:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise CommandError(f'{target} already exists: choose a new file.')
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        self.stderr.write(f'Report written to {target} (0600).')

    def _write_text(self, report):
        self.stdout.write(f'Catalog {report["catalog_version"]} · {report["count"]} findings · {report["generated_at"]}')
        for entry in report['rules']:
            shown = ' '.join(entry['records'])
            self.stdout.write(f'{entry["rule_id"]:<5} {entry["severity"]:<6} {entry["domain"]:<14} '
                              f'{entry["count"]:>5}  {shown}')
        coverage = report.get('coverage')
        if coverage:
            self.stdout.write('Relation inventory (covered / exempt / gap):')
            for anchor, counts in coverage['anchors'].items():
                self.stdout.write(f'  {anchor:<28} {counts.get("covered", 0):>4} {counts.get("exempt", 0):>4} '
                                  f'{counts.get("gap", 0):>4}')
            for key, reason in coverage['gaps'].items():
                self.stdout.write(f'  gap {key}: {reason}')
