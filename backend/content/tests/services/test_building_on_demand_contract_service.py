"""Private cell contract reads, append-only edits and synchronized PDF artifacts."""
from datetime import datetime, timezone
from io import BytesIO
import re
from unittest.mock import Mock

import pytest
from freezegun import freeze_time
from pypdf import PdfReader

from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision, Document
from content.services import building_on_demand_contract_service as service
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db


def test_read_returns_the_seeded_private_contract(building_on_demand_contract):
    """Fails if the deployed contract lacks its complete initial text or provenance."""
    revision = building_on_demand_contract.current_revision

    snapshot = service.read_contract()

    assert snapshot['markdown'].startswith('# CONTRATO DE ALQUILER DE CÉLULA — BUILDING ON DEMAND')
    assert (snapshot['version'], snapshot['version_id'], snapshot['author']) == (1, revision.pk, 'Sistema')
    assert snapshot['change_note'] == 'Versión inicial del contrato de Building on Demand (PA-177/PA-179).'
    assert snapshot['markdown'] == service.validate_markdown(revision.markdown)
    assert snapshot['mirror'] == {
        'status': 'not_initialized', 'document_id': None, 'title': service.CONTRACT_TITLE,
        'folder_id': None, 'folder_path': None, 'version': None, 'last_synced_at': None,
    }


def test_seed_keeps_the_complete_contract_structure(building_on_demand_contract):
    """Fails if the deployed draft loses clauses, annexes, signature blanks or privacy terms."""
    markdown = service.read_contract()['markdown']

    assert len(re.findall(r'^## CLÁUSULA ', markdown, re.M)) == 20
    assert re.findall(r'^## (?!CLÁUSULA)(.+)$', markdown, re.M) == [
        'ANTECEDENTES', 'CONDICIONES PARTICULARES', 'ANEXO A — PRODUCTO, CÉLULA E INFRAESTRUCTURA',
        'EN CONSTANCIA DE LO ANTERIOR,',
    ]
    assert 'XXX-XXX-XXX' in markdown
    assert 'Ley 1581 de 2012' in markdown
    assert '{party_name}' not in markdown


@pytest.mark.parametrize('row', [
    '| Starter | 96 horas | Desarrollo, líder de proyecto y QA en cada entrega. | 1 vCPU / 4 GB / 50 GB / 4 TB | 48 horas hábiles | Una | COP 1.800.000 |',
    '| Business | 192 horas | Todo Starter; diseñador, arquitecto de desarrollo, sesiones de levantamiento de requerimientos y deploy a producción. | 4 vCPU / 16 GB / 200 GB / 16 TB | 24 horas hábiles | Dos | COP 4.200.000 |',
    '| Enterprise | 288 horas | Todo Business; Scrum Master dedicado a la coordinación del servicio, DevOps continuo y prioridad de atención. | 8 vCPU / 32 GB / 400 GB / 32 TB | 4 horas, con prioridad | Tres | COP 9.600.000 |',
])
def test_seed_matches_the_approved_plan_reference(building_on_demand_contract, row):
    """Fails if private plan references diverge from approved hours, roles, VPS or pricing."""
    markdown = service.read_contract()['markdown']

    assert row in markdown.splitlines()
    assert '| Business | 10 % | COP 3.780.000 / COP 11.340.000 | 15 % | COP 3.570.000 / COP 21.420.000 | 20 % | COP 3.360.000 / COP 30.240.000 |' in markdown


def test_initial_inventory_retains_both_fichas(pinned_contracts_folder, admin_user):
    """Fails if initialization omits open questions, their v1 answers or the review warning."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()

    note = mirror.document.document_notes.get(title='Inventario de decisiones pendientes (v1)').content
    pa177, pa179 = note.split('PA-177 —', 1)[1].split('PA-179 —', 1)

    assert re.findall(r'^(\d+)\. ', pa177, re.M) == list(map(str, range(1, 27)))
    assert re.findall(r'^(\d+)\. ', pa179, re.M) == list(map(str, range(1, 12)))
    assert 'Referencia de 55.000 pesos por hora estimada' in pa177
    assert 'Decidido: 15 por ciento' in pa177
    assert 'sólo esa estimación descuenta horas' in pa179
    assert note.endswith('Borrador para revisión del operador y de un asesor jurídico antes de usarlo con un cliente.')


def test_seed_preserves_the_agreed_infrastructure_exit(building_on_demand_contract):
    """Fails if the draft promises a named hosting vendor or omits the client's exit copy."""
    markdown = service.read_contract()['markdown']

    assert 'un VPS bajo la cuenta de PROJECTAPP' in markdown
    assert 'en un proveedor elegido por PROJECTAPP' in markdown
    assert 'una copia completa del código y los datos de su producto' in markdown
    assert 'treinta (30) días calendario de transición' in markdown
    assert 'Hostinger' not in markdown


