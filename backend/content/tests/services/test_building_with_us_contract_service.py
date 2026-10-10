"""Private contract initialization, append-only editing and atomic artifacts."""
import re
from unittest.mock import Mock

import pytest

from content.models import BuildingWithUsContractMirror, BuildingWithUsContractRevision, Document, DocumentFolder
from content.services import building_with_us_contract_service as service
from content.services.building_with_us_content import BuildingWithUsError
from content.tests.building_with_us_fixtures import contract_update

pytestmark = pytest.mark.django_db


def test_seeded_contract_is_valid(building_with_us_contract):
    """Fails if deployment omits full clauses or applies the public figure guard."""
    revision = building_with_us_contract.current_revision

    markdown = service.validate_markdown(revision.markdown)

    assert revision.version == 1
    assert revision.author_label == 'Sistema'
    assert markdown.startswith('# CONTRATO DE ALIANZA COMERCIAL BUILDING WITH US')
    assert len(re.findall(r'^## CLÁUSULA ', markdown, re.M)) == 21
    assert 'COP 1.000.000' in markdown
    assert '70 % PROJECTAPP / 30 % EL ALIADO' in markdown
    assert service.mirror_status()['status'] == 'not_initialized'


def test_patch_preview_preserves_the_revision(building_with_us_contract):
    """Fails if literal patch preview writes a revision or initializes the mirror."""
    before = service.read_contract()
    arguments = {'patches': [{'operation': 'insert_after', 'text': '# CONTRATO DE ALIANZA COMERCIAL BUILDING WITH US',
                              'markdown': '\n\nTexto aclaratorio.'}]}

    preview = service.prepare_update(arguments)

    assert preview['changed'] is True
    assert '+Texto aclaratorio.' in preview['diff']
    assert preview['placeholders'] == []
    assert preview['document_to_sync'] == {'document_id': None, 'status': 'missing'}
    assert service.read_contract() == before
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_update_requires_an_initialized_mirror(building_with_us_contract, admin_user):
    """Fails if a private contract change can bypass its Document synchronization."""
    arguments = contract_update(service.read_contract())

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=admin_user)

    assert error.value.code == 'MIRROR_NOT_INITIALIZED'
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_initialization_creates_an_internal_document(building_with_us_contract_folder, admin_user):
    """Fails if initialization exposes the contract or omits either private note."""
    result = service.initialize_mirror(building_with_us_contract_folder.pk, actor=admin_user)
    document = Document.objects.get(pk=result['mirror']['document_id'])
    notes = list(document.document_notes.order_by('order').values_list('title', 'content'))

    assert result['outcome'] == 'create'
    assert result['mirror']['status'] == 'synchronized'
    assert result['mirror']['folder_path'] == 'ProjectApp › Contratos'
    assert (document.folder_id, document.client_user_id, document.project_id, document.is_client_visible) == (building_with_us_contract_folder.pk, None, None, False)
    assert document.is_contract_mirror is True
    assert [row[0] for row in notes] == ['Contrato Building with Us — versión 1', 'Inventario de decisiones pendientes (v1)']
    assert notes[1][1] == service.PENDING_DECISIONS_V1


def test_initialization_is_idempotent(initialized_building_with_us_mirror, admin_user):
    """Fails if repeating initialization creates another document, PDF or note."""
    mirror = initialized_building_with_us_mirror
    before = service.mirror_status()
    pdf = bytes(mirror.pdf_content)

    result = service.initialize_mirror(mirror.document.folder_id, actor=admin_user)
    mirror.refresh_from_db()

    assert result == {'outcome': 'noop', 'mirror': before}
    assert bytes(mirror.pdf_content) == pdf
    assert mirror.document.document_notes.count() == 2
    assert BuildingWithUsContractMirror.objects.count() == 1


@pytest.mark.parametrize('kind', ['name', 'archived', 'client', 'system'])
def test_initialization_rejects_disallowed_folders(admin_user, kind):
    """Fails if contractual text can be mirrored outside an active internal folder."""
    values = {'name': {'name': 'Otros'}, 'archived': {'name': 'Contratos', 'is_archived': True},
              'client': {'name': 'Contratos', 'client_user': admin_user},
              'system': {'name': 'Contratos', 'system_key': 'test:reserved-contracts'}}
    folder = DocumentFolder.objects.create(**values[kind])

    with pytest.raises(BuildingWithUsError) as error:
        service.initialize_mirror(folder.pk, actor=admin_user)

    assert error.value.code == 'FOLDER_NOT_ALLOWED'
    assert BuildingWithUsContractMirror.objects.count() == 0


