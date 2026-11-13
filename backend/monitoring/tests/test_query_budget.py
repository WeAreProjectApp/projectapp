"""Query and bounded-retention contracts for the monitoring module."""

from datetime import date, datetime, time, timedelta

import pytest
from accounts.models import UserProfile
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from monitoring.models import Case, CaseActivity, Report, Resource, Source

# The existing ceiling includes the mandatory access-revocation profile read.
MAX_CASE_LIST_QUERIES = 6


def _table_selects(queries, model):
    """Return SELECT queries that read the requested model table."""
    table = model._meta.db_table
    return [
        query['sql']
        for query in queries
        if query['sql'].lstrip().upper().startswith('SELECT')
        and table in query['sql']
    ]


def _endpoint(model):
    """Return the list route and timestamp field for one monitoring model."""
    if model is Case:
        return '/api/monitoring/cases/', 'last_seen_at'
    return '/api/monitoring/reports/', 'observed_at'


def _monitored_row(model, source, timestamp, number):
    """Persist one deterministic row at the requested timestamp."""
    if model is Case:
        return Case.objects.create(
            source=source,
            fingerprint=f'date-range:{number}',
            fingerprint_hash=f'{number:064x}',
            title=f'Caso de fecha {number}',
            severity=Case.SEVERITIES[0][0],
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            evidence={},
            detections=1,
        )
    return Report.objects.create(
        source=source,
        title=f'Informe de fecha {number}',
        observed_at=timestamp,
        text='Resultado de monitoreo.',
    )


def _active_day_rows(model, source, active_day, timezone_value, start):
    """Persist 23 midday rows and the last representable moment of one local day."""
    midday = timezone.make_aware(
        datetime.combine(active_day, time(hour=12)), timezone_value,
    )
    final_moment = timezone.make_aware(
        datetime.combine(active_day, time.max), timezone_value,
    )
    rows = [
        _monitored_row(model, source, midday, start + number)
        for number in range(23)
    ]
    rows.append(_monitored_row(model, source, final_moment, start + 23))
    return rows


def _list_select_sql(queries, model):
    """Return the non-count list query for the requested model."""
    return next(
        query['sql'] for query in queries
        if model._meta.db_table in query['sql']
        and 'SELECT' in query['sql']
        and 'COUNT(' not in query['sql']
    )


@pytest.fixture
def staff_client(db):
    """Return a staff session permitted to read monitoring administration lists."""
    user = get_user_model().objects.create_user(username='monitoring-query-staff', is_staff=True)
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN,
        is_onboarded=True,
    )
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def monitored_source(db):
    """Return a project monitoring source with its required resource hierarchy."""
    server = Resource.objects.create(key='srv1681495', name='VPS de producción', kind='server')
    resource = Resource.objects.create(key='projectapp', name='ProjectApp', kind='project', server=server)
    return Source.objects.create(resource=resource, key='silk', name='Silk')


@pytest.fixture
def twenty_six_cases(db):
    """Persist more cases than one administration list page can return."""
    now = timezone.now()
    server = Resource.objects.create(key='srv1681495', name='VPS de producción', kind='server')
    cases = []
    for number in range(26):
        resource = Resource.objects.create(
            key=f'project-{number}', name=f'Proyecto {number}', kind='project', server=server,
        )
        source = Source.objects.create(resource=resource, key='integrity', name='Integridad')
        cases.append(Case(
            source=source,
            fingerprint=f'backup:{number}',
            fingerprint_hash=f'{number:064x}',
            title=f'Backup atrasado {number}',
            severity='warning',
            first_seen_at=now,
            last_seen_at=now,
            evidence={'message': 'detalle que no pertenece al listado'},
            detections=1,
        ))
    return Case.objects.bulk_create(cases)


@pytest.mark.django_db
def test_case_list_limits_results_to_page_size(staff_client, twenty_six_cases):
    """Falla si el listado devuelve más de la página administrativa de 25 casos."""
    response = staff_client.get('/api/monitoring/cases/')

    assert response.status_code == 200
    assert response.json()['count'] == 26
    assert len(response.json()['results']) == 25


