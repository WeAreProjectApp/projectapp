"""Read-volume contracts for requirement package catalog and request summaries."""
import pytest
from content.models import HourPackage, HourPackageSettings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import ChangeRequest
from accounts.models_requirement_packages import PackageRequest
from accounts.services import package_commerce as commerce

pytestmark = pytest.mark.django_db
pytest_plugins = ('accounts.tests.requirement_package_test_support',)

MAX_CATALOG_QUERIES = 6
LONG_REQUEST_DESCRIPTION = 'x' * 15000
REQUEST_SUMMARY_KEYS = frozenset({'id', 'ticket_id', 'project_id', 'project_name', 'title', 'status', 'version', 'created_at'})


def add_requirement_packages(context, count):
    """Insert additional active requirement packages without affecting the measured reads."""
    HourPackage.objects.bulk_create([
        HourPackage(
            nationality='COL',
            pricing_model='requirements',
            name_es=f'Paquete de lectura {index}',
            name_en=f'Read package {index}',
            xs_count=1,
            s_count=0,
            m_count=0,
            validity_months=12,
            discount_percent=0,
            order=index,
        )
        for index in range(count)
    ])


def add_package_requests(context, count):
    """Insert package requests whose descriptions model a large client payload."""
    tickets = ChangeRequest.objects.bulk_create([
        ChangeRequest(
            project=context.project,
            created_by=context.client,
            title=f'Solicitud extensa {index}',
            description=LONG_REQUEST_DESCRIPTION,
        )
        for index in range(count)
    ])
    return PackageRequest.objects.bulk_create([
        PackageRequest(project=context.project, client=context.client, ticket=ticket)
        for ticket in tickets
    ])


def response_key_sets(rows):
    """Return the distinct response field sets for summary-row contract assertions."""
    return {frozenset(row) for row in rows}


def test_requirement_catalog_query_budget_is_constant_from_one_to_twenty_packages(package_context):
    """Fails if quoting each extra requirement package restores a settings query per row."""
    HourPackageSettings.load()

    with CaptureQueriesContext(connection) as one_package_queries:
        one_package_catalog = commerce.catalog(package_context.project)

    add_requirement_packages(package_context, 19)
    with CaptureQueriesContext(connection) as twenty_package_queries:
        twenty_package_catalog = commerce.catalog(package_context.project)

    assert len(one_package_catalog) == 1
    assert len(twenty_package_catalog) == 20
    assert len(one_package_queries) == len(twenty_package_queries)
    assert len(twenty_package_queries) <= MAX_CATALOG_QUERIES


def test_request_list_omits_large_descriptions_while_detail_retains_description(package_context, api_client):
    """Fails if a package request list sends every large description or loses it from request detail."""
    add_package_requests(package_context, 20)
    detail_row = PackageRequest.objects.order_by('pk').first()
    api_client.force_authenticate(user=package_context.client)

    list_response = api_client.get(reverse('package-overview', args=[package_context.project.pk]))
    detail_response = api_client.get(
        reverse('package-request-detail', args=[package_context.project.pk, detail_row.pk]),
    )

    list_rows = list_response.json()['requests']['results']
    assert list_response.status_code == 200
    assert len(list_rows) == 20
    assert response_key_sets(list_rows) == {REQUEST_SUMMARY_KEYS}
    assert detail_response.status_code == 200
    assert detail_response.json()['description'] == LONG_REQUEST_DESCRIPTION
