"""Gestor reads the alliance contract and keeps both mirror families locked."""
import pytest
from django.urls import reverse

from content.models import BuildingWithUsContractRevision
from content.services import building_with_us_contract_service as service
from content.services.contract_mirror_service import BUILDING_WITH_US_MIRROR_MESSAGE
from content.tests.building_with_us_fixtures import rpc_call

pytestmark = pytest.mark.django_db


def test_document_detail_reads_the_alliance_contract(admin_client, initialized_building_with_us_mirror):
    """Fails if the Gestor falls back to a proposal contract for this mirror."""
    mirror = initialized_building_with_us_mirror

    response = admin_client.get(reverse('retrieve-document', args=[mirror.document_id]))

    assert response.status_code == 200
    assert response.data['content_markdown'] == service.read_contract()['markdown']
    assert response.data['contract_variant'] == 'building_with_us'
    assert response.data['contract_version'] == 1
    assert response.data['contract_synced_at'] == mirror.synced_at.isoformat()
    assert response.data['is_contract_mirror'] is True


def test_document_pdf_serves_the_stored_copy(admin_client, initialized_building_with_us_mirror):
    """Fails if a Gestor download substitutes a freshly rendered proposal PDF."""
    mirror = initialized_building_with_us_mirror

    response = admin_client.get(reverse('download-document-pdf', args=[mirror.document_id]))

    assert response.status_code == 200
    assert response.content == bytes(mirror.pdf_content)
    assert response.content.startswith(b'%PDF-')


def test_document_pdf_refuses_an_outdated_copy(admin_client, initialized_building_with_us_mirror):
    """Fails if unsupported direct writes expose a previous contract as current."""
    mirror = initialized_building_with_us_mirror
    revision = BuildingWithUsContractRevision.objects.create(version=2, markdown='# Contrato posterior', change_note='Cambio directo de prueba.')
    mirror.contract.current_revision = revision
    mirror.contract.save(update_fields=['current_revision', 'updated_at'])

    response = admin_client.get(reverse('download-document-pdf', args=[mirror.document_id]))

    assert response.status_code == 503
    assert response.data['detail'] == 'El contrato vigente no está disponible en este momento.'


@pytest.mark.parametrize('route', ['update-document', 'archive-document'])
def test_panel_refuses_mirror_writes(admin_client, initialized_building_with_us_mirror, route):
    """Fails if either editing or archiving bypasses the BWU-specific read-only guard."""
    mirror = initialized_building_with_us_mirror
    before = mirror.document.content_markdown

    response = admin_client.patch(reverse(route, args=[mirror.document_id]), {'content_markdown': '# Prohibido'}, format='json')
    mirror.document.refresh_from_db()

    assert response.status_code == 409
    assert response.data['code'] == 'contract_mirror_read_only'
    assert response.data['detail'] == BUILDING_WITH_US_MIRROR_MESSAGE
    assert mirror.document.content_markdown == before
    assert mirror.document.is_archived is False


@pytest.mark.parametrize(('route', 'payload', 'status'), [
    ('update-document-folder', {'name': 'Otro nombre'}, 400),
    ('archive-document-folder', {}, 409),
])
def test_panel_protects_the_contract_folder(admin_client, initialized_building_with_us_mirror, route, payload, status):
    """Fails if a folder mutation removes this mirror from active Contratos."""
    folder = initialized_building_with_us_mirror.document.folder

    response = admin_client.patch(reverse(route, args=[folder.pk]), payload, format='json')
    folder.refresh_from_db()

    assert response.status_code == status
    assert folder.name == 'Contratos'
    assert folder.is_archived is False


def test_documents_mcp_reads_the_live_mirror(api_client, building_with_us_documents_mcp, initialized_building_with_us_mirror):
    """Fails if the documents connector exposes the pointer instead of current text."""
    mirror = initialized_building_with_us_mirror

    result = rpc_call(api_client, building_with_us_documents_mcp, 'read_document', {'document_id': mirror.document_id}, slug='documents')
    data = result['structuredContent']

    assert result['isError'] is False
    assert data['markdown'] == service.read_contract()['markdown']
    assert data['is_contract_mirror'] is True
    assert data['edit_blockers'] == ['contract_mirror']
    assert data['contract_variant'] == 'building_with_us'
    assert data['contract_version'] == 1


def test_documents_mcp_lists_only_proposal_mirrors(api_client, building_with_us_documents_mcp, initialized_building_with_us_mirror, initialized_contract_mirrors):
    """Fails if BWU changes the established three-variant proposal discovery tool."""
    result = rpc_call(api_client, building_with_us_documents_mcp, 'list_contract_mirrors', {}, slug='documents')['structuredContent']

    assert {row['variant'] for row in result['mirrors']} == {'combined', 'product', 'service'}
    assert initialized_building_with_us_mirror.document_id not in [row['document_id'] for row in result['mirrors']]
    assert len(result['mirrors']) == 3


def test_documents_mcp_refuses_contract_edits(api_client, building_with_us_documents_mcp, initialized_building_with_us_mirror):
    """Fails if the other connector becomes an alternate writer of alliance text."""
    mirror = initialized_building_with_us_mirror

    result = rpc_call(api_client, building_with_us_documents_mcp, 'update_document',
                      {'document_id': mirror.document_id, 'markdown': '# Otro contrato'}, slug='documents')

    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'NOT_EDITABLE'
    assert result['structuredContent']['error']['message'] == BUILDING_WITH_US_MIRROR_MESSAGE


def test_panel_pdf_renders_live_when_the_mirror_is_outdated(admin_client, initialized_building_with_us_mirror):
    """Fails if the module's read-only PDF endpoint cannot render current content."""
    mirror = initialized_building_with_us_mirror
    revision = BuildingWithUsContractRevision.objects.create(version=2, markdown='# Contrato posterior', change_note='Cambio directo de prueba.')
    mirror.contract.current_revision = revision
    mirror.contract.save(update_fields=['current_revision', 'updated_at'])
    before_pdf = bytes(mirror.pdf_content)

    response = admin_client.get(reverse('admin-building-with-us-contract-pdf'), {'inline': '1'})
    mirror.refresh_from_db()

    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert response.content != before_pdf
    assert response['Content-Disposition'] == 'inline; filename="contrato-building-with-us-v2.pdf"'
    assert response['X-Frame-Options'] == 'SAMEORIGIN'
    assert response['Cache-Control'] == 'private, no-store'
    assert bytes(mirror.pdf_content) == before_pdf


def test_panel_pdf_uses_the_synchronized_copy(admin_client, initialized_building_with_us_mirror):
    """Fails if a synchronized module download unnecessarily changes the stored PDF."""
    mirror = initialized_building_with_us_mirror

    response = admin_client.get(reverse('admin-building-with-us-contract-pdf'))

    assert response.status_code == 200
    assert response.content == bytes(mirror.pdf_content)
    assert response['Content-Disposition'] == 'attachment; filename="contrato-building-with-us-v1.pdf"'