@pytest.mark.django_db
def test_case_list_query_budget_is_stable_for_single_source(
    staff_client,
    twenty_six_cases,
    record_property,
):
    """Falla si filtrar un origen reduce el número de filas pero aumenta las consultas."""
    with CaptureQueriesContext(connection) as full_queries:
        staff_client.get('/api/monitoring/cases/')
    with CaptureQueriesContext(connection) as filtered_queries:
        filtered_response = staff_client.get(f'/api/monitoring/cases/?source={twenty_six_cases[0].source_id}')

    record_property('query_count_full', len(full_queries))
    record_property('query_count_filtered', len(filtered_queries))
    assert filtered_response.json()['count'] == 1
    assert len(full_queries) == len(filtered_queries)
    assert len(full_queries) <= MAX_CASE_LIST_QUERIES
    assert len(_table_selects(full_queries, UserProfile)) == 1
    assert len(_table_selects(filtered_queries, UserProfile)) == 1


@pytest.mark.django_db
def test_case_list_defers_evidence_from_select(staff_client, twenty_six_cases):
    """Falla si el listado carga el JSON de evidencia reservado al detalle del caso."""
    with CaptureQueriesContext(connection) as queries:
        staff_client.get('/api/monitoring/cases/')

    case_select = next(
        query['sql'] for query in queries
        if 'monitoring_case' in query['sql'] and 'SELECT' in query['sql'] and 'COUNT(' not in query['sql']
    )

    assert '"evidence"' not in case_select


@pytest.mark.django_db
@freeze_time('2024-03-01T12:00:00Z')
def test_report_list_defers_large_report_text(staff_client, monitored_source):
    """Falla si el listado carga o expone el texto completo de los informes técnicos."""
    Report.objects.create(
        source=monitored_source,
        title='Informe de consultas lentas',
        observed_at=timezone.now(),
        text='x' * 50_000,
    )

    with CaptureQueriesContext(connection) as queries:
        response = staff_client.get('/api/monitoring/reports/')

    report_select = next(
        query['sql'] for query in queries
        if 'monitoring_report' in query['sql'] and 'SELECT' in query['sql'] and 'COUNT(' not in query['sql']
    )
    assert response.status_code == 200
    assert response.json()['results'][0]['title'] == 'Informe de consultas lentas'
    assert 'text' not in response.json()['results'][0]
    assert '"text"' not in report_select


