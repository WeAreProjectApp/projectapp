"""Gestor reads the alliance contract and keeps both mirror families locked."""
import pytest
from django.urls import reverse

from content.models import BuildingWithUsContractRevision
from content.services import building_with_us_contract_service as service
from content.services.document_write_service import document_etag
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


def test_panel_edit_creates_a_synchronized_alliance_revision(admin_client, initialized_building_with_us_mirror):
    """Fails if Gestor content editing skips the alliance revision."""
    mirror = initialized_building_with_us_mirror
    response = admin_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'content_markdown': '# Contrato de alianza actualizado\n\nLa evidencia se conserva con el hito.',
        'if_match': document_etag(mirror.document),
        'change_note': 'Aclara la conservación de evidencia.',
        'include_content': True,
    }, format='json')
    mirror.refresh_from_db()

    assert response.status_code == 200
    assert response.data['markdown'] == '# Contrato de alianza actualizado\n\nLa evidencia se conserva con el hito.'
    assert response.data['contract_version'] == 2
    assert service.read_contract()['markdown'] == response.data['markdown']
    assert mirror.revision.version == 2


def test_panel_edit_regenerates_the_alliance_pdf_for_presentation_changes(admin_client, initialized_building_with_us_mirror):
    """Fails if a presentation-only Gestor edit leaves the stored alliance PDF unchanged."""
    mirror = initialized_building_with_us_mirror
    before_pdf = bytes(mirror.pdf_content)
    response = admin_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'if_match': document_etag(mirror.document),
        'change_note': 'Actualiza la presentación del contrato.',
        'include_portada': False,
        'template_style': 'friendly',
    }, format='json')
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert response.status_code == 200
    assert mirror.revision.version == 2
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert bytes(mirror.pdf_content) != before_pdf
    assert (mirror.document.include_portada, mirror.document.template_style) == (False, 'friendly')


def test_panel_edit_requires_the_document_version(admin_client, initialized_building_with_us_mirror):
    """Fails if a Gestor edit can overwrite an alliance revision without its displayed ETag."""
    mirror = initialized_building_with_us_mirror
    before = service.read_contract()

    response = admin_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'content_markdown': '# Contrato de alianza actualizado',
        'change_note': 'Intento sin precondición.',
    }, format='json')

    assert response.status_code == 428
    assert response.data['code'] == 'PRECONDITION_REQUIRED'
    assert service.read_contract() == before


def test_panel_edit_refuses_a_non_admin(api_client, admin_user, initialized_building_with_us_mirror):
    """Fails if a signed-in user without panel administration can revise the alliance contract."""
    mirror = initialized_building_with_us_mirror
    admin_user.is_staff = False
    admin_user.save(update_fields=['is_staff'])
    api_client.force_authenticate(user=admin_user)

    response = api_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'content_markdown': '# Contrato no autorizado',
        'if_match': document_etag(mirror.document),
        'change_note': 'Intento sin permiso.',
    }, format='json')

    assert response.status_code == 403
    assert service.read_contract()['version'] == 1


def test_panel_edit_rejects_protected_metadata(admin_client, initialized_building_with_us_mirror):
    """Fails if an alliance edit can rename or relocate the contract through the content writer."""
    mirror = initialized_building_with_us_mirror
    before = service.read_contract()

    response = admin_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'title': 'Contrato reubicado',
        'if_match': document_etag(mirror.document),
        'change_note': 'Intento de cambiar la ubicación.',
    }, format='json')
    mirror.document.refresh_from_db()

    assert response.status_code == 400
    assert response.data['code'] == 'VALIDATION_ERROR'
    assert mirror.document.title == service.CONTRACT_TITLE
    assert service.read_contract() == before


def test_contract_etag_changes_when_only_the_current_revision_changes(initialized_building_with_us_mirror):
    """Fails if a stale editor cannot detect a revision change that leaves document.updated_at untouched."""
    mirror = initialized_building_with_us_mirror
    original_etag = document_etag(mirror.document)
    original_updated_at = mirror.document.updated_at
    revision = BuildingWithUsContractRevision.objects.create(
        version=2, markdown='# Contrato posterior', change_note='Cambio directo de prueba.',
    )
    mirror.contract.current_revision = revision
    mirror.contract.save(update_fields=['current_revision'])
    mirror.document.refresh_from_db()

    assert mirror.document.updated_at == original_updated_at
    assert document_etag(mirror.document) != original_etag


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
    assert (data['editable'], data['content_editable'], data['movable']) == (True, True, False)
    assert data['edit_blockers'] == []
    assert data['contract_variant'] == 'building_with_us'
    assert data['contract_version'] == 1


def test_documents_mcp_lists_only_proposal_mirrors(api_client, building_with_us_documents_mcp, initialized_building_with_us_mirror, initialized_contract_mirrors):
    """Fails if BWU changes the established three-variant proposal discovery tool."""
    result = rpc_call(api_client, building_with_us_documents_mcp, 'list_contract_mirrors', {}, slug='documents')['structuredContent']

    assert {row['variant'] for row in result['mirrors']} == {'combined', 'product', 'service'}
    assert initialized_building_with_us_mirror.document_id not in [row['document_id'] for row in result['mirrors']]
    assert len(result['mirrors']) == 3


def test_documents_mcp_rejects_a_stale_alliance_editor(api_client, building_with_us_documents_mcp, initialized_building_with_us_mirror, admin_client):
    """Fails if Documents MCP overwrites an alliance edit that Gestor saved first."""
    mirror = initialized_building_with_us_mirror
    stale_etag = document_etag(mirror.document)
    panel = admin_client.patch(reverse('update-document', args=[mirror.document_id]), {
        'content_markdown': '# Contrato vigente\n\nPrimero guarda el Gestor.',
        'if_match': stale_etag,
        'change_note': 'Primera edición del Gestor.',
    }, format='json')

    result = rpc_call(api_client, building_with_us_documents_mcp, 'update_document',
                      {'document_id': mirror.document_id, 'markdown': '# Otro contrato',
                       'if_match': stale_etag, 'change_note': 'Edición desactualizada.'}, slug='documents')

    assert panel.status_code == 200
    assert result['isError'] is True
    assert result['structuredContent']['error']['code'] == 'STALE_VERSION'
    assert service.read_contract()['markdown'] == '# Contrato vigente\n\nPrimero guarda el Gestor.'


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
