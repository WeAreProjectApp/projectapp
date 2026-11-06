"""Deterministic local observations, without real ingestion credentials."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Project
from content.fake_data import add_seed_arguments, ensure_fake_data_allowed, seed_context
from monitoring.models import Case, CaseActivity, Report, Resource, Source


class Command(BaseCommand):
    help = 'Crear ejemplos reproducibles de monitoreo exclusivamente en desarrollo.'

    def add_arguments(self, parser):
        add_seed_arguments(parser, count_default=30)

    @transaction.atomic
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
                state = Case.STATES[index % len(Case.STATES)][0]
                case, created = Case.objects.get_or_create(
                    source=source, fingerprint_hash=context.uuid(f'case-{index}').hex.ljust(64, '0'),
                    defaults={
                        'fingerprint': f'demo-{index}', 'title': f'Ejemplo de observación {index + 1}',
                        'severity': Case.SEVERITIES[index % len(Case.SEVERITIES)][0], 'state': state,
                        'condition': 'recovered' if state == 'resolved' else 'active',
                        'first_seen_at': now - timedelta(days=3 + options['count'] // 24),
                        'last_seen_at': now - timedelta(hours=index),
                        'closed_at': now if state == 'resolved' else None, 'detections': index + 1,
                        'resource_snapshot': {'key': resource.key, 'environment': 'development'},
                        'evidence': {'metric': 'duration', 'value': context.rng.randrange(600, 900), 'unit': 'ms'},
                    },
                )
                if created:
                    activity = CaseActivity.objects.create(case=case, kind='note', actor_name='Demo',
                        text='Ejemplo ficticio para validar el seguimiento manual.')
                    CaseActivity.objects.filter(pk=activity.pk).update(created_at=now)
            Report.objects.get_or_create(source=source, title='Reporte de demostración', defaults={
                'observed_at': now, 'text': 'Reporte ficticio; sin incidentes ni sondas reales.',
                'resource_snapshot': {'key': resource.key, 'environment': 'development'},
            })
        self.stdout.write('Datos de monitoreo disponibles (sin credenciales de ingestión).')