@pytest.mark.django_db
def test_monitoring_history_indexes_cover_list_prefixes():
    """Falla si una migración pierde los índices que sostienen los listados ordenados."""
    with connection.cursor() as cursor:
        case_constraints = connection.introspection.get_constraints(cursor, Case._meta.db_table)
        activity_constraints = connection.introspection.get_constraints(cursor, CaseActivity._meta.db_table)

    case_indexes = {tuple(value['columns']) for value in case_constraints.values() if value['index']}
    activity_indexes = {tuple(value['columns']) for value in activity_constraints.values() if value['index']}
    assert {('state', 'last_seen_at'), ('severity', 'last_seen_at'), ('last_seen_at', 'id')} <= case_indexes
    assert ('case_id', 'created_at') in activity_indexes


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
def test_monitoring_range_respects_the_active_timezone_day(staff_client, monitored_source, model):
    """Falla si el rango indexable omite el final del día activo o incluye el siguiente."""
    active_day = date(2024, 2, 15)
    endpoint, _ = _endpoint(model)

    with timezone.override('America/Bogota'):
        timezone_value = timezone.get_current_timezone()
        first_moment = timezone.make_aware(
            datetime.combine(active_day, time.min), timezone_value,
        )
        first_row = _monitored_row(model, monitored_source, first_moment, 100)

        with CaptureQueriesContext(connection) as one_row_queries:
            first_response = staff_client.get(
                endpoint, {'since': active_day.isoformat(), 'until': active_day.isoformat()},
            )

        matching_rows = _active_day_rows(model, monitored_source, active_day, timezone_value, 101)
        next_day = timezone.make_aware(
            datetime.combine(active_day + timedelta(days=1), time.min), timezone_value,
        )
        _monitored_row(model, monitored_source, next_day, 125)

        with CaptureQueriesContext(connection) as twenty_five_row_queries:
            response = staff_client.get(
                endpoint, {'since': active_day.isoformat(), 'until': active_day.isoformat()},
            )

    first_body = first_response.json()
    body = response.json()
    returned_ids = {row['id'] for row in body['results']}
    expected_ids = {first_row.id, *(row.id for row in matching_rows)}

    assert first_response.status_code == 200
    assert first_body['count'] == 1
    assert response.status_code == 200
    assert body['count'] == 25
    assert returned_ids == expected_ids
    assert len(one_row_queries) == len(twenty_five_row_queries)
    assert len(twenty_five_row_queries) <= MAX_CASE_LIST_QUERIES


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
def test_monitoring_range_uses_raw_timestamp_comparisons(staff_client, monitored_source, model):
    """Falla si un rango ordinario vuelve a transformar la columna de fecha indexada."""
    active_day = date(2024, 2, 15)
    endpoint, date_field = _endpoint(model)

    with timezone.override('America/Bogota'):
        timezone_value = timezone.get_current_timezone()
        boundary = timezone.make_aware(
            datetime.combine(active_day, time.min), timezone_value,
        )
        _monitored_row(model, monitored_source, boundary, 150)
        with CaptureQueriesContext(connection) as queries:
            response = staff_client.get(
                endpoint, {'since': active_day.isoformat(), 'until': active_day.isoformat()},
            )

    list_select = _list_select_sql(queries, model).lower()

    assert response.status_code == 200
    assert date_field in list_select
    assert 'django_datetime_cast_date' not in list_select
    assert 'date(' not in list_select


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
@pytest.mark.parametrize(
    ('parameter', 'expected_numbers'),
    [('since', {201, 202}), ('until', {200, 201})],
)
def test_monitoring_single_date_filter_keeps_its_inclusive_boundary(
    staff_client, monitored_source, model, parameter, expected_numbers,
):
    """Falla si un límite de fecha independiente deja fuera su propia medianoche."""
    active_day = date(2024, 2, 15)
    endpoint, _ = _endpoint(model)

    with timezone.override('America/Bogota'):
        timezone_value = timezone.get_current_timezone()
        previous_row = _monitored_row(
            model,
            monitored_source,
            timezone.make_aware(datetime.combine(active_day - timedelta(days=1), time.max), timezone_value),
            200,
        )
        boundary_row = _monitored_row(
            model,
            monitored_source,
            timezone.make_aware(datetime.combine(active_day, time.min), timezone_value),
            201,
        )
        later_row = _monitored_row(
            model,
            monitored_source,
            timezone.make_aware(datetime.combine(active_day + timedelta(days=1), time.min), timezone_value),
            202,
        )
        response = staff_client.get(endpoint, {parameter: active_day.isoformat()})

    row_ids = {previous_row.id: 200, boundary_row.id: 201, later_row.id: 202}
    returned_numbers = {row_ids[row['id']] for row in response.json()['results']}

    assert response.status_code == 200
    assert returned_numbers == expected_numbers


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
def test_monitoring_inverted_dates_return_validation_error(staff_client, monitored_source, model):
    """Falla si una consulta acepta un rango cuyo final es anterior al inicio."""
    endpoint, _ = _endpoint(model)
    active_day = date(2024, 2, 15)

    with timezone.override('America/Bogota'):
        timezone_value = timezone.get_current_timezone()
        _monitored_row(
            model,
            monitored_source,
            timezone.make_aware(datetime.combine(active_day, time.min), timezone_value),
            300,
        )
        response = staff_client.get(
            endpoint,
            {'since': (active_day + timedelta(days=1)).isoformat(), 'until': active_day.isoformat()},
        )

    assert response.status_code == 400
    assert 'until' in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize('model', [Case, Report])
@pytest.mark.parametrize(
    ('parameter', 'boundary_day'),
    [('since', date.min), ('until', date.max)],
)
def test_monitoring_extreme_date_filter_keeps_its_boundary_row(
    staff_client, monitored_source, model, parameter, boundary_day,
):
    """Falla si un límite DateField extremo desborda o pierde su registro representable."""
    endpoint, _ = _endpoint(model)

    with timezone.override('UTC'):
        boundary = timezone.make_aware(
            datetime.combine(boundary_day, time.min), timezone.get_current_timezone(),
        )
        row = _monitored_row(model, monitored_source, boundary, 400 if parameter == 'since' else 401)
        response = staff_client.get(endpoint, {parameter: boundary_day.isoformat()})

    assert response.status_code == 200
    assert response.json()['count'] == 1
    assert response.json()['results'][0]['id'] == row.id
