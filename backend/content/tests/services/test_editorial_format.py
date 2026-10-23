"""Behavior tests for the shared editorial-format grammar."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from rest_framework.exceptions import ValidationError

from content.services.editorial_format import (
    plain_text,
    parse_html,
    render_source,
    style_properties,
    validate_formats,
    validate_nested_formats,
)


FIXTURE_PATH = Path(__file__).parents[4] / 'docs' / 'fixtures' / 'editorial-format.json'
with FIXTURE_PATH.open(encoding='utf-8') as fixture_file:
    EDITORIAL_CASES = json.load(fixture_file)


@pytest.mark.parametrize('case', EDITORIAL_CASES, ids=lambda case: case['name'])
def test_shared_editorial_corpus_preserves_text_and_supported_markup(case):
    """Falla si un perfil Python deja de representar el contenido acordado con el editor Vue."""
    format_name = 'whatsapp_v1' if case['profile'] == 'whatsapp' else 'markdown_html_v1'

    rendered = render_source(case['source'], format=format_name)

    assert plain_text(case['source'], format=format_name) == case['expected_text']
    assert [fragment for fragment in case['expected_fragments'] if fragment not in rendered] == []


def test_render_source_preserves_markdown_table_structure():
    """Falla si una tabla Markdown deja de conservar cabecera, filas o columnas."""
    source = '| Servicio | Valor |\n| --- | --- |\n| Diseño | $100 |'

    rendered = render_source(source, format='markdown')

    assert rendered == (
        '<table>\n<thead>\n<tr>\n<th>Servicio</th>\n<th>Valor</th>\n'
        '</tr>\n</thead>\n<tbody>\n<tr>\n<td>Diseño</td>\n<td>$100</td>\n'
        '</tr>\n</tbody>\n</table>\n'
    )


def test_render_source_preserves_tag_scoped_inline_formatting():
    """Falla si el renderizado elimina los estilos que puede producir la barra editorial."""
    source = (
        '<p style="text-align:justify"><span style="color:#ff0000">'
        '<strong>Oferta</strong></span> <mark style="background-color:yellow">'
        'vigente</mark></p>'
    )

    root = parse_html(render_source(source))

    assert style_properties(root.find('.//p').attrib['style']) == {'text-align': 'justify'}
    assert style_properties(root.find('.//span').attrib['style']) == {
        'color': 'rgb(255, 0, 0)',
    }
    assert style_properties(root.find('.//mark').attrib['style']) == {
        'background-color': 'rgb(255, 255, 0)',
    }


def test_render_source_rejects_style_on_wrong_editorial_tag():
    """Falla si un color de texto puede aplicarse a un párrafo fuera del contrato visual."""
    source = '<p style="color:#ff0000">Oferta</p>'

    with pytest.raises(ValidationError, match='Atributo editorial no permitido: style'):
        render_source(source)


def test_render_source_rejects_legacy_highlight_data_attribute():
    """Falla si persiste el atributo de resaltado que el editor ya no puede reconstruir."""
    source = '<mark data-color="yellow">Oferta</mark>'

    with pytest.raises(ValidationError, match='Atributo editorial no permitido: data-color'):
        render_source(source)


def test_render_source_preserves_zero_based_ordered_list_start():
    """Falla si una lista ordenada válida que inicia en cero se rechaza o se renumera."""
    source = '<ol start="0"><li>Primero</li></ol>'

    rendered = render_source(source)

    assert 'start="0"' in rendered


def test_render_source_rejects_script_link_protocol():
    """Falla si un enlace javascript codificado puede persistirse como contenido editorial."""
    source = '<a href="jav&#x61;script:alert(1)">Abrir</a>'

    with pytest.raises(ValidationError, match='Atributo editorial no permitido: href'):
        render_source(source)


def test_render_source_rejects_executable_css():
    """Falla si un estilo con URL ejecutable pasa la lista permitida de estilos."""
    source = '<p style="background-image:url(javascript:alert(1))">Oferta</p>'

    with pytest.raises(ValidationError, match='Atributo editorial no permitido: style'):
        render_source(source)


def test_render_source_keeps_markdown_table_literal_for_whatsapp_profile():
    """Falla si una sintaxis de tabla de WhatsApp se transforma en una estructura que el canal no representa."""
    source = '| A | B |\n| --- | --- |\n| 1 | 2 |'

    rendered = render_source(source, format='whatsapp_v1')

    assert '<table>' not in rendered
    assert plain_text(source, format='whatsapp_v1') == source


def test_render_source_escapes_historical_plain_html():
    """Falla si texto plano histórico se interpreta como HTML al previsualizarlo."""
    source = '<strong>literal</strong>\nsegunda línea'

    rendered = render_source(source, format='plain')

    assert rendered == '<p>&lt;strong&gt;literal&lt;/strong&gt;<br>segunda línea</p>'


def test_plain_text_discards_executable_historical_markup():
    """Falla si una vista de texto plano expone contenido de una etiqueta script histórica."""
    source = '<p>Resumen</p><script>alert("secret")</script><p>Final</p>'

    rendered = plain_text(source)

    assert rendered == 'Resumen\n\nFinal'


def test_style_properties_accepts_only_declared_visual_properties():
    """Falla si el parser pierde color o alineación que la barra editorial puede producir."""
    properties = style_properties('color: rgb(12, 34, 56); text-align: justify')

    assert properties == {
        'color': 'rgb(12, 34, 56)',
        'text-align': 'justify',
    }


def test_validate_formats_resolves_escaped_nested_json_pointer():
    """Falla si un formato no puede dirigirse a una clave anidada con barra literal."""
    values = {'content_json': {'sections': {'intro/body': '**Oferta**'}}}
    formats = {'/content_json/sections/intro~1body': 'markdown'}

    validated = validate_formats('proposalsection', values, formats)

    assert validated == formats


def test_validate_formats_rejects_pointer_outside_model_editorial_roots():
    """Falla si metadatos de formato pueden apuntar a un campo no editorial del modelo."""
    values = {'content': 'Mensaje'}

    with pytest.raises(ValidationError) as error:
        validate_formats('communicationmessage', values, {'/subject': 'markdown'})

    assert error.value.detail == {
        'text_formats': 'Campo o formato no permitido: /subject.'
    }


def test_validate_formats_rejects_missing_nested_pointer():
    """Falla si un perfil de formato queda ligado silenciosamente a una ruta obsoleta."""
    values = {'content_json': {'sections': []}}

    with pytest.raises(ValidationError) as error:
        validate_formats(
            'proposalsection',
            values,
            {'/content_json/sections/0/body': 'markdown'},
        )

    assert error.value.detail == {
        'text_formats': 'El campo ya no existe: /content_json/sections/0/body.'
    }


def test_validate_formats_does_not_mutate_preview_inputs():
    """Falla si validar formatos modifica el contenido o metadatos entregados por una previsualización."""
    values = {'content': '<p>Mensaje <strong>vigente</strong></p>'}
    formats = {'/content': 'markdown_html_v1'}
    original_values = deepcopy(values)
    original_formats = deepcopy(formats)

    validate_formats('communicationmessage', values, formats)

    assert values == original_values
    assert formats == original_formats


def test_validate_nested_formats_keeps_valid_nested_editorial_values_unchanged():
    """Falla si validar perfiles dentro de JSON altera la estructura que el módulo ya guarda."""
    value = {
        'summary': '**Alcance aprobado**',
        'text_formats': {'/summary': 'markdown'},
        'sections': [{
            'body': '*Confirmado*',
            'text_formats': {'/body': 'whatsapp_v1'},
        }],
    }
    original = deepcopy(value)

    validated = validate_nested_formats(value)

    assert validated is value
    assert value == original


def test_validate_nested_formats_rejects_non_text_pointer_target():
    """Falla si un perfil anidado puede declararse sobre un valor que no es contenido textual."""
    value = {
        'metadata': {'version': 3},
        'text_formats': {'/metadata/version': 'markdown'},
    }

    with pytest.raises(ValidationError, match='texto'):
        validate_nested_formats(value)
