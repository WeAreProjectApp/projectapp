"""Versioned Consulting presentation behavior and bounded database reads."""
from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from content.models import ConsultingProgramRevision
from content.services import consulting_program_service as service
from content.services.consulting_content import ConsultingError, validate_content
from content.tests.consulting_fixtures import (
    changed_consulting_program, consulting_program, hero_update,
)

pytestmark = pytest.mark.django_db


def _html_hero(snapshot):
    sections = {'hero': {lang: deepcopy(snapshot['content'][lang]['hero']) for lang in ('es', 'en')}}
    sections['hero']['es']['title'] = '<b>Oferta insegura</b>'
    return sections


def _unknown_section(snapshot):
    return {'unexpected': {lang: deepcopy(snapshot['content'][lang]['hero']) for lang in ('es', 'en')}}


def _short_areas(snapshot):
    sections = {'areas': {lang: deepcopy(snapshot['content'][lang]['areas']) for lang in ('es', 'en')}}
    sections['areas']['en']['items'].pop()
    return sections


def _short_impact(snapshot):
    sections = {'impact': {lang: deepcopy(snapshot['content'][lang]['impact']) for lang in ('es', 'en')}}
    sections['impact']['es']['items'].pop()
    return sections


def _misaligned_area_ids(snapshot):
    sections = {'areas': {lang: deepcopy(snapshot['content'][lang]['areas']) for lang in ('es', 'en')}}
    sections['areas']['en']['items'][0]['id'] = 'different-area'
    return sections


def test_seeded_program_covers_five_business_areas_and_six_value_paths(consulting_program):
    """Fails if the deployed seed loses the business areas or measurable value paths it sells."""
    content = validate_content(consulting_program.current_revision.content)

    assert consulting_program.current_revision.version == 1
    assert content['es']['hero']['title'] == 'Una empresa más saludable. Tiempo y dinero mejor aprovechados.'
    assert [item['id'] for item in content['es']['areas']['items']] == [
        'economic', 'financial', 'commercial', 'operational', 'administrative',
    ]
    assert [item['id'] for item in content['es']['impact']['items']] == [
        'hours', 'errors', 'collections', 'sales', 'capacity', 'costs',
    ]


@pytest.mark.parametrize('invalid_sections', [
    _html_hero, _unknown_section, _short_areas, _short_impact, _misaligned_area_ids,
], ids=['html', 'unknown-key', 'five-areas', 'six-impact-paths', 'misaligned-ids'])
def test_invalid_content_cannot_create_a_revision(consulting_program, invalid_sections):
    """Fails if invalid HTML, keys, card counts, or bilingual IDs reach public history."""
    before = service.read_program()

    with pytest.raises(ConsultingError):
        service.apply_update({
            'sections': invalid_sections(before), 'if_match': before['etag'],
            'change_note': 'Intento de contenido inválido.',
        }, actor=None)

    assert ConsultingProgramRevision.objects.count() == 1
    assert service.read_program()['version_id'] == before['version_id']


def test_invalid_bilingual_update_preserves_the_seeded_revision(consulting_program):
    """Fails if a partial translation can replace a public section and corrupt the current revision."""
    before = service.read_program()

    with pytest.raises(ConsultingError) as error:
        service.apply_update({
            'sections': {'hero': {'es': before['content']['es']['hero']}},
            'if_match': before['etag'], 'change_note': 'Intento incompleto.',
        }, actor=None)

    assert error.value.details == {'path': 'hero'}
    assert ConsultingProgramRevision.objects.count() == 1
    assert service.read_program()['version_id'] == before['version_id']


def test_publication_appends_history_and_schedules_one_rebuild(consulting_program, admin_user, monkeypatch, django_capture_on_commit_callbacks):
    """Fails if publishing drops untouched copy, skips rebuild, or mutates the seed in place."""
    before = service.read_program()
    rebuilds = []
    monkeypatch.setattr(service, 'schedule_rebuild_after_publish', lambda **kwargs: rebuilds.append(kwargs))

    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        result = service.apply_update(hero_update(before), actor=admin_user)
    after = service.read_program()

    assert result['version'] == 2
    assert after['content']['es']['hero']['title'] == 'Una operación más clara. Decisiones mejor informadas.'
    assert after['content']['en']['areas'] == before['content']['en']['areas']
    assert after['author'] == admin_user.get_username()
    assert len(callbacks) == 1
    assert rebuilds == [{'reason': 'consulting'}]
    assert ConsultingProgramRevision.objects.count() == 2


@pytest.mark.parametrize('operation', ['save', 'delete'])
def test_revisions_cannot_be_changed_or_deleted(consulting_program, operation):
    """Fails if an editorial revision can be overwritten or removed after publication."""
    revision = consulting_program.current_revision
    original = deepcopy(revision.content)
    revision.content['es']['hero']['title'] = 'Cambio prohibido'

    with pytest.raises(ValidationError):
        getattr(revision, operation)()

    assert ConsultingProgramRevision.objects.get(pk=revision.pk).content == original


def test_restore_appends_a_revision_linked_to_its_source(changed_consulting_program, admin_user):
    """Fails if restoring a snapshot destroys provenance or does not reinstate its original content."""
    current = service.read_program()
    result = service.apply_update({
        'version_id': changed_consulting_program['version_id'], 'if_match': current['etag'],
        'change_note': 'Restaurar la presentación inicial.',
    }, actor=admin_user, restore=True)
    restored = ConsultingProgramRevision.objects.get(pk=result['version_id'])

    assert result['version'] == 3
    assert restored.restored_from_id == changed_consulting_program['version_id']
    assert restored.content == changed_consulting_program['content']
    assert service.list_versions()['versions'][0]['restored_from_version'] == 1


def test_stale_or_unversioned_writes_preserve_current_history(consulting_program):
    """Fails if a missing or stale ETag can overwrite a newer public presentation."""
    before = service.read_program()
    missing_match = hero_update(before)
    missing_match.pop('if_match')

    with pytest.raises(ConsultingError) as precondition:
        service.apply_update(missing_match, actor=None)
    with pytest.raises(ConsultingError) as stale:
        service.apply_update({**hero_update(before), 'if_match': 'stale'}, actor=None)

    assert precondition.value.code == 'PRECONDITION_REQUIRED'
    assert stale.value.details == {'current_etag': before['etag']}
    assert ConsultingProgramRevision.objects.count() == 1


def test_public_serialization_uses_one_database_query(consulting_program):
    """Fails if serving the brochure adds a query beyond the program and current revision join."""
    service.serialize_public_program('es')

    with CaptureQueriesContext(connection) as queries:
        payload = service.serialize_public_program('es')

    assert payload['version'] == 1
    assert len(queries) == 1


def test_version_listing_uses_two_database_queries(changed_consulting_program):
    """Fails if reading version metadata creates per-revision queries instead of a bounded history read."""
    service.list_versions(limit=1)

    with CaptureQueriesContext(connection) as queries:
        page = service.list_versions(limit=1)

    assert page['total'] == 2
    assert page['versions'][0]['version'] == 2
    assert len(queries) == 2
