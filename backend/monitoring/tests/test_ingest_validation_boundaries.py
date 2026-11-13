"""Incomplete observations cannot enter monitoring with ambiguous meaning."""
import pytest

from monitoring.serializers import IngestSerializer


@pytest.mark.parametrize(('details', 'error_field'), [
    ({'kind': 'detection', 'title': 'Detectado'}, 'fingerprint'),
    ({'kind': 'detection', 'fingerprint': 'event-one'}, 'title'),
    ({'kind': 'report', 'title': 'Reporte'}, 'text'),
    ({'kind': 'heartbeat'}, 'enabled'),
    ({'kind': 'metric'}, 'metrics'),
    ({'kind': 'metric', 'metrics': {
        'cpu_percent': 20, 'cpu_count': 2, 'load_1m': 0.1,
        'ram_total_bytes': 1024, 'ram_used_bytes': 512,
        'disk_total_bytes': 2048, 'disk_used_bytes': 256,
        'unknown_metric': 1,
    }}, 'metrics'),
])
def test_ingest_rejects_invalid_observation(details, error_field):
    data = {'schema_version': 1, 'external_id': 'boundary-one', 'server': 'test-server',
            'resource': 'test-resource', 'source': 'test-source',
            'observed_at': '2026-01-01T00:00:00Z', **details}
    serializer = IngestSerializer(data=data)

    assert not serializer.is_valid()
    assert error_field in serializer.errors
