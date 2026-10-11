"""Validation and optimistic preconditions for the private cell contract writer."""
import pytest

from content.models import BuildingOnDemandContractMirror, BuildingOnDemandContractRevision
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(('markdown', 'code'), [
    (None, 'VALIDATION_ERROR'), ('', 'VALIDATION_ERROR'), ('Texto sin título', 'VALIDATION_ERROR'),
    ('# Contrato\n' + 'x' * 250000, 'VALIDATION_ERROR'),
    ('# Contrato\n\n{party_name}', 'PLACEHOLDER_NOT_SUPPORTED'),
])
def test_invalid_markdown_cannot_reach_a_preview(building_on_demand_contract, markdown, code):
    """Fails if invalid titles, oversized text or unsupported placeholders enter an edit."""
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update({'markdown': markdown})

    assert rejected.value.code == code
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


@pytest.mark.parametrize('arguments', [None, {'unexpected': True}])
def test_undeclared_preview_arguments_are_rejected(building_on_demand_contract, arguments):
    """Fails if the editing contract silently accepts unsupported argument shapes."""
    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update(arguments)

    assert (rejected.value.code, rejected.value.message) == ('VALIDATION_ERROR', 'Hay argumentos desconocidos.')
    assert BuildingOnDemandContractRevision.objects.count() == 1


@pytest.mark.parametrize(('arguments', 'restore'), [
    ({}, False), ({'markdown': '# Contrato', 'patches': []}, False), ({}, True),
])
def test_preview_requires_one_edit_source(building_on_demand_contract, arguments, restore):
    """Fails if missing or ambiguous content can pass a contract preparation step."""
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update(arguments, restore=restore)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert 'exactamente markdown o patches' in rejected.value.message
    assert service.read_contract() == before


@pytest.mark.parametrize('version_id', [True, 0, '1'])
def test_restore_refuses_nonpositive_or_coerced_ids(building_on_demand_contract, version_id):
    """Fails if restoration treats booleans, strings or zero as stored revision ids."""
    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update({'version_id': version_id}, restore=True)

    assert (rejected.value.code, rejected.value.message) == ('VALIDATION_ERROR', 'version_id debe ser un entero positivo.')
    assert BuildingOnDemandContractRevision.objects.count() == 1
    assert service.mirror_status()['status'] == 'not_initialized'


def test_restore_reports_a_missing_revision(building_on_demand_contract):
    """Fails if a missing historical contract is restored or reported as an internal failure."""
    missing_id = building_on_demand_contract.current_revision_id + 1000

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update({'version_id': missing_id}, restore=True)

    assert (rejected.value.code, rejected.value.message) == ('NOT_FOUND', 'La versión no existe.')
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_write_requires_if_match_before_initializing(pinned_contracts_folder, admin_user):
    """Fails if omission of the revision precondition creates a mirror or new text."""
    before = service.read_contract()
    arguments = contract_update(before)
    arguments.pop('if_match')

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user)

    assert (rejected.value.code, rejected.value.message) == ('PRECONDITION_REQUIRED', 'if_match es obligatorio.')
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_write_rejects_a_stale_contract_etag(pinned_contracts_folder, admin_user):
    """Fails if an old contract precondition can create a revision or Gestor mirror."""
    before = service.read_contract()
    arguments = {**contract_update(before), 'if_match': 'stale'}

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user)

    assert rejected.value.code == 'STALE_VERSION'
    assert rejected.value.details == {'current_etag': before['etag']}
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


@pytest.mark.parametrize('note', [None, '   ', 'x' * 4001])
def test_write_requires_a_usable_change_note(pinned_contracts_folder, admin_user, note):
    """Fails if an edit without a valid audit explanation creates transactional artifacts."""
    before = service.read_contract()
    arguments = {**contract_update(before), 'change_note': note}

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.apply_update(arguments, actor=admin_user)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.message == 'change_note debe explicar el cambio (entre 1 y 4000 caracteres).'
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_patch_target_error_retains_its_diagnostics(building_on_demand_contract):
    """Fails if a missing literal patch heading loses its structured target information."""
    before = service.read_contract()
    arguments = {'patches': [{
        'operation': 'replace', 'heading': '## Encabezado inexistente', 'markdown': 'Nuevo texto',
    }]}

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update(arguments)

    assert rejected.value.code == 'PATCH_TARGET_ERROR'
    assert rejected.value.details == {'heading': '## Encabezado inexistente', 'matches': 0}
    assert service.read_contract() == before
