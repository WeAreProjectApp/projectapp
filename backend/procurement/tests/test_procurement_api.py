"""HTTP contract tests for ProjectApp procurement administration."""

from io import BytesIO

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from openpyxl import load_workbook
from procurement.models import Classification, Delivery

pytestmark = pytest.mark.django_db


def test_classification_endpoint_rejects_prohibited_clients(opportunity, prohibited_procurement_client):
    """Falla si una persona externa lee procesos o una sesión sin CSRF registra seguimiento."""
    record = opportunity('PERMISSIONS-1')

    response = prohibited_procurement_client.post(
        f'/api/procurement/opportunities/{record.pk}/classification/',
        {'state': 'interesting', 'notes': 'Revisar requisitos.'}, format='json',
    )

    assert response.status_code == 403
    assert Classification.objects.count() == 0


def test_classification_endpoint_rejects_array_payload(opportunity, staff_client):
    """Falla si una carga JSON con forma inválida llega a crear una clasificación."""
    record = opportunity('INVALID-PAYLOAD')

    response = staff_client.post(
        f'/api/procurement/opportunities/{record.pk}/classification/',
        [{'state': 'interesting'}], format='json',
    )

    assert response.status_code == 400
    assert Classification.objects.filter(opportunity=record).count() == 0


def test_paginated_opportunities_exclude_heavy_descriptions(opportunity, many_opportunities, staff_client):
    """Falla si la tabla carga descripciones SECOP pesadas en cada fila paginada."""
    opportunity('LIST-1', description='x' * 50000)
    many_opportunities(99, description='x' * 50000)

    with CaptureQueriesContext(connection) as queries:
        response = staff_client.get('/api/procurement/opportunities/')

    body = response.json()
    assert response.status_code == 200
    assert (body['count'], body['page'], body['page_size']) == (100, 1, 25)
    assert 'description' not in body['results'][0]
    assert len(queries) <= 6
    assert len(response.content) < 262144


def test_paginated_opportunities_include_only_requester_classification(
        opportunity, staff_user, other_staff_user, staff_client):
    """Falla si el panel presenta como propia la decisión de otro administrador."""
    record = opportunity('MY-CLASSIFICATION')
    mine = Classification.objects.create(opportunity=record, owner=staff_user, state='interesting')
    Classification.objects.create(opportunity=record, owner=other_staff_user, state='discarded', notes='Ajena')

    response = staff_client.get('/api/procurement/opportunities/')

    assert response.json()['results'][0]['my_classification'] == {
        'id': mine.pk, 'state': 'interesting', 'owner': staff_user.pk,
    }


def test_opportunity_detail_keeps_full_description_for_the_review_screen(opportunity, staff_client):
    """Falla si compactar el listado también borra la evidencia extensa necesaria en el detalle."""
    record = opportunity('DETAIL-1', description='e' * 50000)

    response = staff_client.get(f'/api/procurement/opportunities/{record.pk}/')

    assert response.status_code == 200
    assert response.json()['description'] == 'e' * 50000


def test_delivery_list_excludes_heavy_snapshot(staff_client):
    """Falla si la tabla descarga la evidencia pesada de cada entrega."""
    Delivery.objects.create(
        recipient='carlos@example.com', frequency='daily', opportunity_count=2,
        snapshot={'opportunities': [{'title': 'Proceso auditado'}]},
    )

    listing = staff_client.get('/api/procurement/deliveries/')

    assert listing.status_code == 200
    assert listing.json()['results'][0]['opportunity_count'] == 2
    assert 'snapshot' not in listing.json()['results'][0]


def test_delivery_detail_preserves_auditable_snapshot(staff_client):
    """Falla si el detalle deja de permitir auditar la evidencia de una entrega."""
    delivery = Delivery.objects.create(
        recipient='carlos@example.com', frequency='daily', opportunity_count=2,
        snapshot={'opportunities': [{'title': 'Proceso auditado'}]},
    )

    detail = staff_client.get(f'/api/procurement/deliveries/{delivery.pk}/')

    assert detail.json()['snapshot'] == {'opportunities': [{'title': 'Proceso auditado'}]}


@pytest.mark.parametrize('prefix', ['=', '+', '-', '@'])
def test_export_escapes_excel_formula_prefixes(opportunity, staff_client, prefix):
    """Falla si Excel interpreta texto SECOP controlado como una fórmula al abrir la descarga."""
    record = opportunity(f'EXPORT-{ord(prefix)}', reference=f'{prefix}REF', title=f'{prefix}Título')

    response = staff_client.get('/api/procurement/export/')
    rows = list(load_workbook(BytesIO(response.content), read_only=True).active.iter_rows(values_only=True))

    exported = next(row for row in rows[1:] if row[0] == f"'{record.reference}")
    assert response.status_code == 200
    assert response['Content-Disposition'] == 'attachment; filename="oportunidades-secop.xlsx"'
    assert exported[:2] == (f"'{record.reference}", f"'{record.title}")
