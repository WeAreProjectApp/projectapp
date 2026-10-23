"""Repeated annotations retain validation and persistence guarantees."""

from copy import deepcopy

import pytest
from rest_framework.exceptions import ValidationError

from content.models import BusinessProposal, ProposalSection
from content.serializers.proposal import ProposalSectionUpdateSerializer
from content.services.editorial_format import validate_nested_formats


FORMAT = 'markdown_html_v1'
SOURCE = '<p><strong>Alcance aprobado</strong></p>'
UNSAFE = '<p style="position:fixed">Contenido prohibido</p>'


@pytest.fixture
def proposal_section(db):
    proposal = BusinessProposal.objects.create(
        title='Validación editorial', client_name='Cliente de prueba',
    )
    return ProposalSection.objects.create(
        proposal=proposal,
        section_type='executive_summary',
        title='Resumen',
        content_json={'paragraphs': ['Texto inicial']},
    )


@pytest.fixture
def repeated_content():
    return {
        'paragraphs': [SOURCE, SOURCE],
        'text_formats': {'/paragraphs/0': FORMAT, '/paragraphs/1': FORMAT},
    }


@pytest.fixture
def many_sources():
    return [
        {'body': f'**Item {index}**', 'text_formats': {'/body': FORMAT}}
        for index in range(1001)
    ]


def test_duplicate_annotations_persist_original_rich_source(proposal_section, repeated_content):
    """Falla si reutilizar una validación altera el contenido o pierde una anotación al guardar."""
    serializer = ProposalSectionUpdateSerializer(
        proposal_section,
        data={
            'content_json': repeated_content,
            'text_formats': {'/content_json/paragraphs/0': FORMAT},
        },
        partial=True,
    )

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    proposal_section.refresh_from_db()

    assert proposal_section.content_json == {
        'paragraphs': [SOURCE, SOURCE],
        'text_formats': {'/paragraphs/0': FORMAT, '/paragraphs/1': FORMAT},
    }
    assert proposal_section.text_formats == {'/content_json/paragraphs/0': FORMAT}


def test_duplicate_annotations_reject_changed_unsafe_source(proposal_section, repeated_content):
    """Falla si validar un texto previo permite guardar otro texto inseguro con el mismo formato."""
    repeated_content['paragraphs'][1] = UNSAFE
    serializer = ProposalSectionUpdateSerializer(
        proposal_section,
        data={
            'content_json': repeated_content,
            'text_formats': {'/content_json/paragraphs/0': FORMAT},
        },
        partial=True,
    )

    assert not serializer.is_valid()
    proposal_section.refresh_from_db()

    assert 'text_formats' in serializer.errors
    assert proposal_section.content_json == {'paragraphs': ['Texto inicial']}
    assert proposal_section.text_formats == {}


def test_reused_source_still_rejects_a_conflicting_annotation():
    """Falla si reconocer un texto previo permite omitir un conflicto de formato en otra ruta."""
    value = {
        'earlier': SOURCE,
        'group': {'body': SOURCE, 'text_formats': {'/body': 'plain'}},
        'text_formats': {'/earlier': FORMAT, '/group/body': FORMAT},
    }
    original = deepcopy(value)

    with pytest.raises(ValidationError) as error:
        validate_nested_formats(value)

    assert error.value.detail == {
        'text_formats': 'Hay formatos contradictorios para el mismo texto.'
    }
    assert value == original


def test_reused_source_still_rejects_a_missing_annotation_target():
    """Falla si una anotación repetida oculta una ruta que ya no existe."""
    value = {
        'body': SOURCE,
        'text_formats': {'/body': FORMAT, '/missing': FORMAT},
    }

    with pytest.raises(ValidationError) as error:
        validate_nested_formats(value)

    assert error.value.detail == {
        'text_formats': 'El campo ya no existe: /missing.'
    }


def test_plain_validation_cannot_authorize_the_same_source_as_rich_html():
    """Falla si aceptar HTML como texto literal permite después tratarlo como formato seguro."""
    value = {
        'literal': UNSAFE,
        'formatted': UNSAFE,
        'text_formats': {'/literal': 'plain', '/formatted': FORMAT},
    }

    with pytest.raises(ValidationError) as error:
        validate_nested_formats(value)

    assert error.value.detail == {
        'text_formats': {
            '/formatted': ['Atributo editorial no permitido: style.'],
        },
    }


def test_validation_accepts_more_distinct_sources_than_the_reuse_capacity(many_sources):
    """Falla si llenar la memoria de reutilización cambia el límite contractual de los documentos."""
    value = {'items': many_sources}

    validated = validate_nested_formats(value)

    assert validated['items'][1000] == {
        'body': '**Item 1000**', 'text_formats': {'/body': FORMAT},
    }
    assert len(validated['items']) == 1001


def test_validation_still_rejects_unsafe_source_after_reuse_capacity(many_sources):
    """Falla si llenar la memoria de reutilización desactiva la validación de las hojas siguientes."""
    value = {'items': many_sources + [
        {'body': UNSAFE, 'text_formats': {'/body': FORMAT}},
    ]}

    with pytest.raises(ValidationError) as error:
        validate_nested_formats(value)

    assert error.value.detail == {
        'text_formats': {
            '/body': ['Atributo editorial no permitido: style.'],
        },
    }
