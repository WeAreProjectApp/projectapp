"""Inventory product surfaces and served domain tools without business reads."""
import csv
import io
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from content.mcp.coverage import CoverageError, build_matrix, load_verified_report
from content.mcp.presentation import connector_name


def csv_report(report):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['tipo_fila', 'superficie', 'modulo_vista', 'funcionalidad_accion', 'gestor', 'herramienta',
                     'rol_permisos', 'resultado', 'evidencia_codigo', 'evidencia_funcional'])
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


class Command(BaseCommand):
    help = 'Genera la matriz PA-221; un mapeo estático nunca acredita cobertura funcional.'

    def add_arguments(self, parser):
        parser.add_argument('--format', choices=['json', 'csv'], default='json')
        parser.add_argument('--output', type=Path)
        parser.add_argument('--verify', type=Path, help='Comprueba un reporte funcional sin escribir.')
        parser.add_argument('--check', action='store_true', help='Rechaza vistas sin gestor o excepción explícita.')

    def handle(self, *args, **options):
        try:
            report = build_matrix()
            if options['verify']:
                load_verified_report(options['verify'])
                self.stdout.write('Reporte de comprobaciones QA coherente con el corte; no autentica CI ni reemplaza la revisión humana. Consumidores y ventanas se comprueban por separado.')
                return
        except (CoverageError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        output = csv_report(report) if options['format'] == 'csv' else json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if options['output']:
            options['output'].write_text(output)
            self.stdout.write(json.dumps({'surfaces': len(report['surfaces']), 'tools': len(report['rows']),
                                         'states': dict(Counter(row['result'] for row in report['surfaces']))}))
        else:
            self.stdout.write(output)
        if options['check'] and any(surface['result'] == 'gap' for surface in report['surfaces']):
            raise CommandError('Hay vistas sin gestor o excepción explícita; consulta la matriz.')
