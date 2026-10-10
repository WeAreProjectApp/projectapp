"""Private contract validation, transactional rejection and artifact failures."""
from unittest.mock import DEFAULT, Mock

import pytest

from content.models import BuildingWithUsContractMirror, BuildingWithUsContractRevision, Document, DocumentFolder, DocumentNote
from content.services import building_with_us_contract_service as service
from content.services.building_with_us_content import BuildingWithUsError
from content.tests.building_with_us_fixtures import contract_update

pytestmark = pytest.mark.django_db


def test_markdown_requires_text():
    """Fails if non-text markdown raises a native error instead of structured validation."""
    with pytest.raises(BuildingWithUsError) as error:
        service.validate_markdown(None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'markdown debe ser texto no vacío de hasta 250000 caracteres.'


@pytest.mark.parametrize('folder_id', [None, True, 0, '1'])
def test_initialization_requires_a_positive_folder_id(folder_id):
    """Fails if initialization coerces invalid identifiers into internal folders."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_initialization(folder_id)

    assert error.value.code == 'FOLDER_NOT_ALLOWED'
    assert error.value.message == 'folder_id debe ser un entero positivo.'
    assert BuildingWithUsContractMirror.objects.count() == 0


@pytest.mark.parametrize('arguments', [None, {'unexpected': True}])
def test_preview_rejects_unknown_arguments(arguments):
    """Fails if the contract preview accepts arguments outside its declared contract."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update(arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Hay argumentos desconocidos.'


@pytest.mark.parametrize(('arguments', 'restore'), [
    ({}, False), ({'markdown': '# Contrato', 'patches': []}, False), ({}, True),
])
def test_preview_requires_one_source(arguments, restore):
    """Fails if ambiguous edits or a restore without version_id reach preparation."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update(arguments, restore=restore)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Indica exactamente markdown o patches; para restaurar usa version_id.'


@pytest.mark.parametrize('version_id', [None, True, 0, '1'])
def test_restore_requires_a_positive_version_id(building_with_us_contract, version_id):
    """Fails if restoration accepts non-positive or coerced revision identifiers."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'version_id': version_id}, restore=True)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'version_id debe ser un entero positivo.'
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_restore_requires_an_existing_revision(building_with_us_contract):
    """Fails if missing historical contract text is reported as an internal error."""
    missing_id = building_with_us_contract.current_revision_id + 1000

    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'version_id': missing_id}, restore=True)

    assert error.value.code == 'NOT_FOUND'
    assert error.value.message == 'La versión no existe.'
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_publication_requires_a_precondition(building_with_us_contract):
    """Fails if a contract publication can omit the version precondition."""
    arguments = contract_update(service.read_contract())
    arguments.pop('if_match')

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'PRECONDITION_REQUIRED'
    assert error.value.message == 'if_match es obligatorio.'
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_publication_rejects_a_stale_precondition(building_with_us_contract):
    """Fails if an outdated if_match can publish private contractual text."""
    before = service.read_contract()
    arguments = {**contract_update(before), 'if_match': 'stale'}

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'STALE_VERSION'
    assert error.value.message == 'El contrato cambió; vuelve a leerlo.'
    assert error.value.details == {'current_etag': before['etag']}
    assert service.read_contract() == before


@pytest.mark.parametrize('note', [None, '   ', 'x' * 4001])
def test_publication_rejects_invalid_change_notes(building_with_us_contract, note):
    """Fails if publication lacks a usable audit explanation before mirror synchronization."""
    arguments = {**contract_update(service.read_contract()), 'change_note': note}

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'change_note debe explicar el cambio (entre 1 y 4000 caracteres).'
    assert BuildingWithUsContractRevision.objects.count() == 1


@pytest.mark.parametrize(('patches', 'code', 'message', 'details'), [
    ([], 'VALIDATION_ERROR', 'patches debe contener entre 1 y 50 operaciones.', {}),
    ([{'operation': 'replace', 'heading': '## Encabezado inexistente', 'markdown': 'Nuevo texto'}],
     'PATCH_TARGET_ERROR', 'El encabezado no existe o es ambiguo.', {'heading': '## Encabezado inexistente', 'matches': 0}),
])
def test_preview_preserves_patch_errors(building_with_us_contract, patches, code, message, details):
    """Fails if literal patch failures lose their code or target diagnostics."""
    before = service.read_contract()

    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'patches': patches})

    assert error.value.code == code
    assert error.value.message == message
    assert error.value.details == details
    assert service.read_contract() == before


@pytest.mark.parametrize('state', ['archived', 'moved'])
def test_publication_refuses_an_inactive_mirror(initialized_building_with_us_mirror, admin_user, state):
    """Fails if an archived or misplaced document can receive a new contract revision."""
    mirror = initialized_building_with_us_mirror
    another_folder = DocumentFolder.objects.create(name='Archivo manual')
    updates = {'archived': {'is_archived': True}, 'moved': {'folder_id': another_folder.pk}}
    Document.objects.filter(pk=mirror.document_id).update(**updates[state])
    before = service.read_contract()
    pdf = bytes(mirror.pdf_content)

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(contract_update(before), actor=admin_user)
    mirror.refresh_from_db()

    assert error.value.code == 'MIRROR_SYNC_FAILED'
    assert error.value.details == {'stage': 'mirror', 'applied': False}
    assert service.read_contract() == before
    assert bytes(mirror.pdf_content) == pdf
    assert BuildingWithUsContractRevision.objects.count() == 1
    assert mirror.document.document_notes.count() == 2


