"""Deterministic local observations, without real ingestion credentials."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Project
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from content.fake_data_files import fake_data_transaction
from monitoring.models import CapacityAllocation, Case, CaseActivity, Delivery, Report, Resource, Source, TelemetrySample


class Command(BaseCommand):
    help = 'Crear ejemplos reproducibles de monitoreo exclusivamente en desarrollo.'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=75)

    @fake_data_transaction()
    def handle(self, *args, **options):
        ensure_fake_data_allowed('create_fake_monitoring')
        if options['count'] < 1:
            raise CommandError('--count must be greater than zero.')
        context = seed_context(options, 'monitoring')
        now = context.anchor_now
        server, _ = Resource.objects.get_or_create(key='demo-server', defaults={
            'name': 'Servidor de demostración', 'kind': 'server', 'environment': 'development',
        })
        project, _ = Resource.objects.get_or_create(key='demo-project', defaults={
            'name': 'Proyecto de demostración', 'kind': 'project', 'server': server,
            'environment': 'development', 'project': Project.objects.order_by('pk').first(),
        })
        for resource in (server, project):
            source, _ = Source.objects.get_or_create(resource=resource, key='demo', defaults={
                'name': 'Monitor de demostración', 'last_seen_at': now,
            })
            for index in range(options['count']):
                state = Case.STATES[(index // 3 + index) % len(Case.STATES)][0]
                case, created = Case.objects.get_or_create(
                    source=source, fingerprint_hash=context.uuid(f'case-{index}').hex.ljust(64, '0'),
                    defaults={
                        'fingerprint': f'demo-{index}', 'title': f'Ejemplo de observación {index + 1}',
                        'severity': Case.SEVERITIES[index % len(Case.SEVERITIES)][0], 'state': state,
                        'condition': 'recovered' if state == 'resolved' or index % 4 == 0 else 'active',
                        'first_seen_at': now - timedelta(days=3 + options['count'] // 24),
                        'last_seen_at': now - timedelta(hours=index),
                        'closed_at': now if state == 'resolved' else None, 'detections': index + 1,
                        'resource_snapshot': {'key': resource.key, 'environment': 'development'},
                        'summary': 'Observación ficticia para validar prioridades y seguimiento.',
                        'evidence': {} if index % 5 == 0 else {'metric': 'duration', 'value': 0 if index % 7 == 0 else context.rng.randrange(600, 900), 'unit': 'ms', 'message': ('Observación extensa. ' * 100) if index % 6 == 0 else 'Ejemplo ficticio', 'result': False, 'path': ''},
                    },
                )
                if created:
                    activity = CaseActivity.objects.create(case=case, kind='note', actor_name='Demo',
                        text='Ejemplo ficticio para validar el seguimiento manual.')
                    CaseActivity.objects.filter(pk=activity.pk).update(created_at=now)
                if index == 0:
                    for history_index in range(max(55, options['count'])):
                        observed = now - timedelta(minutes=history_index)
                        activity, activity_created = CaseActivity.objects.get_or_create(case=case, kind='note', actor_name='Demo', text=f'Observación de prueba {history_index + 1}')
                        if activity_created:
                            CaseActivity.objects.filter(pk=activity.pk).update(created_at=observed)
                        Delivery.objects.get_or_create(source=source, external_id=f'fake-history-{history_index}', defaults={'digest': context.uuid(f'delivery-{history_index}').hex.ljust(64, '0'), 'kind': 'detection', 'observed_at': observed, 'case': case, 'evidence': {'count': history_index}})
            Report.objects.get_or_create(source=source, title='Reporte de demostración', defaults={
                'observed_at': now, 'text': 'Reporte ficticio; sin incidentes ni sondas reales.',
                'resource_snapshot': {'key': resource.key, 'environment': 'development'},
            })
            for report_index in range(options['count']):
                Report.objects.get_or_create(source=source, title=f'Reporte ficticio {report_index + 1}', defaults={'observed_at': now - timedelta(hours=report_index), 'text': 'Reporte informativo ficticio.\n' * (100 if report_index == 0 else 2), 'resource_snapshot': {'key': resource.key, 'environment': 'development'}})
        for key, defaults in {
            'demo-no-data': {'last_seen_at': None},
            'demo-stale': {'last_seen_at': now - timedelta(hours=2)},
            'demo-disabled': {'enabled': False},
        }.items():
            Source.objects.get_or_create(resource=server, key=key, defaults={'name': key, **defaults})
        telemetry, _ = Source.objects.get_or_create(resource=server, key='telemetry', defaults={'name': 'Mediciones ficticias', 'last_seen_at': now, 'expected_interval': 60})
        for sample_index in range(180):
            if sample_index % 11 == 0:
                continue  # Deliberate missing intervals, never interpolated by the chart.
            observed = now - timedelta(minutes=sample_index)
            delivery, _ = Delivery.objects.get_or_create(source=telemetry, external_id=f'fake-sample-{sample_index}', defaults={'kind': 'metric', 'digest': context.uuid(f'sample-{sample_index}').hex.ljust(64, '0'), 'observed_at': observed})
            TelemetrySample.objects.get_or_create(delivery=delivery, defaults={'resource': server, 'observed_at': observed, 'cpu_percent': sample_index % 100, 'cpu_count': 2, 'load_1m': (sample_index % 9) / 2, 'ram_total_bytes': 4 * 1024**3, 'ram_used_bytes': (2000 + sample_index * 10) * 1024**2, 'disk_total_bytes': 80 * 1024**3, 'disk_used_bytes': 60 * 1024**3})
        CapacityAllocation.objects.get_or_create(resource=project, defaults={'cpu_mode': 'assigned', 'cpu_vcpu': '0.400', 'ram_mode': 'assigned', 'ram_bytes': 350 * 1024**2, 'storage_mode': 'shared'})
        self.stdout.write('Datos de monitoreo disponibles (sin credenciales de ingestión).')
