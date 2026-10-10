"""Strict section validation with the deployed bilingual presentation."""
from copy import deepcopy

import pytest

from content.services.building_with_us_content import BuildingWithUsError, validate_section

pytestmark = pytest.mark.django_db


@pytest.fixture
def section_content(building_with_us_program):
    def copy_section(key):
        content = building_with_us_program.current_revision.content
        return {lang: deepcopy(content[lang][key]) for lang in ('es', 'en')}

    return copy_section


@pytest.mark.parametrize('value', [None, []])
def test_section_requires_an_object(value):
    """Fails if a non-object section causes an internal error instead of validation."""
    with pytest.raises(BuildingWithUsError) as error:
        validate_section('hero', value)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Debe ser un objeto.'
    assert error.value.details == {'path': 'hero'}


@pytest.mark.parametrize('value', [None, [], ['Industria'] * 9])
def test_section_rejects_invalid_lists(section_content, value):
    """Fails if industry lists accept invalid types or exceed their size bounds."""
    content = section_content('origin')
    content['es']['industries'] = value

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('origin', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'La lista debe tener entre 1 y 8 elementos.'
    assert error.value.details == {'path': 'origin.es.industries'}


@pytest.mark.parametrize('months', [True, '3', 0, 37])
def test_section_rejects_invalid_months(section_content, months):
    """Fails if incubation accepts booleans, strings or months outside its bounds."""
    content = section_content('incubation_periods')
    content['es']['items'][0]['months'] = months

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('incubation_periods', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Usa un entero entre 1 y 36.'
    assert error.value.details == {'path': 'incubation_periods.es.items[0].months'}


@pytest.mark.parametrize('value', [None, 42])
def test_section_requires_text(section_content, value):
    """Fails if titles accept non-text values or raise an unstructured error."""
    content = section_content('hero')
    content['es']['title'] = value

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('hero', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Debe ser texto.'
    assert error.value.details == {'path': 'hero.es.title'}


@pytest.mark.parametrize('value', ['   ', 'x' * 121])
def test_section_rejects_invalid_text_length(section_content, value):
    """Fails if required hero titles accept blank or oversized text."""
    content = section_content('hero')
    content['es']['title'] = value

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('hero', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'El texto es obligatorio y debe respetar la longitud máxima.'
    assert error.value.details == {'path': 'hero.es.title'}


@pytest.mark.parametrize('slug', ['Upper', 'bad id', 'two--hyphens'])
def test_section_rejects_invalid_slugs(section_content, slug):
    """Fails if stable card identifiers stop enforcing the lowercase slug format."""
    content = section_content('incubation_periods')
    content['es']['items'][0]['id'] = slug

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('incubation_periods', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'id debe ser un slug en minúsculas.'
    assert error.value.details == {'path': 'incubation_periods.es.items[0].id'}


def test_section_rejects_duplicate_identifiers(section_content):
    """Fails if two incubation options can share the same stable identifier."""
    content = section_content('incubation_periods')
    content['es']['items'][1]['id'] = content['es']['items'][0]['id']

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('incubation_periods', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'No repitas ids dentro de la lista.'
    assert error.value.details == {'path': 'incubation_periods.es.items'}


def test_section_rejects_an_unknown_key():
    """Fails if section validation accepts a key absent from the presentation spec."""
    with pytest.raises(BuildingWithUsError) as error:
        validate_section('unexpected', {'es': {}, 'en': {}})

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == 'Sección desconocida.'
    assert error.value.details == {'path': 'unexpected'}


@pytest.mark.parametrize(('mismatch', 'path', 'message'), [
    ('length', 'incubation_periods.items', 'Las listas deben tener la misma longitud en ambos idiomas.'),
    ('id', 'incubation_periods.items[0].id', 'Los ids y meses deben coincidir entre idiomas y conservar su orden.'),
    ('months', 'incubation_periods.items[0].months', 'Los ids y meses deben coincidir entre idiomas y conservar su orden.'),
])
def test_section_rejects_translation_mismatches(section_content, mismatch, path, message):
    """Fails if single-section validation permits differently ordered alliance options."""
    content = section_content('incubation_periods')
    first, *remaining = content['en']['items']
    replacements = {
        'length': content['en']['items'][:-1],
        'id': [{**first, 'id': 'different'}, *remaining],
        'months': [{**first, 'months': 36}, *remaining],
    }
    content['en']['items'] = replacements[mismatch]

    with pytest.raises(BuildingWithUsError) as error:
        validate_section('incubation_periods', content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.message == message
    assert error.value.details == {'path': path}


@pytest.mark.parametrize('months', [1, 36])
def test_section_accepts_month_boundaries(section_content, months):
    """Fails if either documented incubation boundary is incorrectly rejected."""
    content = section_content('incubation_periods')
    content['es']['items'][0]['months'] = months
    content['en']['items'][0]['months'] = months

    validated = validate_section('incubation_periods', content)

    assert validated == content
    assert validated['es']['items'][0]['months'] == months


def test_section_trims_text(section_content):
    """Fails if otherwise valid section text retains surrounding whitespace."""
    content = section_content('hero')
    content['es']['title'] = '  Un producto con propósito.  '

    validated = validate_section('hero', content)

    assert validated['es']['title'] == 'Un producto con propósito.'
    assert validated['en'] == content['en']