def test_first_write_creates_the_pinned_mirror(pinned_contracts_folder, admin_user):
    """Fails if the first contract edit leaves its revision without a private mirror."""
    before = service.read_contract()

    result = service.apply_update(contract_update(before), actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    document = mirror.document

    assert (result['applied'], result['changed'], result['version']) == (True, True, 2)
    assert mirror.revision_id == result['version_id']
    assert result['mirror']['status'] == 'synchronized'
    assert (document.folder_id, document.client_user_id, document.project_id, document.is_client_visible) == (
        pinned_contracts_folder.pk, None, None, False,
    )
    assert document.content_markdown == service.MIRROR_POINTER
    assert list(document.document_notes.values_list('title', flat=True)) == [
        'Contrato Building on Demand — versión 2', 'Inventario de decisiones pendientes (v1)',
    ]
    assert document.document_notes.last().content == service.PENDING_DECISIONS_V1


def test_matching_preview_permits_a_missing_pinned_mirror(pinned_contracts_folder):
    """Fails if a valid first-write preview requires a mirror that the write must create."""
    before = service.read_contract()

    prepared = service.prepare_update(contract_update(before), require_match=True)

    assert prepared['changed'] is True
    assert prepared['markdown'] == contract_update(before)['markdown']
    assert prepared['document_to_sync'] == {'document_id': None, 'status': 'missing'}
    assert prepared['placeholders'] == []
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_patch_preview_leaves_the_contract_untouched(building_on_demand_contract):
    """Fails if preparing a literal markdown patch mutates the current contract."""
    before = service.read_contract()
    arguments = {'patches': [{
        'operation': 'insert_after',
        'text': '# CONTRATO DE ALQUILER DE CÉLULA — BUILDING ON DEMAND',
        'markdown': '\n\nAclaración privada para revisión.',
    }]}

    prepared = service.prepare_update(arguments)

    assert prepared['changed'] is True
    assert '+Aclaración privada para revisión.' in prepared['diff']
    assert 'Aclaración privada para revisión.' in prepared['markdown']
    assert service.read_contract() == before
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_patch_write_updates_the_mirror(pinned_contracts_folder, admin_user):
    """Fails if applying literal patches updates history without the Gestor document."""
    before = service.read_contract()
    arguments = {
        'patches': [{'operation': 'insert_after', 'text': before['markdown'].splitlines()[0],
                     'markdown': '\n\nCondición aprobada por escrito.'}],
        'if_match': before['etag'], 'change_note': 'Precisa una condición acordada.',
    }

    result = service.apply_update(arguments, actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()

    assert result['version'] == 2
    assert 'Condición aprobada por escrito.' in service.read_contract()['markdown']
    assert mirror.revision_id == result['version_id']
    assert mirror.document.document_notes.first().title == 'Contrato Building on Demand — versión 2'
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')


def test_existing_write_replaces_the_pdf(pinned_contracts_folder, admin_user):
    """Fails if an applied revision keeps the prior PDF or loses its version note."""
    with freeze_time('2026-10-11 11:00:00'):
        service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    prior_pdf = bytes(mirror.pdf_content)

    with freeze_time('2026-10-11 13:00:00'):
        result = service.apply_update(contract_update(service.read_contract()), actor=admin_user)
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert mirror.revision_id == result['version_id']
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert bytes(mirror.pdf_content) != prior_pdf
    assert mirror.document.updated_at == datetime(2026, 10, 11, 13, tzinfo=timezone.utc)
    assert mirror.document.document_notes.last().title == 'Contrato Building on Demand — versión 2'


def test_unchanged_write_preserves_contract_history(pinned_contracts_folder, admin_user):
    """Fails if identical text creates another immutable revision or private note."""
    service.sync_mirror(actor=admin_user)
    before = service.read_contract()
    arguments = {'markdown': before['markdown'], 'if_match': before['etag'], 'change_note': 'Revisión sin cambios.'}

    result = service.apply_update(arguments, actor=admin_user)

    assert result == {'applied': True, 'changed': False}
    assert service.read_contract() == before
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.get().document.document_notes.count() == 2


def test_unchanged_first_write_still_creates_the_mirror(pinned_contracts_folder, admin_user):
    """Fails if submitting unchanged text bypasses the required initial synchronization."""
    before = service.read_contract()
    arguments = {'markdown': before['markdown'], 'if_match': before['etag'], 'change_note': 'Inicializar el espejo vigente.'}

    result = service.apply_update(arguments, actor=admin_user)

    assert result == {'applied': True, 'changed': False}
    assert service.mirror_status()['status'] == 'synchronized'
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert BuildingOnDemandContractMirror.objects.get().revision_id == before['version_id']
    assert BuildingOnDemandContractMirror.objects.get().document.document_notes.count() == 2


def test_restore_appends_a_historical_contract(pinned_contracts_folder, admin_user):
    """Fails if restoring overwrites history or leaves the mirror on a different version."""
    original = service.read_contract()
    unused = BuildingOnDemandContractRevision.objects.create(
        version=100, markdown=original['markdown'], change_note='Reserva de identificador para la prueba.',
    )
    BuildingOnDemandContractRevision.objects.filter(pk=unused.pk).delete()
    service.apply_update(contract_update(original), actor=admin_user)
    target = service.read_contract()
    service.apply_update({**contract_update(target), 'markdown': target['markdown'] + '\n\nAcuerdo temporal.'}, actor=admin_user)
    arguments = {'version_id': target['version_id'], 'if_match': service.read_contract()['etag'],
                 'change_note': 'Recupera la segunda versión del contrato.'}

    result = service.apply_update(arguments, actor=admin_user, restore=True)
    versions = service.list_versions(limit=1, include_content=True)

    assert result['version'] == 4
    assert service.read_contract()['markdown'] == target['markdown']
    assert versions['total'] == 4
    assert versions['versions'][0]['restored_from_version_id'] == target['version_id']
    assert versions['versions'][0]['restored_from_version'] == 2
    assert result['mirror']['version'] == 4
    assert result['mirror']['status'] == 'synchronized'


def test_version_listing_paginates_without_private_text(pinned_contracts_folder, admin_user):
    """Fails if history pagination reverses chronology or includes unrequested markdown."""
    original = service.read_contract()
    service.apply_update(contract_update(original), actor=admin_user)

    page = service.list_versions(offset=1, limit=1)

    assert page['total'] == 2
    assert [row['version'] for row in page['versions']] == [1]
    assert page['versions'][0]['version_id'] == original['version_id']
    assert 'markdown' not in page['versions'][0]
    assert (page['versions'][0]['restored_from_version_id'], page['versions'][0]['restored_from_version']) == (None, None)


def test_version_listing_includes_requested_markdown(building_on_demand_contract):
    """Fails if include_content omits the literal revision needed for restoration review."""
    revision = building_on_demand_contract.current_revision

    page = service.list_versions(include_content=True)

    assert page['total'] == 1
    assert page['versions'][0]['markdown'] == revision.markdown
    assert page['versions'][0]['author'] == 'Sistema'


def test_current_pdf_reuses_the_synchronized_artifact(pinned_contracts_folder, admin_user, monkeypatch):
    """Fails if reading a synchronized PDF renders again or writes another private note."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    renderer = Mock(side_effect=RuntimeError('Unexpected PDF regeneration'))
    monkeypatch.setattr(service.DocumentPdfService, 'generate_from_markdown', renderer)

    pdf, version = service.current_pdf()

    assert pdf == bytes(mirror.pdf_content)
    assert version == 1
    assert mirror.document.document_notes.count() == 2
    renderer.assert_not_called()


def test_current_pdf_renders_before_initialization(building_on_demand_contract):
    """Fails if a private PDF read requires a mirror or creates Gestor records."""
    document_count = Document.objects.count()

    pdf, version = service.current_pdf()
    pages = PdfReader(BytesIO(pdf)).pages
    extracted_text = '\n'.join(map(lambda page: page.extract_text(), pages))

    assert pdf.startswith(b'%PDF-')
    assert version == 1
    assert 'BUILDING ON DEMAND' in extracted_text.upper()
    assert BuildingOnDemandContractMirror.objects.count() == 0
    assert Document.objects.count() == document_count


def test_outdated_pdf_read_does_not_repair_the_mirror(pinned_contracts_folder, admin_user):
    """Fails if serving an outdated artifact writes synchronization state during a read."""
    service.sync_mirror(actor=admin_user)
    mirror = BuildingOnDemandContractMirror.objects.get()
    BuildingOnDemandContractMirror.objects.filter(pk=mirror.pk).update(pdf_content=b'invalid')

    pdf, version = service.current_pdf()
    mirror.refresh_from_db()

    assert pdf.startswith(b'%PDF-')
    assert version == 1
    assert bytes(mirror.pdf_content) == b'invalid'
    assert mirror.document.document_notes.count() == 2
    assert service.mirror_status()['status'] == 'out_of_sync'
