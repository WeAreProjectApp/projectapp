"""Presentation service failures preserve the deployed revision history."""
import pytest

from content.models import BuildingWithUsProgram, BuildingWithUsProgramRevision
from content.services import building_with_us_contract_service as contract_service
from content.services import building_with_us_program_service as service
from content.services.building_with_us_content import BuildingWithUsError
from content.tests.building_with_us_fixtures import hero_update

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('history_service', [service, contract_service], ids=['program', 'contract'])
@pytest.mark.parametrize('arguments', [
    {'offset': -1}, {'offset': '0'}, {'offset': False},
    {'limit': 0}, {'limit': 51}, {'limit': '1'}, {'limit': True},
    {'include_content': 1},
])
def test_history_rejects_invalid_arguments(history_service, arguments):
    """Fails if pagination coercion accepts invalid limits, offsets or content flags."""
    with pytest.raises(BuildingWithUsError) as error:
        history_service.list_versions(**arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Usa offset >= 0, limit entre 1 y 50 e include_content booleano.'


@pytest.mark.parametrize('arguments', [None, {'unexpected': True}])
def test_preview_rejects_unknown_arguments(building_with_us_program, arguments):
    """Fails if unknown preview arguments escape the service's structured validation."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update(arguments)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Hay argumentos desconocidos.'
    assert BuildingWithUsProgramRevision.objects.count() == 1


@pytest.mark.parametrize('sections', [None, {}])
def test_preview_requires_sections(building_with_us_program, sections):
    """Fails if a preview can omit all known presentation sections."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'sections': sections})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Incluye al menos una sección conocida.'
    assert error.value.details == {'path': 'sections'}


@pytest.mark.parametrize('translations', [None, {'es': {}}, {'en': {}}])
def test_preview_requires_both_languages(building_with_us_program, translations):
    """Fails if a partial translation can replace a bilingual section."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'sections': {'hero': translations}})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Cada sección requiere es y en.'
    assert error.value.details == {'path': 'hero'}


@pytest.mark.parametrize('version_id', [None, True, 0, '1'])
def test_restore_requires_a_positive_version_id(building_with_us_program, version_id):
    """Fails if restoration coerces invalid version identifiers into historical rows."""
    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'version_id': version_id}, restore=True)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'version_id debe ser un entero positivo.'
    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_restore_requires_an_existing_revision(building_with_us_program):
    """Fails if restoring a missing revision raises an internal lookup error."""
    missing_id = building_with_us_program.current_revision_id + 1000

    with pytest.raises(BuildingWithUsError) as error:
        service.prepare_update({'version_id': missing_id}, restore=True)

    assert error.value.code == 'NOT_FOUND'
    assert error.value.message == 'La versión no existe.'
    assert BuildingWithUsProgramRevision.objects.count() == 1


@pytest.mark.parametrize('note', [None, '   ', 'x' * 4001])
def test_publication_rejects_invalid_change_notes(building_with_us_program, note):
    """Fails if publication accepts a missing, blank or oversized audit explanation."""
    arguments = {**hero_update(service.read_program()), 'change_note': note}

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'change_note debe explicar el cambio (entre 1 y 4000 caracteres).'
    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_public_serialization_rejects_an_unsupported_language():
    """Fails if an unsupported string locale silently selects a valid translation."""
    with pytest.raises(BuildingWithUsError) as error:
        service.serialize_public_program('fr')

    assert error.value.code == 'INVALID_LANGUAGE'
    assert error.value.message == 'Usa es o en.'


def test_read_requires_the_seeded_program(building_with_us_program):
    """Fails if a missing singleton is reported as an internal database error."""
    BuildingWithUsProgram.objects.filter(pk=building_with_us_program.pk).delete()

    with pytest.raises(BuildingWithUsError) as error:
        service.read_program()

    assert error.value.code == 'NOT_FOUND'
    assert error.value.message == 'La presentación no está configurada.'


def test_console_publication_records_its_author(building_with_us_program):
    """Fails if console publications lose their explicit author provenance."""
    result = service.apply_update(hero_update(service.read_program()), actor=None)
    revision = BuildingWithUsProgramRevision.objects.get(pk=result['version_id'])

    assert revision.author_label == 'Consola'
    assert revision.author_id is None
    assert revision.credential_id is None
