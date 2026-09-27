"""Query-budget contracts for report-linked monitoring observations."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from monitoring.models import Case, Credential, Delivery, Report, Resource, Source

MAX_OBSERVE_CASE_QUERIES = 1
INGEST_URL = "/api/monitoring/v1/ingest/"
SERVER_KEY = "srv1681495"


@pytest.fixture
def monitored_resource(db):
    """Create the monitored project resource accepted by the machine credential."""
    server = Resource.objects.create(
        key=SERVER_KEY, name="Budget server", kind="server"
    )
    return Resource.objects.create(
        key="projectapp", name="ProjectApp", kind="project", server=server
    )


@pytest.fixture
def monitored_source(monitored_resource):
    """Create the observation source used by each request."""
    return Source.objects.create(resource=monitored_resource, key="silk", name="Silk")


@pytest.fixture
def machine_client(monitored_resource):
    """Authenticate an API client with a credential scoped to the resource."""
    token = "monitoring-query-budget-token"
    credential = Credential.objects.create(
        label="query-budget collector",
        token_hash=Credential.hash_token(token),
    )
    credential.resources.add(monitored_resource)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def detection_payload():
    """Build valid observation payloads while allowing one contract variation."""

    def build(*, omit=(), **overrides):
        payload = {
            "schema_version": 1,
            "external_id": "silk:query-budget:1",
            "server": SERVER_KEY,
            "resource": "projectapp",
            "source": "silk",
            "observed_at": "2024-01-01T09:00:00Z",
            "kind": "detection",
            "fingerprint": "silk:query-budget",
            "title": "Query budget observation",
            "severity": "warning",
            "evidence": {"route": "/panel/"},
        }
        payload.update(overrides)
        for field in omit:
            payload.pop(field)
        return payload

    return build


def _selects_for_table(queries, model):
    table = model._meta.db_table.lower()
    return [
        query["sql"]
        for query in queries
        if query["sql"].lstrip().upper().startswith("SELECT")
        and table in query["sql"].lower()
    ]


@pytest.mark.django_db
def test_detection_with_own_report_reads_case_once_without_loading_report_text(
    machine_client,
    monitored_source,
    detection_payload,
    record_property,
):
    """Falla si enlazar un informe vuelve a leer el caso o hidrata el texto del informe."""
    report = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id="silk:report:detection-budget",
            kind="report",
            title="Informe de detección",
            text="x" * 50_000,
            omit=("fingerprint",),
        ),
        format="json",
    )

    with CaptureQueriesContext(connection) as queries:
        response = machine_client.post(
            INGEST_URL,
            detection_payload(
                external_id="silk:detection:budget",
                report_id="silk:report:detection-budget",
            ),
            format="json",
        )

    record_property("query_count_detection", len(queries))
    case = Case.objects.get(source=monitored_source)
    assert (
        response.status_code,
        response.json()["report_id"],
        response.json()["case_id"],
    ) == (
        201,
        report.json()["report_id"],
        case.pk,
    )
    assert case.condition == "active"
    assert (
        len(_selects_for_table(queries, Case)),
        _selects_for_table(queries, Report),
    ) == (
        MAX_OBSERVE_CASE_QUERIES,
        [],
    )


@pytest.mark.django_db
def test_recovery_with_own_report_reads_case_once_without_loading_report_text(
    machine_client,
    monitored_source,
    detection_payload,
    record_property,
):
    """Falla si recuperar un caso enlazado consulta dos veces el caso o carga el informe completo."""
    report = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id="silk:report:recovery-budget",
            kind="report",
            title="Informe de recuperación",
            text="x" * 50_000,
            omit=("fingerprint",),
        ),
        format="json",
    )
    original = machine_client.post(INGEST_URL, detection_payload(), format="json")

    with CaptureQueriesContext(connection) as queries:
        response = machine_client.post(
            INGEST_URL,
            detection_payload(
                external_id="silk:recovery:budget",
                kind="recovery",
                observed_at="2024-01-02T09:00:00Z",
                report_id="silk:report:recovery-budget",
                omit=("title",),
            ),
            format="json",
        )

    record_property("query_count_recovery", len(queries))
    case = Case.objects.get(source=monitored_source)
    assert (original.status_code, response.status_code) == (201, 201)
    assert (response.json()["report_id"], response.json()["case_id"]) == (
        report.json()["report_id"],
        case.pk,
    )
    assert case.condition == "recovered"
    assert (
        len(_selects_for_table(queries, Case)),
        _selects_for_table(queries, Report),
    ) == (
        MAX_OBSERVE_CASE_QUERIES,
        [],
    )


@pytest.mark.django_db
def test_orphan_recovery_creates_delivery_without_creating_case(
    machine_client,
    monitored_source,
    detection_payload,
):
    """Falla si una recuperación sin detección previa abre un caso inexistente."""
    response = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id="silk:recovery:orphan",
            kind="recovery",
            fingerprint="silk:orphan-query-budget",
            omit=("title",),
        ),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["case_id"] is None
    assert response.json()["report_id"] is None
    assert Delivery.objects.filter(source=monitored_source).count() == 1
    assert Case.objects.filter(source=monitored_source).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize("report_id", ["silk:report:missing", "silk:heartbeat:budget"])
def test_invalid_report_reference_rolls_back_detection_with_report_kind_filter(
    machine_client,
    monitored_source,
    detection_payload,
    report_id,
):
    """Falla si una referencia ausente o no informe deja una detección parcial."""
    heartbeat = machine_client.post(
        INGEST_URL,
        detection_payload(
            external_id="silk:heartbeat:budget",
            kind="heartbeat",
            enabled=True,
            omit=("fingerprint", "title"),
        ),
        format="json",
    )
    before_deliveries = Delivery.objects.filter(source=monitored_source).count()

    with CaptureQueriesContext(connection) as queries:
        response = machine_client.post(
            INGEST_URL,
            detection_payload(
                external_id=f"silk:detection:{report_id}", report_id=report_id
            ),
            format="json",
        )

    assert heartbeat.status_code == 201
    assert response.status_code == 404
    assert Delivery.objects.filter(source=monitored_source).count() == before_deliveries
    assert Case.objects.filter(source=monitored_source).count() == 0
    assert any(
        "monitoring_delivery" in query["sql"].lower()
        and "report" in query["sql"].lower()
        for query in queries
    )