def test_initialization_preview_rejects_a_disallowed_folder(building_with_us_contract_folder):
    """Fails if preview promises initialization in an archived internal folder."""
    folder = building_with_us_contract_folder
    folder.is_archived = True
    folder.save(update_fields=['is_archived'])

    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_initialization(folder.pk)

    assert error.value.code == 'FOLDER_NOT_ALLOWED'
    assert error.value.message == 'Elige una carpeta interna, activa y manual llamada Contratos.'
    assert BuildingWithUsContractMirror.objects.count() == 0


def test_initialization_rechecks_the_preview_folder(building_with_us_contract_folder, admin_user):
    """Fails if initialization accepts a folder changed after its dependency preview."""
    folder = building_with_us_contract_folder
    expected = service.prepare_initialization(folder.pk)['resource_etags']
    folder.name = 'Otro destino'
    folder.save(update_fields=['name', 'updated_at'])

    with pytest.raises(BuildingWithUsError) as error:
        service.initialize_mirror(folder.pk, actor=admin_user, expected_etags=expected)

    assert error.value.code == 'STALE_VERSION'
    assert error.value.message == 'El contrato, su espejo o la carpeta cambió desde la vista previa.'
    assert BuildingWithUsContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0


def test_resource_etags_identifies_a_deleted_folder(building_with_us_contract_folder):
    """Fails if a deleted preview dependency cannot be identified as missing."""
    folder_id = building_with_us_contract_folder.pk
    before = service.resource_etags({'folder_id': folder_id})
    building_with_us_contract_folder.delete()

    resources = service.resource_etags({'folder_id': folder_id})

    assert resources == {**before, 'folder': 'none'}


@pytest.mark.parametrize('state', ['archived', 'empty_pdf', 'invalid_pdf'])
def test_initialization_repairs_an_outdated_artifact(initialized_building_with_us_mirror, admin_user, state):
    """Fails if explicit resynchronization leaves a damaged mirror unusable."""
    mirror = initialized_building_with_us_mirror
    updates = {'archived': {'is_archived': True}, 'empty_pdf': {}, 'invalid_pdf': {}}
    Document.objects.filter(pk=mirror.document_id).update(**updates[state])
    pdfs = {'archived': bytes(mirror.pdf_content), 'empty_pdf': b'', 'invalid_pdf': b'not a PDF'}
    mirror.pdf_content = pdfs[state]
    mirror.save(update_fields=['pdf_content'])
    preview = service.prepare_initialization(mirror.document.folder_id)

    result = service.initialize_mirror(mirror.document.folder_id, actor=admin_user, expected_etags=preview['resource_etags'])
    mirror.refresh_from_db()
    mirror.document.refresh_from_db()

    assert preview['outcome'] == 'resync'
    assert preview['mirror']['status'] == 'out_of_sync'
    assert result['outcome'] == 'resync'
    assert result['mirror']['status'] == 'synchronized'
    assert bytes(mirror.pdf_content).startswith(b'%PDF-')
    assert mirror.document.is_archived is False
    assert BuildingWithUsContractRevision.objects.count() == 1


def test_initialization_rolls_back_a_pending_note_failure(building_with_us_contract_folder, admin_user, monkeypatch):
    """Fails if failure of the second initialization note leaves a partial mirror."""
    note_writer = Mock(wraps=service.create_note, side_effect=[DEFAULT, RuntimeError('Note store unavailable')])
    monkeypatch.setattr(service, 'create_note', note_writer)

    with pytest.raises(BuildingWithUsError) as error:
        service.initialize_mirror(building_with_us_contract_folder.pk, actor=admin_user)

    assert error.value.code == 'MIRROR_SYNC_FAILED'
    assert error.value.details == {'stage': 'private_note', 'applied': False}
    assert BuildingWithUsContractMirror.objects.count() == 0
    assert Document.objects.filter(title=service.CONTRACT_TITLE).count() == 0
    assert DocumentNote.objects.filter(title='Contrato Building with Us — versión 1').count() == 0
    note_writer.assert_called()


@pytest.mark.parametrize('pdf', [None, b'not a PDF'])
def test_current_pdf_rejects_an_invalid_render(building_with_us_contract, monkeypatch, pdf):
    """Fails if invalid renderer output is returned as a downloadable contract."""
    renderer = Mock(return_value=pdf)
    monkeypatch.setattr(service.DocumentPdfService, 'generate_from_markdown', renderer)

    with pytest.raises(BuildingWithUsError) as error:
        service.current_pdf()

    assert error.value.code == 'PDF_RENDER_FAILED'
    assert error.value.message == 'El PDF vigente no está disponible.'
    assert BuildingWithUsContractMirror.objects.count() == 0
    renderer.assert_called_once()


@pytest.mark.parametrize('pdf', [None, b'not a PDF'])
def test_current_pdf_rejects_an_invalid_watermark(building_with_us_contract, monkeypatch, pdf):
    """Fails if watermark corruption is returned as a valid private PDF."""
    watermark = Mock(return_value=pdf)
    monkeypatch.setattr(service, 'add_watermark_to_pdf', watermark)

    with pytest.raises(BuildingWithUsError) as error:
        service.current_pdf()

    assert error.value.code == 'PDF_RENDER_FAILED'
    assert error.value.message == 'El PDF vigente no está disponible.'
    assert BuildingWithUsContractMirror.objects.count() == 0
    watermark.assert_called_once()
