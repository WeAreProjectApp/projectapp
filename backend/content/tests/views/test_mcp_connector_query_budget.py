"""Panel MCP list query, hydration and payload contracts."""
import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models.signals import post_init
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from content.models import McpConnector, McpCredential, McpRequestLog
from content.views.mcp_blog import _connector_payload

pytestmark = pytest.mark.django_db
MAX_MCP_CONNECTOR_LIST_QUERIES = 6
PANEL_URL = '/api/mcp-connectors/'


@pytest.fixture(autouse=True)
def isolate_connector_catalog(db):
    """Keep data-migration connectors outside these explicit fixtures."""
    McpConnector.objects.all().delete()


def _panel_client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _create_connectors(total, *, identity_prefix='fixture', logs_per_connector=0):
    connectors = []
    for index in range(total):
        actor = get_user_model().objects.create(username=f'{identity_prefix}-connector-actor-{index:03d}', email=f'{identity_prefix}-connector-actor-{index:03d}@example.com')
        connector = McpConnector.objects.create(slug=f'query-connector-{index:03d}', name=f'Query connector {index:03d}', is_active=True)
        primary = McpCredential.objects.create(connector=connector, label='Primary', token_hash='a' * 64, token_prefix=f'p{index:03d}', actor=actor)
        McpCredential.objects.create(connector=connector, label='Backup', token_hash='b' * 64, token_prefix=f'b{index:03d}', actor=actor)
        McpRequestLog.objects.bulk_create([
            McpRequestLog(connector=connector, credential=primary, event='handshake', detail=f'event-{event_number}')
            for event_number in range(logs_per_connector)
        ])
        connectors.append(connector)
    return connectors


def _count_panel_queries(client):
    with CaptureQueriesContext(connection) as queries:
        response = client.get(PANEL_URL)
    return response, len(queries)


def test_connector_list_query_budget_does_not_grow_with_fifty_connectors(record_property):
    """Falla si el panel consulta logs, credenciales o actores por cada conector."""
    superuser = get_user_model().objects.create_superuser(username='connector-budget-admin', email='connector-budget@example.com', password='testpass123')
    _create_connectors(1, identity_prefix='single', logs_per_connector=11)
    single_response, single_queries = _count_panel_queries(_panel_client(superuser))
    McpConnector.objects.all().delete()
    _create_connectors(50, identity_prefix='many', logs_per_connector=11)
    many_response, many_queries = _count_panel_queries(_panel_client(superuser))

    record_property('mcp_connector_queries_one', single_queries)
    record_property('mcp_connector_queries_fifty', many_queries)
    assert single_response.status_code == 200
    assert many_response.status_code == 200
    assert len(single_response.data) == 1
    assert len(many_response.data) == 50
    assert single_queries == many_queries
    assert many_queries <= MAX_MCP_CONNECTOR_LIST_QUERIES


def test_connector_list_hydrates_exactly_ten_recent_logs_per_connector():
    """Falla si el prefetch vuelve a cargar el historial completo de cada conector."""
    superuser = get_user_model().objects.create_superuser(username='connector-hydration-admin', email='connector-hydration@example.com', password='testpass123')
    _create_connectors(2, logs_per_connector=11)
    initialized = []

    def remember_log(sender, instance, **kwargs):
        initialized.append(instance.pk)

    post_init.connect(remember_log, sender=McpRequestLog, weak=False)
    try:
        response = _panel_client(superuser).get(PANEL_URL)
    finally:
        post_init.disconnect(remember_log, sender=McpRequestLog)

    assert response.status_code == 200
    assert len(initialized) == 20
    assert [len(row['recent_events']) for row in response.data] == [10, 10]


def test_connector_list_payload_keeps_event_order_with_credential_actors():
    """Falla si el panel pierde orden de eventos, credenciales o sus actores."""
    superuser = get_user_model().objects.create_superuser(username='connector-payload-admin', email='connector-payload@example.com', password='testpass123')
    connector = _create_connectors(1, logs_per_connector=11)[0]
    expected_actor = connector.credentials.select_related('actor').get(label='Primary').actor.username

    response = _panel_client(superuser).get(PANEL_URL)
    payload = response.data[0]

    assert response.status_code == 200
    assert payload['slug'] == connector.slug
    assert [event['detail'] for event in payload['recent_events']] == ['event-10', 'event-9', 'event-8', 'event-7', 'event-6', 'event-5', 'event-4', 'event-3', 'event-2', 'event-1']
    assert [credential['token_prefix'] for credential in payload['credentials']] == ['p000', 'b000']
    assert [credential['actor'] for credential in payload['credentials']] == [expected_actor, expected_actor]


def test_connector_payload_uses_relations_when_prefetch_attributes_are_absent():
    """Falla si un caller individual sin prefetch deja de mostrar su actividad."""
    connector = _create_connectors(1, logs_per_connector=1)[0]

    payload = _connector_payload(McpConnector.objects.get(pk=connector.pk))

    assert payload['recent_events'][0]['detail'] == 'event-0'
    assert [credential['token_prefix'] for credential in payload['credentials']] == ['p000', 'b000']
