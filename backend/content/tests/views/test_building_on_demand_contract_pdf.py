"""The Panel downloads its current private contract without changing the mirror."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision
from content.services import building_on_demand_contract_service as service

pytestmark = pytest.mark.django_db
PDF_ROUTE = 'admin-building-on-demand-contract-pdf'


@pytest.mark.parametrize(('query', 'disposition'), [
    ({}, 'attachment'), ({'inline': '1'}, 'inline'), ({'inline': 'true'}, 'attachment'),
])
def test_contract_pdf_uses_the_synchronized_artifact(
    admin_client, building_on_demand_contract, pinned_contracts_folder, superuser, query, disposition,
):
    """Fails if download disposition or embedding headers change the synchronized PDF."""
    service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
               side_effect=AssertionError('A synchronized PDF must not be rendered again.')):
        response = admin_client.get(reverse(PDF_ROUTE), query)

    assert response.status_code == 200
    assert response.content == bytes(mirror.pdf_content)
    assert response.content.startswith(b'%PDF-')
    assert response['Content-Disposition'] == f'{disposition}; filename="contrato-building-on-demand-v1.pdf"'
    assert response['X-Frame-Options'] == 'SAMEORIGIN'
    assert response['Cache-Control'] == 'private, no-store'
    assert mirror.document.document_notes.count() == 2


def test_contract_pdf_renders_without_initializing_a_document(admin_client, building_on_demand_contract):
    """Fails if reading a contract PDF creates a mirror or private synchronization note."""
    response = admin_client.get(reverse(PDF_ROUTE))

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert response['Content-Disposition'] == 'attachment; filename="contrato-building-on-demand-v1.pdf"'
    assert not BuildingOnDemandContractMirror.objects.filter(contract=building_on_demand_contract).exists()


def test_contract_pdf_renders_the_current_unsynchronized_revision(
    admin_client, building_on_demand_contract, pinned_contracts_folder, superuser,
):
    """Fails if an outdated mirror is served as current or changed during a Panel download."""
    service.sync_mirror(actor=superuser)
    mirror = BuildingOnDemandContractMirror.objects.get(contract=building_on_demand_contract)
    before_pdf = bytes(mirror.pdf_content)
    before_synced_at = mirror.synced_at
    revision = BuildingOnDemandContractRevision.objects.create(
        version=2, markdown='# CONTRATO POSTERIOR\n\nContenido vigente distinto.', change_note='Cambio directo de prueba.',
    )
    building_on_demand_contract.current_revision = revision
    building_on_demand_contract.save(update_fields=['current_revision', 'updated_at'])

    response = admin_client.get(reverse(PDF_ROUTE), {'inline': '1'})
    mirror.refresh_from_db()

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert response.content != before_pdf
    assert response['Content-Disposition'] == 'inline; filename="contrato-building-on-demand-v2.pdf"'
    assert bytes(mirror.pdf_content) == before_pdf
    assert mirror.synced_at == before_synced_at
    assert mirror.document.document_notes.count() == 2


def test_contract_pdf_reports_render_failure(admin_client, building_on_demand_contract):
    """Fails if a failed PDF renderer becomes an empty download or writes a mirror."""
    with patch('content.services.document_pdf_service.DocumentPdfService.generate_from_markdown',
               side_effect=RuntimeError('PDF renderer unavailable.')):
        response = admin_client.get(reverse(PDF_ROUTE))

    assert response.status_code == 400
    assert response.data == {
        'message': 'El PDF vigente no está disponible.', 'code': 'PDF_RENDER_FAILED', 'details': {},
    }
    assert not BuildingOnDemandContractMirror.objects.exists()
