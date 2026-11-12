import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from monitoring.models import Case, Credential, Resource, Source


@pytest.fixture
def dashboard(db):
    cache.clear()
    actor = get_user_model().objects.create_user(username='dashboard-operator', is_staff=True, is_superuser=True)
    client = APIClient()
    client.force_login(actor)
    server = Resource.objects.create(key='fixture-host', name='Servidor de pruebas', kind='server', environment='development')
    project = Resource.objects.create(key='fixture-project', name='Proyecto de pruebas', kind='project', server=server, environment='development')
    source = Source.objects.create(resource=project, key='demo', name='Fuente de pruebas', last_seen_at=timezone.now())
    telemetry = Source.objects.create(resource=server, key='telemetry', name='Mediciones', expected_interval=60)
    credential, _ = Credential.issue('Fixture only')
    credential.resources.add(server)
    yield {'client': client, 'actor': actor, 'server': server, 'project': project, 'source': source, 'telemetry': telemetry, 'credential': credential}
    cache.clear()


def create_cases(source, count=53):
    now = timezone.now()
    return Case.objects.bulk_create([Case(source=source, fingerprint=f'fixture-{index}', fingerprint_hash=f'{index:064x}', title=f'Caso {index}', severity='critical', state='resolved' if index % 2 else 'pending', condition='active', detections=100, first_seen_at=now, last_seen_at=now) for index in range(count)])


def measurement(dashboard, **changes):
    return {'schema_version': 1, 'external_id': 'fixture-measurement', 'server': dashboard['server'].key,
            'resource': dashboard['server'].key, 'source': 'telemetry', 'kind': 'metric', 'observed_at': timezone.now(),
            'metrics': {'cpu_percent': 25.0, 'cpu_count': 2, 'load_1m': 1.0, 'ram_total_bytes': 4096,
                        'ram_used_bytes': 2048, 'disk_total_bytes': 8192, 'disk_used_bytes': 4096, **changes}}