def test_update_synchronizes_the_pdf(initialized_building_with_us_mirror, admin_user):
    """Fails if an applied revision leaves an older PDF or loses its audit note."""
    mirror = initialized_building_with_us_mirror
    before_pdf = bytes(mirror.pdf_content)
    before_stamp = mirror.document.updated_at

    result = service.apply_update(contract_update(service.read_contract()), actor=admin_user)
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert result['version'] == 2
    assert mirror.revision_id == result['version_id']
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert bytes(mirror.pdf_content) != before_pdf
    assert mirror.document.updated_at > before_stamp
    assert mirror.document.document_notes.last().title == 'Contrato Building with Us — versión 2'


@pytest.mark.parametrize('stage', ['pdf', 'private_note'])
def test_synchronization_failure_rolls_back_the_revision(initialized_building_with_us_mirror, admin_user, monkeypatch, stage):
    """Fails if a renderer or late note failure leaves any partial applied state."""
    mirror = initialized_building_with_us_mirror
    before = service.read_contract()
    pdf = bytes(mirror.pdf_content)
    failing = {'pdf': 'render_pdf', 'private_note': 'create_note'}[stage]
    failed_boundary = Mock(side_effect=RuntimeError('Unavailable test boundary'))
    monkeypatch.setattr(service, failing, failed_boundary)

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(contract_update(before), actor=admin_user)
    mirror.refresh_from_db()

    assert (error.value.code, error.value.details) == ('MIRROR_SYNC_FAILED', {'stage': stage, 'applied': False})
    assert service.read_contract() == before
    assert bytes(mirror.pdf_content) == pdf
    assert mirror.document.document_notes.count() == 2
    assert BuildingWithUsContractRevision.objects.count() == 1
    failed_boundary.assert_called_once()


@pytest.mark.parametrize(('markdown', 'code'), [
    ('# Contrato\n\n{party_name}', 'PLACEHOLDER_NOT_SUPPORTED'),
    ('Texto sin título', 'VALIDATION_ERROR'), ('', 'VALIDATION_ERROR'),
    ('# Contrato\n' + 'x' * 250000, 'VALIDATION_ERROR'),
])
def test_preview_rejects_invalid_markdown(building_with_us_contract, markdown, code):
    """Fails if incomplete titles, placeholders or oversized drafts reach editing."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'markdown': markdown})

    assert error.value.code == code
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_restore_appends_a_revision(initialized_building_with_us_mirror, admin_user):
    """Fails if restoring rewrites history or reports a revision id as its number."""
    original = service.read_contract()
    service.apply_update(contract_update(original), actor=admin_user)

    result = service.apply_update({'version_id': original['version_id'], 'if_match': service.read_contract()['etag'],
                                   'change_note': 'Recuperar el contrato inicial.'}, actor=admin_user, restore=True)
    versions = service.list_versions(limit=1, include_content=True)

    assert result['version'] == 3
    assert service.read_contract()['markdown'] == original['markdown']
    assert versions['total'] == 3
    assert versions['versions'][0]['restored_from_version_id'] == original['version_id']
    assert versions['versions'][0]['restored_from_version'] == 1
    assert result['mirror']['status'] == 'synchronized'


def test_initialization_repairs_a_moved_mirror(initialized_building_with_us_mirror, admin_user):
    """Fails if explicit resync cannot return a misplaced mirror to Contratos."""
    mirror = initialized_building_with_us_mirror
    original_folder_id = mirror.document.folder_id
    another = DocumentFolder.objects.create(name='Archivo manual')
    Document.objects.filter(pk=mirror.document_id).update(folder=another)

    result = service.initialize_mirror(original_folder_id, actor=admin_user)

    assert result['outcome'] == 'resync'
    assert result['mirror']['status'] == 'synchronized'
    assert result['mirror']['folder_id'] == original_folder_id
    assert mirror.document.document_notes.count() == 3


def test_update_rechecks_frozen_resources(initialized_building_with_us_mirror, admin_user):
    """Fails if the transactional writer ignores the dependency set of a preview."""
    before = service.read_contract()
    expected = {**service.resource_etags(), 'mirror': 'stale'}

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(contract_update(before), actor=admin_user, expected_etags=expected)

    assert error.value.code == 'STALE_VERSION'
    assert service.read_contract() == before


def test_unchanged_update_preserves_history(initialized_building_with_us_mirror, admin_user):
    """Fails if identical text creates a redundant revision or private note."""
    before = service.read_contract()

    result = service.apply_update({'markdown': before['markdown'], 'if_match': before['etag'],
                                   'change_note': 'Revisión sin cambios.'}, actor=admin_user)

    assert result == {'applied': True, 'changed': False}
    assert BuildingWithUsContractRevision.objects.count() == 1
    assert initialized_building_with_us_mirror.document.document_notes.count() == 2
