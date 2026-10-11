"""Contract tests for authenticated machine monitoring deliveries."""

import pytest
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from rest_framework.test import APIClient

from monitoring.models import Case, Credential, Delivery, Resource, Source
from monitoring.services import change_state


INGEST_URL = '/api/monitoring/v1/ingest/'
SERVER_KEY = 'srv1681495'
OBSERVED_AT = '2024-01-01T09:00:00Z'


@pytest.fixture
def monitored_resource(db):
    server = Resource.objects.create(key=SERVER_KEY, name='VPS de producción', kind='server')
    return Resource.objects.create(
        key='projectapp', name='ProjectApp', kind='project', server=server,
    )


@pytest.fixture
def monitored_source(monitored_resource):
    return Source.objects.create(resource=monitored_resource, key='silk', name='Silk')


@pytest.fixture
def machine_credential(monitored_resource):
    token = 'monitoring-machine-token'
    credential = Credential.objects.create(
        label='collector', token_hash=Credential.hash_token(token),
    )
    credential.resources.add(monitored_resource)
    return credential, token


@pytest.fixture
def machine_client(machine_credential):
    _, token = machine_credential
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def detection_payload():
    def build(*, omit=(), **overrides):
        payload = {
            'schema_version': 1,
            'external_id': 'silk:n-plus-one:1',
            'server': SERVER_KEY,
            'resource': 'projectapp',
            'source': 'silk',
            'observed_at': OBSERVED_AT,
            'kind': 'detection',
            'fingerprint': 'silk:n-plus-one:dashboard',
            'title': 'Consulta N+1 en panel',
            'severity': 'warning',
            'evidence': {'query_count': 18, 'route': '/panel/'},
        }
        payload.update(overrides)
        for field in omit:
            payload.pop(field)
        return payload

    return build


@pytest.mark.django_db
def test_same_detection_delivery_is_idempotent(machine_client, monitored_source, detection_payload):
    """Falla si un reintento crea otro caso o incrementa detecciones."""
    payload = detection_payload()

    first = machine_client.post(INGEST_URL, payload, format='json')
    duplicate = machine_client.post(INGEST_URL, payload, format='json')

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()['duplicate'] is True
    assert Delivery.objects.filter(source=monitored_source).count() == 1
    assert Case.objects.get(source=monitored_source).detections == 1


@pytest.mark.django_db
def test_reused_external_id_with_changed_content_returns_conflict(machine_client, monitored_source, detection_payload):
    """Falla si un productor puede reemplazar una entrega ya recibida."""
    first = machine_client.post(INGEST_URL, detection_payload(), format='json')
    conflict = machine_client.post(
        INGEST_URL, detection_payload(evidence={'query_count': 19, 'route': '/panel/'}), format='json',
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert Delivery.objects.filter(source=monitored_source).count() == 1


@pytest.mark.django_db
def test_credential_cannot_ingest_for_resource_outside_its_scope(machine_client, monitored_resource, detection_payload):
    """Falla si una credencial de proyecto puede escribir eventos de otro recurso."""
    other_resource = Resource.objects.create(
        key='mimittos-project', name='Mimittos', kind='project', server=monitored_resource.server,
    )
    other_source = Source.objects.create(resource=other_resource, key='silk', name='Silk')

    response = machine_client.post(
        INGEST_URL, detection_payload(resource=other_resource.key), format='json',
    )

    assert response.status_code == 403
    assert Delivery.objects.filter(source=other_source).count() == 0


@pytest.mark.django_db
def test_recovery_is_kept_when_an_older_detection_arrives_later(machine_client, monitored_source, detection_payload):
    """Falla si el orden de llegada revive una condición ya recuperada."""
    detected = machine_client.post(INGEST_URL, detection_payload(), format='json')
    recovered = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id='silk:n-plus-one:2', kind='recovery',
            observed_at='2024-01-02T09:00:00Z', omit=('title',),
        ),
        format='json',
    )
    delayed = machine_client.post(
        INGEST_URL,
        detection_payload(external_id='silk:n-plus-one:3', observed_at='2024-01-01T12:00:00Z'),
        format='json',
    )

    case = Case.objects.get(source=monitored_source)
    assert detected.status_code == 201
    assert recovered.status_code == 201
    assert delayed.status_code == 201
    assert case.state == 'pending'
    assert case.condition == 'recovered'
    assert case.last_seen_at == parse_datetime('2024-01-02T09:00:00Z')


