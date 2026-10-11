"""Bounded history reads and audit inputs for cell contract synchronization."""
import pytest

from content.models import BuildingOnDemandContract, BuildingOnDemandContractMirror, BuildingOnDemandContractRevision
from content.services import building_on_demand_contract_service as service
from content.services.building_on_demand_content import BuildingOnDemandError
from content.tests.building_on_demand_fixtures import contract_update

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('arguments', [
    {'offset': True}, {'offset': -1}, {'limit': True}, {'limit': 0},
    {'limit': 51}, {'limit': '1'}, {'include_content': 1}, {'include_content': 'false'},
])
def test_history_rejects_unbounded_or_coerced_queries(building_on_demand_contract, arguments):
    """Fails if history accepts invalid pagination or a truthy substitute for include_content."""
    with pytest.raises(BuildingOnDemandError) as rejected:
        service.list_versions(**arguments)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.message == 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.'
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_history_returns_an_empty_page_past_its_end(building_on_demand_contract):
    """Fails if pagination beyond the last contract revision loses the total or raises."""
    result = service.list_versions(offset=10)

    assert result == {'total': 1, 'versions': []}


def test_read_reports_an_unconfigured_contract(building_on_demand_contract):
    """Fails if a missing singleton escapes as a model error rather than a domain 404."""
    BuildingOnDemandContract.objects.filter(pk=building_on_demand_contract.pk).delete()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.read_contract()

    assert (rejected.value.code, rejected.value.message) == ('NOT_FOUND', 'El contrato no está configurado.')
    assert BuildingOnDemandContractRevision.objects.count() == 1


def test_patch_preview_rejects_an_empty_operation_list(building_on_demand_contract):
    """Fails if an empty literal patch list silently passes as a meaningful edit."""
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update({'patches': []})

    assert (rejected.value.code, rejected.value.message) == ('VALIDATION_ERROR', 'patches debe contener entre 1 y 50 operaciones.')
    assert service.read_contract() == before


def test_matching_preview_requires_a_revision_precondition(pinned_contracts_folder):
    """Fails if require_match preparation omits if_match before transaction execution."""
    arguments = contract_update(service.read_contract())
    arguments.pop('if_match')

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.prepare_update(arguments, require_match=True)

    assert rejected.value.code == 'PRECONDITION_REQUIRED'
    assert BuildingOnDemandContractMirror.objects.count() == 0


@pytest.mark.parametrize('note', [False, '   ', 'x' * 4001])
def test_sync_rejects_invalid_audit_notes(pinned_contracts_folder, admin_user, note):
    """Fails if synchronization accepts empty, oversized or non-text private explanations."""
    before = service.read_contract()

    with pytest.raises(BuildingOnDemandError) as rejected:
        service.sync_mirror(actor=admin_user, note=note)

    assert rejected.value.code == 'VALIDATION_ERROR'
    assert rejected.value.message == 'note debe ser texto no vacío de hasta 4000 caracteres.'
    assert service.read_contract() == before
    assert BuildingOnDemandContractMirror.objects.count() == 0


def test_sync_records_a_trimmed_explicit_note(pinned_contracts_folder, admin_user):
    """Fails if a supplied synchronization explanation is ignored or kept with surrounding spaces."""
    result = service.sync_mirror(actor=admin_user, note='  Inicialización revisada por el operador.  ')
    mirror = BuildingOnDemandContractMirror.objects.get()

    note = mirror.document.document_notes.first()

    assert result['mirror']['status'] == 'synchronized'
    assert '\nInicialización revisada por el operador.\n' in note.content
    assert '\n  Inicialización revisada por el operador.' not in note.content
    assert note.created_by_id == admin_user.pk


def test_console_write_keeps_its_author_provenance(pinned_contracts_folder):
    """Fails if a console contract edit loses its author label or private artifact provenance."""
    result = service.apply_update(contract_update(service.read_contract()), actor=None)
    revision = BuildingOnDemandContractRevision.objects.get(pk=result['version_id'])
    mirror = BuildingOnDemandContractMirror.objects.get()

    assert (revision.author_id, revision.author_label) == (None, 'Consola')
    assert mirror.document.created_by_id is None
    assert mirror.document.document_notes.first().created_by_id is None
    assert result['mirror']['status'] == 'synchronized'
