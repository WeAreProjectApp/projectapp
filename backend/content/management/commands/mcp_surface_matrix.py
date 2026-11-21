"""Inventory product surfaces and served domain tools without business reads."""
import csv
import io
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from content.mcp.coverage import CoverageError, build_matrix, read_verified_report
from content.mcp.presentation import connector_name

CSV_COLUMNS = ['tipo_fila', 'superficie', 'modulo_vista', 'funcionalidad_accion', 'gestor', 'herramienta',
               'rol_permisos', 'resultado', 'evidencia_codigo', 'evidencia_funcional']


def csv_report(report):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(CSV_COLUMNS)
    for row in report['rows']:
        views = ' | '.join(row['view_ids']) if row['view_ids'] else 'Candidatas sin validar: ' + ' | '.join(row['candidate_view_ids'])
        writer.writerow(['operacion_mcp', ' | '.join(row['surface']), views, row['action'],
                         row['manager'], row['tool'], ' | '.join(row['permissions']), row['result'],
                         row['source'], ' | '.join(row['evidence'])])
    for surface in report['surfaces']:
        for feature in surface.get('feature_checks', []):
            writer.writerow(['funcion_de_vista', surface['surface'], surface['id'] + ' · ' + feature['id'],
                             feature['action'], connector_name(surface.get('connector')),
                             'Candidatas sin validar: ' + ' | '.join(feature['candidate_tools']),
                             surface['audience'], feature['result'], surface.get('file', ''),
                             ' | '.join(feature['evidence'])])
        if surface['result'] in {'exempt', 'gap'}:
            writer.writerow(['vista_exenta_o_sin_asignacion', surface['surface'], surface['id'], surface.get('reason', surface.get('description', '')),
                             surface.get('connector', ''), '', surface['audience'], surface['result'], surface.get('file', ''), ''])
    return stream.getvalue()


def verified_csv_report(report):
    """Export the views, tools and actors actually checked in this validated report."""
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([*CSV_COLUMNS, 'rol_probado', 'evidencia_permiso', 'evidencia_confirmacion'])
    by_id = {row['id']: row for row in report['rows']}
    surfaces = {view['id']: view['surface'] for view in report['surfaces']}

    def write_operation(kind, area, view, action, tool, source, evidence):
        writer.writerow([kind, area, view, action, tool['manager'], tool['tool'],
                         ' | '.join(tool['permissions']), tool['result'], source, ' | '.join(evidence),
                         tool['tested_role'], ' | '.join(tool['permission_evidence']),
                         ' | '.join(tool['confirmation_evidence']) if tool['requires_confirmation'] else ''])

    for tool in report['rows']:
        areas = sorted({surfaces[view_id] for view_id in tool['view_ids']})
        write_operation('operacion_mcp', ' | '.join(areas), ' | '.join(tool['view_ids']), tool['action'],
                        tool, tool['source'], tool['evidence'])
    for view in report['surfaces']:
        if view['result'] == 'exempt':
            writer.writerow(['vista_exenta_o_sin_asignacion', view['surface'], view['id'], view['reason'],
                             '', '', view['audience'], 'exempt', view['file'], '', '', '', ''])
            continue
        for feature in view['feature_checks']:
            for tool_id in feature['checks']:
                tool = by_id[tool_id]
                evidence = dict.fromkeys([*feature['evidence'], *tool['evidence'], *view['evidence']])
                write_operation('funcion_de_vista', view['surface'], view['id'] + ' · ' + feature['id'],
                                feature['action'], tool, view['file'], evidence)
    return stream.getvalue()


class Command(BaseCommand):
    help = 'Genera la matriz PA-221; un mapeo estático nunca acredita cobertura funcional.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['json', 'csv'], default='json')
        parser.add_argument('--output', type=Path)
        parser.add_argument('--verify', type=Path,
                            help='Valida el JSON funcional. Con --format csv exporta las comprobaciones acreditadas.')
        parser.add_argument('--check', action='store_true', help='Rechaza vistas sin gestor o excepción explícita.')

    def handle(self, *args, **options):
        verify = Path(options['verify']) if options['verify'] else None
        destination = Path(options['output']) if options['output'] else None
        try:
            if verify:
                report, _ = read_verified_report(verify)
                if destination and destination.exists() and verify.samefile(destination):
                    raise CommandError('Elige una salida distinta del reporte QA original.')
                if not destination and options['format'] == 'json':
                    self.stdout.write('Reporte de comprobaciones QA coherente con el corte; no autentica CI ni reemplaza la revisión humana. Consumidores y ventanas se comprueban por separado.')
                    return
            else:
                report = build_matrix()
        except (CoverageError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        if options['format'] == 'csv':
            output = verified_csv_report(report) if verify else csv_report(report)
        else:
            output = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if destination:
            destination.write_text(output, encoding='utf-8')
            self.stdout.write(json.dumps({'surfaces': len(report['surfaces']), 'tools': len(report['rows']),
                                         'states': dict(Counter(row['result'] for row in report['surfaces']))}))
        else:
            self.stdout.write(output)
        if options['check'] and any(surface['result'] == 'gap' for surface in report['surfaces']):
            raise CommandError('Hay vistas sin gestor o excepción explícita; consulta la matriz.')
