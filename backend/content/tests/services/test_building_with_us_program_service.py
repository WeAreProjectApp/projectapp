"""Versioning, strict bilingual validation and commit-bound rebuild requests."""
from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError

from content.models import BuildingWithUsProgramRevision
from content.services import building_with_us_program_service as service
from content.services.building_with_us_content import BuildingWithUsError, validate_content
from content.tests.building_with_us_fixtures import hero_update

pytestmark = pytest.mark.django_db


def test_seeded_presentation_is_valid(building_with_us_program):
    """Fails if the deploy seed cannot be consumed by the current content spec."""
    revision = building_with_us_program.current_revision

    content = validate_content(revision.content)

    assert revision.version == 1
    assert content['es']['hero']['title'] == 'Construye con nosotros. Construimos para ti.'
    assert content['en']['hero']['title'] == 'Build with us. We build for you.'


@pytest.mark.parametrize('mismatch', ['length', 'id', 'months'])
def test_language_mismatch_is_rejected(building_with_us_program, mismatch):
    """Fails if translated periods describe different alliance options."""
    content = deepcopy(building_with_us_program.current_revision.content)
    changes = {'length': content['en']['incubation_periods']['items'][:3],
               'id': [{**content['en']['incubation_periods']['items'][0], 'id': 'different'}, *content['en']['incubation_periods']['items'][1:]],
               'months': [{**content['en']['incubation_periods']['items'][0], 'months': 4}, *content['en']['incubation_periods']['items'][1:]]}
    content['en']['incubation_periods']['items'] = changes[mismatch]

    with pytest.raises(BuildingWithUsError) as error:
        validate_content(content)

    assert error.value.code == 'VALIDATION_ERROR'


@pytest.mark.parametrize('figure', ['%', '$', 'USD'])
def test_public_figures_are_rejected(building_with_us_program, figure):
    """Fails if presentation validation allows public economic figures."""
    content = deepcopy(building_with_us_program.current_revision.content)
    content['es']['participation_models']['items'][0]['summary'] = f'Aporte {figure}'

    with pytest.raises(BuildingWithUsError) as error:
        validate_content(content)

    assert error.value.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
    assert error.value.details == {'path': 'es.participation_models.items[0].summary'}


@pytest.mark.parametrize('unknown', ['section', 'field'])
def test_unknown_content_is_rejected(building_with_us_program, unknown):
    """Fails if updates bypass the presentation spec with undeclared content."""
    arguments = hero_update(service.read_program())
    candidates = {'section': {'unexpected': arguments['sections']['hero']},
                  'field': {'hero': {lang: {**value, 'unexpected': 'Texto'} for lang, value in arguments['sections']['hero'].items()}}}
    arguments['sections'] = candidates[unknown]

    with pytest.raises(BuildingWithUsError):
        service.apply_update(arguments, actor=None)

    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_update_appends_a_revision(building_with_us_program, admin_user, monkeypatch, django_capture_on_commit_callbacks):
    """Fails if publication loses untouched sections or requests multiple rebuilds."""
    before = service.read_program()
    calls = []
    monkeypatch.setattr(service, 'schedule_rebuild_after_publish', lambda **kwargs: calls.append(kwargs))

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = service.apply_update(hero_update(before), actor=admin_user)
    after = service.read_program()

    assert result['version'] == 2
    assert after['content']['es']['hero']['title'] == 'Tu experiencia, un producto con propósito.'
    assert after['content']['en']['origin'] == before['content']['en']['origin']
    assert after['author'] == admin_user.get_username()
    assert len(callbacks) == 1
    assert calls == [{'reason': 'building-with-us'}]
    assert BuildingWithUsProgramRevision.objects.count() == 2


def test_stale_update_preserves_the_current_revision(building_with_us_program):
    """Fails if a stale etag can overwrite presentation history."""
    before = service.read_program()
    arguments = {**hero_update(before), 'if_match': 'stale'}

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'STALE_VERSION'
    assert error.value.details['current_etag'] == before['etag']
    assert service.read_program()['version_id'] == before['version_id']
    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_restore_appends_an_auditable_revision(changed_building_with_us_program, admin_user):
    """Fails if restoring edits history instead of preserving the source revision."""
    original = changed_building_with_us_program
    arguments = {'version_id': original['version_id'], 'if_match': service.read_program()['etag'], 'change_note': 'Restaurar versión inicial.'}

    result = service.apply_update(arguments, actor=admin_user, restore=True)
    restored = BuildingWithUsProgramRevision.objects.get(pk=result['version_id'])

    assert result['version'] == 3
    assert restored.restored_from_id == original['version_id']
    assert restored.content == original['content']
    assert service.list_versions()['versions'][0]['restored_from_version'] == 1


@pytest.mark.parametrize('operation', ['save', 'delete'])
def test_revisions_are_immutable(building_with_us_program, operation):
    """Fails if a stored revision can be rewritten or removed through its model."""
    revision = building_with_us_program.current_revision
    before = deepcopy(revision.content)
    revision.content['es']['hero']['title'] = 'Cambio prohibido'

    with pytest.raises(ValidationError):
        getattr(revision, operation)()

    assert BuildingWithUsProgramRevision.objects.get(pk=revision.pk).content == before


def test_unchanged_publication_keeps_the_revision(building_with_us_program, django_capture_on_commit_callbacks):
    """Fails if identical content creates redundant history or regeneration work."""
    before = service.read_program()
    sections = {'hero': {lang: before['content'][lang]['hero'] for lang in ('es', 'en')}}

    with django_capture_on_commit_callbacks() as callbacks:
        result = service.apply_update({'sections': sections, 'if_match': before['etag'], 'change_note': 'Revisión sin cambios.'}, actor=None)

    assert result == {'applied': True, 'changed': False, 'version': 1}
    assert BuildingWithUsProgramRevision.objects.count() == 1
    assert callbacks == []


def test_update_requires_a_precondition(building_with_us_program):
    """Fails if an unversioned update can publish new content."""
    arguments = hero_update(service.read_program())
    arguments.pop('if_match')

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None)

    assert error.value.code == 'PRECONDITION_REQUIRED'
    assert BuildingWithUsProgramRevision.objects.count() == 1


def test_restore_revalidates_historical_content(changed_building_with_us_program):
    """Fails if legacy content containing a public figure is republished."""
    content = deepcopy(changed_building_with_us_program['content'])
    content['es']['hero']['note'] = 'Importe USD'
    historical = BuildingWithUsProgramRevision.objects.create(version=3, content=content, change_note='Contenido legado inválido.')
    before = service.read_program()

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update({'version_id': historical.pk, 'if_match': before['etag'], 'change_note': 'Intento de restauración.'}, actor=None, restore=True)

    assert error.value.code == 'PUBLIC_FIGURE_NOT_ALLOWED'
    assert service.read_program()['version_id'] == before['version_id']


def test_expected_resources_are_rechecked_under_lock(building_with_us_program):
    """Fails if the transactional writer ignores frozen confirmation etags."""
    arguments = hero_update(service.read_program())

    with pytest.raises(BuildingWithUsError) as error:
        service.apply_update(arguments, actor=None, expected_etags={'program': 'stale'})

    assert error.value.code == 'STALE_VERSION'
    assert BuildingWithUsProgramRevision.objects.count() == 1


@pytest.mark.parametrize('language', [None, ['es']])
def test_public_serialization_rejects_invalid_language_types(language):
    """Fails if unsupported language types raise an internal error instead of validation."""
    with pytest.raises(BuildingWithUsError) as error:
        service.serialize_public_program(language)

    assert error.value.code == 'INVALID_LANGUAGE'
