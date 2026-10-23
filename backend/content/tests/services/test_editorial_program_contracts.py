"""Rich editorial metadata in the three closed bilingual program contracts."""

from copy import deepcopy
from functools import partial
from importlib import import_module

import pytest
from django.apps import apps


PROGRAM_CASES = (
    ('building_with_us', '0286_building_with_us_program', 'BuildingWithUsError', 400, 'es.hero'),
    ('consulting', '0300_consulting_program', 'ConsultingError', 600, 'content.es.hero'),
    ('building_on_demand', '0291_building_on_demand_program', 'BuildingOnDemandError', 400, 'es.hero'),
)


@pytest.fixture(params=PROGRAM_CASES, ids=lambda case: case[0])
def program_case(request):
    name, migration, error_class, maximum, path = request.param
    module = import_module(f'content.services.{name}_content')
    seed = import_module(f'content.migrations.{migration}').PROGRAM_V1
    return {
        'name': name, 'module': module, 'source': deepcopy(seed), 'maximum': maximum,
        'error': getattr(module, error_class), 'path': path,
    }


def _formatted_hero(case, source, format_name='markdown_html_v1'):
    content = deepcopy(case['source'])
    content['es']['hero']['subtitle'] = source
    content['es']['hero']['text_formats'] = {'/subtitle': format_name}
    return content


def _program_writer(case):
    service = import_module(f'content.services.{case["name"]}_program_service')
    names = {'building_with_us': 'BuildingWithUsProgramRevision', 'consulting': 'ConsultingProgramRevision', 'building_on_demand': 'BuildingOnDemandProgramRevision'}
    writer = partial(service.apply_operation, 'update_program') if case['name'] == 'building_on_demand' else service.apply_update
    return service, writer, apps.get_model('content', names[case['name']])


def _publication_arguments(snapshot, source, format_name):
    hero = {language: deepcopy(snapshot['content'][language]['hero']) for language in ('es', 'en')}
    hero['es']['subtitle'] = source
    hero['es']['text_formats'] = {'/subtitle': format_name}
    return {'sections': {'hero': hero}, 'if_match': snapshot['etag'], 'change_note': 'Revisar presentación editorial.'}


@pytest.mark.parametrize('format_name', ['markdown', 'markdown_html_v1'])
def test_program_accepts_format_at_visible_length_limit(program_case, format_name):
    """Falla si los delimitadores de formato consumen el límite reservado al texto visible."""
    visible = 'A' * program_case['maximum']
    sources = {
        'markdown': f'**{visible}**',
        'markdown_html_v1': f'<p style="text-align: center"><span style="color: #123456">{visible}</span></p>',
    }
    content = _formatted_hero(program_case, sources[format_name], format_name)

    validated = program_case['module'].validate_content(content)

    assert validated['es']['hero']['subtitle'] == sources[format_name]
    assert validated['es']['hero']['text_formats'] == {'/subtitle': format_name}
    assert validated['en']['hero'] == program_case['source']['en']['hero']


def test_program_keeps_bilingual_metadata_independent(program_case):
    """Falla si exigir alineación bilingüe obliga a compartir estilos o sobrescribe un idioma."""
    content = _formatted_hero(program_case, '**Texto en español**', 'markdown')
    content['en']['hero']['subtitle'] = '<p style="text-align: right"><u>English text</u></p>'
    content['en']['hero']['text_formats'] = {'/subtitle': 'markdown_html_v1'}

    validated = program_case['module'].validate_content(content)

    assert validated['es']['hero']['subtitle'] == '**Texto en español**'
    assert validated['en']['hero']['subtitle'] == '<p style="text-align: right"><u>English text</u></p>'
    assert validated['es']['hero']['text_formats'] == {'/subtitle': 'markdown'}
    assert validated['en']['hero']['text_formats'] == {'/subtitle': 'markdown_html_v1'}


