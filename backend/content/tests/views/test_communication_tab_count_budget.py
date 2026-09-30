"""Query budget contract for communication tab counts."""

from datetime import UTC, datetime

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from content.models import (
    CommunicationFolder,
    CommunicationMessage,
    CommunicationThread,
)

pytestmark = pytest.mark.django_db

MAX_COMMUNICATION_TAB_COUNT_QUERIES = 6
OCCURRED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def _tab_client(user):
    client = APIClient()
    client.force_login(user)
    return client


def _communication_fixture(actor):
    user = get_user_model().objects.create_user(
        username="tab-count-client",
        email="tab-count-client@example.com",
        password="testpass123",
    )
    client = UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
    folder = CommunicationFolder.objects.create(name="Query folder", client=client)
    correlated = CommunicationThread.objects.create(
        client=client,
        folder=folder,
        title="Correlated messages",
        created_by=actor,
        updated_by=actor,
    )
    unmatched = CommunicationThread.objects.create(
        client=client,
        title="Unanswered message",
        created_by=actor,
        updated_by=actor,
    )
    archived = CommunicationThread.objects.create(
        client=client,
        folder=folder,
        title="Archived thread",
        is_archived=True,
        created_by=actor,
        updated_by=actor,
    )
    outgoing = CommunicationMessage.objects.create(
        thread=correlated,
        channel=CommunicationMessage.Channel.WHATSAPP,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=CommunicationMessage.Status.SENT,
        content="Needle message",
        occurred_at=OCCURRED_AT,
    )
    CommunicationMessage.objects.create(
        thread=correlated,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.INCOMING,
        status=CommunicationMessage.Status.RECEIVED,
        content="Needle reply",
        occurred_at=OCCURRED_AT,
        reply_to=outgoing,
    )
    CommunicationMessage.objects.create(
        thread=unmatched,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=CommunicationMessage.Status.SENT,
        content="Unanswered email",
        occurred_at=OCCURRED_AT,
    )
    CommunicationMessage.objects.create(
        thread=archived,
        channel=CommunicationMessage.Channel.WHATSAPP,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=CommunicationMessage.Status.DRAFT,
        content="Archived message",
        occurred_at=OCCURRED_AT,
    )
    return folder, correlated, unmatched


def _tab_specs(folder, correlated, unmatched):
    return [
        {"id": "visible", "filters": {}},
        {
            "id": "correlated-impossible",
            "filters": {
                "channel": ["whatsapp"],
                "direction": ["incoming"],
            },
        },
        {"id": "answered", "filters": {"reply_status": ["answered"]}},
        {"id": "unanswered", "filters": {"reply_status": ["unanswered"]}},
        {"id": "needle", "filters": {"q": "Needle"}},
        {"id": "thread-id", "filters": {"q": str(unmatched.pk)}},
        {"id": "folder", "filters": {"folder": [str(folder.pk)]}},
        {"id": "archived", "filters": {"scope": "archived"}},
        {
            "id": "email-outgoing",
            "filters": {
                "channel": ["email"],
                "direction": ["outgoing"],
            },
        },
        {"id": "open", "filters": {"status": ["open"]}},
        {"id": "all-scope", "filters": {"scope": "all"}},
        {"id": "reply-text", "filters": {"q": "reply"}},
        {"id": "duplicate", "filters": {}},
        {"id": "duplicate", "filters": {"q": str(unmatched.pk)}},
        {"id": "visible-copy-01", "filters": {}},
        {"id": "visible-copy-02", "filters": {}},
        {"id": "visible-copy-03", "filters": {}},
        {"id": "visible-copy-04", "filters": {}},
        {"id": "visible-copy-05", "filters": {}},
        {"id": "visible-copy-06", "filters": {}},
        {"id": "visible-copy-07", "filters": {}},
        {"id": "visible-copy-08", "filters": {}},
        {"id": "visible-copy-09", "filters": {}},
        {"id": "visible-copy-10", "filters": {}},
    ]


def _tab_count_response(client, tabs):
    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            reverse("communication-thread-tab-counts"),
            {"tabs": tabs},
            format="json",
        )
    return response, len(queries)


def test_tab_counts_query_budget_does_not_grow_from_one_tab_to_twenty_four(
    record_property,
):
    """Falla si cada pestaña vuelve a ejecutar un Count independiente."""
    superuser = get_user_model().objects.create_superuser(
        username="tab-budget-admin",
        email="tab-budget-admin@example.com",
        password="testpass123",
    )
    folder, correlated, unmatched = _communication_fixture(superuser)
    client = _tab_client(superuser)
    one_tab_response, one_tab_queries = _tab_count_response(
        client,
        [{"id": "visible", "filters": {}}],
    )
    response, many_tab_queries = _tab_count_response(
        client,
        _tab_specs(folder, correlated, unmatched),
    )

    record_property("communication_tab_queries_one", one_tab_queries)
    record_property("communication_tab_queries_twenty_four", many_tab_queries)
    assert one_tab_response.status_code == 200
    assert response.status_code == 200
    assert one_tab_queries == many_tab_queries
    assert many_tab_queries <= MAX_COMMUNICATION_TAB_COUNT_QUERIES


def test_tab_counts_preserve_correlated_filter_results():
    """Falla si una pestaña separa filtros que deben coincidir en el mismo mensaje."""
    superuser = get_user_model().objects.create_superuser(
        username="tab-contract-admin",
        email="tab-contract-admin@example.com",
        password="testpass123",
    )
    folder, correlated, unmatched = _communication_fixture(superuser)
    response = _tab_client(superuser).post(
        reverse("communication-thread-tab-counts"),
        {"tabs": _tab_specs(folder, correlated, unmatched)},
        format="json",
    )

    assert response.status_code == 200
    assert response.data == {
        "counts": {
            "visible": 2,
            "correlated-impossible": 0,
            "answered": 1,
            "unanswered": 1,
            "needle": 1,
            "thread-id": 1,
            "folder": 1,
            "archived": 1,
            "email-outgoing": 1,
            "open": 2,
            "all-scope": 3,
            "reply-text": 1,
            "duplicate": 1,
            "visible-copy-01": 2,
            "visible-copy-02": 2,
            "visible-copy-03": 2,
            "visible-copy-04": 2,
            "visible-copy-05": 2,
            "visible-copy-06": 2,
            "visible-copy-07": 2,
            "visible-copy-08": 2,
            "visible-copy-09": 2,
            "visible-copy-10": 2,
        }
    }


def test_empty_tab_counts_skip_the_communication_aggregate_query():
    """Falla si una solicitud vacía consulta conteos de hilos innecesariamente."""
    superuser = get_user_model().objects.create_superuser(
        username="empty-tab-budget-admin",
        email="empty-tab-budget-admin@example.com",
        password="testpass123",
    )

    client = _tab_client(superuser)
    with CaptureQueriesContext(connection) as queries:
        response = client.post(
            reverse("communication-thread-tab-counts"),
            {"tabs": []},
            format="json",
        )

    assert response.status_code == 200
    assert response.data == {"counts": {}}
    assert CommunicationThread._meta.db_table not in " ".join(
        query["sql"] for query in queries
    ).lower()