@pytest.mark.django_db
def test_newer_detection_reopens_a_manually_resolved_case(machine_client, monitored_source, detection_payload):
    """Falla si una detección posterior no reabre un caso que ya se cerró."""
    machine_client.post(INGEST_URL, detection_payload(), format='json')
    case = Case.objects.get(source=monitored_source)
    actor = get_user_model().objects.create_user(username='monitoring-closer')
    change_state(case.pk, actor, {'state': 'resolved', 'version': case.version})
    case.refresh_from_db()
    case.closed_at = parse_datetime('2024-01-01T10:00:00Z')
    case.save(update_fields=['closed_at'])

    response = machine_client.post(
        INGEST_URL,
        detection_payload(external_id='silk:n-plus-one:2', observed_at='2024-01-01T11:00:00Z'),
        format='json',
    )

    case.refresh_from_db()
    assert response.status_code == 201
    assert case.state == 'pending'
    assert case.closed_at is None
    assert case.activities.get(kind='reopened').to_state == 'pending'


@pytest.mark.django_db
def test_older_detection_keeps_a_manually_resolved_case_closed(machine_client, monitored_source, detection_payload):
    """Falla si una observación anterior reabre un caso que fue cerrado después."""
    machine_client.post(INGEST_URL, detection_payload(), format='json')
    case = Case.objects.get(source=monitored_source)
    actor = get_user_model().objects.create_user(username='monitoring-closer')
    change_state(case.pk, actor, {'state': 'resolved', 'version': case.version})
    case.refresh_from_db()
    case.closed_at = parse_datetime('2024-01-02T09:00:00Z')
    case.save(update_fields=['closed_at'])

    response = machine_client.post(
        INGEST_URL,
        detection_payload(external_id='silk:n-plus-one:2', observed_at='2024-01-01T10:00:00Z'),
        format='json',
    )

    case.refresh_from_db()
    assert response.status_code == 201
    assert case.state == 'resolved'
    assert case.closed_at == parse_datetime('2024-01-02T09:00:00Z')


@pytest.mark.django_db
def test_report_creates_a_report_without_creating_case(machine_client, monitored_source, detection_payload):
    """Falla si un informe técnico se mezcla con un caso accionable."""
    response = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id='silk:weekly:1', kind='report',
            title='Reporte semanal de Silk', text='Dos consultas lentas.', omit=('fingerprint',),
        ),
        format='json',
    )

    assert response.status_code == 201
    assert response.json()['report_id'] is not None
    assert response.json()['case_id'] is None
    assert Delivery.objects.get(source=monitored_source).report.title == 'Reporte semanal de Silk'
    assert Case.objects.filter(source=monitored_source).count() == 0


@pytest.mark.django_db
def test_disabled_heartbeat_updates_source_without_creating_case(machine_client, monitored_source, detection_payload):
    """Falla si una pausa del origen se presenta como una alerta operativa."""
    response = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id='silk:heartbeat:1', kind='heartbeat', enabled=False,
            error='esperando reporte', omit=('fingerprint', 'title'),
        ),
        format='json',
    )

    monitored_source.refresh_from_db()
    assert response.status_code == 201
    assert monitored_source.enabled is False
    assert monitored_source.last_error == 'esperando reporte'
    assert monitored_source.health == 'disabled'
    assert Case.objects.filter(source=monitored_source).count() == 0


@pytest.mark.django_db
def test_revoked_machine_token_is_rejected_without_delivery(machine_client, machine_credential, monitored_source, detection_payload):
    """Falla si una credencial revocada aún puede insertar observaciones."""
    credential, _ = machine_credential
    credential.revoked_at = parse_datetime('2024-01-01T00:00:00Z')
    credential.save(update_fields=['revoked_at'])

    response = machine_client.post(INGEST_URL, detection_payload(), format='json')

    assert response.status_code == 401
    assert Delivery.objects.filter(source=monitored_source).count() == 0