def test_program_accepts_nested_answer_metadata(program_case):
    """Falla si la metadata local de una respuesta dentro de una lista cerrada se pierde al validar."""
    content = deepcopy(program_case['source'])
    content['es']['faq']['items'][0]['answer'] = '<p>Una <strong>respuesta</strong> editorial.</p>'
    content['es']['faq']['items'][0]['text_formats'] = {'/answer': 'markdown_html_v1'}

    validated = program_case['module'].validate_content(content)

    assert validated['es']['faq']['items'][0]['answer'] == '<p>Una <strong>respuesta</strong> editorial.</p>'
    assert validated['es']['faq']['items'][0]['text_formats'] == {'/answer': 'markdown_html_v1'}
    assert validated['en']['faq'] == program_case['source']['en']['faq']


def test_program_rejects_visible_text_above_limit(program_case):
    """Falla si declarar un formato permite eludir el límite de texto público visible."""
    content = _formatted_hero(program_case, '**' + 'A' * (program_case['maximum'] + 1) + '**', 'markdown')

    with pytest.raises(program_case['error']) as error:
        program_case['module'].validate_content(content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': program_case['path'] + '.subtitle'}


def test_program_rejects_format_for_plain_heading(program_case):
    """Falla si la metadata habilita formato en títulos que siguen siendo texto plano."""
    content = deepcopy(program_case['source'])
    content['es']['hero']['text_formats'] = {'/title': 'markdown_html_v1'}

    with pytest.raises(program_case['error']) as error:
        program_case['module'].validate_content(content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': program_case['path'] + '.text_formats'}


def test_program_rejects_unknown_format(program_case):
    """Falla si un formato arbitrario evade el contrato editorial versionado."""
    content = _formatted_hero(program_case, 'Texto editorial', 'html')

    with pytest.raises(program_case['error']) as error:
        program_case['module'].validate_content(content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': program_case['path'] + '.text_formats'}


def test_program_rejects_unsafe_html_without_mutating_source(program_case):
    """Falla si el programa acepta HTML ejecutable o sanitiza destructivamente el borrador original."""
    content = _formatted_hero(program_case, '<p onclick="alert(1)">Texto editorial</p>')
    original = deepcopy(content)

    with pytest.raises(program_case['error']) as error:
        program_case['module'].validate_content(content)

    assert error.value.code == 'VALIDATION_ERROR'
    assert error.value.details == {'path': program_case['path'] + '.text_formats'}
    assert content == original


def test_program_schema_declares_optional_bounded_metadata(program_case):
    """Falla si el esquema MCP obliga a enviar metadata o anuncia un mapa sin límite."""
    schema = program_case['module'].section_json_schema()['properties']['hero']['properties']['es']

    assert 'text_formats' not in schema['required']
    assert schema['properties']['text_formats']['maxProperties'] == 1000
    assert schema['properties']['subtitle']['x-editorial-max-visible-length'] == program_case['maximum']
    assert schema['additionalProperties'] is False


@pytest.mark.django_db
def test_program_failed_publication_keeps_revision(program_case):
    """Falla si un formato prohibido llega a crear una revisión o modifica la presentación vigente."""
    service, writer, revisions = _program_writer(program_case)
    snapshot = service.read_program()
    arguments = _publication_arguments(snapshot, 'Contenido sin formato válido', 'html')

    with pytest.raises(program_case['error']) as error:
        writer(arguments, actor=None)

    assert error.value.code == 'VALIDATION_ERROR'
    assert service.read_program()['version_id'] == snapshot['version_id']
    assert service.read_program()['content'] == snapshot['content']
    assert revisions.objects.count() == 1


@pytest.mark.django_db
def test_program_publication_persists_formatted_source(program_case):
    """Falla si la publicación guarda la proyección plana en lugar de la fuente y su metadata."""
    service, writer, revisions = _program_writer(program_case)
    snapshot = service.read_program()
    source = '<p style="text-align: center"><strong>Presentación aprobada</strong></p>'

    writer(_publication_arguments(snapshot, source, 'markdown_html_v1'), actor=None)
    published = service.read_program()

    assert published['version'] == 2
    assert published['content']['es']['hero']['subtitle'] == source
    assert published['content']['es']['hero']['text_formats'] == {'/subtitle': 'markdown_html_v1'}
    assert published['content']['en']['hero'] == snapshot['content']['en']['hero']
    assert revisions.objects.count() == 2