@pytest.mark.django_db
def test_unknown_source_creates_no_delivery(machine_client, monitored_resource, detection_payload):
    """Falla si el receptor acepta un origen que no fue inventariado."""
    response = machine_client.post(INGEST_URL, detection_payload(source='unknown-source'), format='json')

    assert response.status_code == 404
    assert Delivery.objects.filter(source__resource=monitored_resource).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('payload_override', 'error_field'),
    [
        ({'evidence': {'authorization': 'secret'}}, 'evidence'),
        ({'unexpected': 'field'}, 'non_field_errors'),
    ],
)
def test_ingest_rejects_unapproved_or_unknown_payload_data(machine_client, monitored_source, detection_payload, payload_override, error_field):
    """Falla si la API deja ingresar secretos o campos sin contrato."""
    response = machine_client.post(INGEST_URL, detection_payload(**payload_override), format='json')

    assert response.status_code == 400
    assert error_field in response.json()
    assert Delivery.objects.filter(source=monitored_source).count() == 0


@pytest.mark.django_db
def test_heartbeats_share_one_receipt_per_source_and_hour(machine_client, monitored_source, detection_payload):
    """Falla si cada latido guarda su fila o si un latido sin fila propia responde sin el id entero que espera el colector."""
    def heartbeat(number, observed_at):
        return detection_payload(
            external_id=f'silk:heartbeat:{number}', kind='heartbeat', enabled=True,
            observed_at=observed_at, omit=('fingerprint', 'title'),
        )

    first = machine_client.post(INGEST_URL, heartbeat(1, '2024-01-01T09:05:00Z'), format='json')
    same_hour = machine_client.post(INGEST_URL, heartbeat(2, '2024-01-01T09:35:00Z'), format='json')
    next_hour = machine_client.post(INGEST_URL, heartbeat(3, '2024-01-01T10:05:00Z'), format='json')

    assert [first.status_code, same_hour.status_code, next_hour.status_code] == [201, 201, 201]
    assert type(same_hour.json()['id']) is int
    assert same_hour.json()['id'] == first.json()['id']
    assert next_hour.json()['id'] != first.json()['id']
    assert Delivery.objects.filter(source=monitored_source, kind='heartbeat').count() == 2


@pytest.mark.django_db
def test_heartbeat_retry_and_late_heartbeat_keep_the_latest_source_state(machine_client, monitored_source, detection_payload):
    """Falla si un reintento o un latido atrasado cambia el estado que dejó el latido más nuevo de la hora."""
    def heartbeat(name, observed_at, **fields):
        return detection_payload(
            external_id=f'silk:heartbeat:{name}', kind='heartbeat', observed_at=observed_at,
            omit=('fingerprint', 'title'), **fields,
        )

    latest = heartbeat('latest', '2024-01-01T09:40:00Z', enabled=True, error='')
    machine_client.post(INGEST_URL, heartbeat('earlier', '2024-01-01T09:05:00Z', enabled=True, error=''), format='json')
    machine_client.post(INGEST_URL, latest, format='json')
    monitored_source.refresh_from_db()
    delivered = (monitored_source.last_seen_at, monitored_source.last_received_at, monitored_source.enabled, monitored_source.last_error)
    retry = machine_client.post(INGEST_URL, latest, format='json')
    monitored_source.refresh_from_db()
    after_retry = (monitored_source.last_seen_at, monitored_source.last_received_at, monitored_source.enabled, monitored_source.last_error)
    delayed = machine_client.post(
        INGEST_URL, heartbeat('late', '2024-01-01T09:10:00Z', enabled=False, error='colector atrasado'), format='json',
    )
    retry_after_delay = machine_client.post(INGEST_URL, latest, format='json')
    monitored_source.refresh_from_db()

    assert (retry.status_code, retry.json()['duplicate']) == (200, True)
    assert after_retry == delivered
    assert delayed.status_code == 201
    assert delayed.json()['id'] == retry.json()['id']
    assert (retry_after_delay.status_code, retry_after_delay.json()['duplicate']) == (200, True)
    assert (monitored_source.last_seen_at, monitored_source.enabled, monitored_source.last_error) == (
        parse_datetime('2024-01-01T09:40:00Z'), True, '',
    )
