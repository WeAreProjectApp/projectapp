"""Paragraph Ten reaches both default contracts once, in its place, and rolls back exactly."""

import re
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ContractTemplate
from content.services import contract_variants as variants

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0267_add_provider_dependency_paragraph')
TITLE = 'Dependencia de Proveedores Tecnológicos y de Inteligencia Artificial'
FIELDS = [field for field, *_ in migration.INSERTIONS]
# (text, clause the paragraph closes, clause of the orderly exit it cites, paragraph)
PLACEMENTS = [
    ('content_markdown', 'VIGÉSIMA SEGUNDA', 'VIGÉSIMA CUARTA', migration.FULL_CONTRACT_PARAGRAPH),
    ('service_content_markdown', 'QUINTA', 'SÉPTIMA', migration.SERVICE_CONTRACT_PARAGRAPH),
]


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


@pytest.fixture
def default_template():
    return ContractTemplate.get_default()


def _texts(template):
    template.refresh_from_db()
    return {field: getattr(template, field) for field in FIELDS}


def _clause(text, ordinal):
    """CLÁUSULA *ordinal*, up to the separator before the next clause."""
    start = text.index(f'## CLÁUSULA {ordinal} —')
    end = text.find('\n\n---\n\n## CLÁUSULA', start)
    return text[start:] if end == -1 else text[start:end]


def _paragraph_titles(clause):
    return re.findall(r'^### Parágrafo (\w+) — (.+)$', clause, re.MULTILINE)


@pytest.mark.parametrize(('field', 'ordinal', 'exit_ordinal', 'paragraph'), PLACEMENTS)
def test_paragraph_ten_closes_the_clause_right_after_paragraph_nine(
    default_template, field, ordinal, exit_ordinal, paragraph,
):
    """Fails if the paragraph is missing, repeated, in the wrong version or out of place."""
    text = getattr(default_template, field)
    clause = _clause(text, ordinal)

    assert text.count(TITLE) == 1
    assert clause.endswith(f'\n\n{paragraph}')
    assert _paragraph_titles(clause)[-2:] == [
        ('Noveno', 'Límite de Responsabilidad del Servicio'),
        ('Décimo', TITLE),
    ]


@pytest.mark.parametrize(('field', 'ordinal', 'exit_ordinal', 'paragraph'), PLACEMENTS)
def test_paragraph_ten_cites_the_paragraphs_it_names(
    default_template, field, ordinal, exit_ordinal, paragraph,
):
    """Fails if the paragraph cites attention levels, exclusions or an exit that moved."""
    text = getattr(default_template, field)
    own = dict(_paragraph_titles(_clause(text, ordinal)))
    exit_clause = dict(_paragraph_titles(_clause(text, exit_ordinal)))

    assert 'se suspenderán los niveles de atención del PARÁGRAFO CUARTO' in paragraph
    assert own['Cuarto'] == 'Niveles de Atención'
    assert 'con los PARÁGRAFOS SÉPTIMO y NOVENO de la presente cláusula' in paragraph
    assert own['Séptimo'] == 'Exclusiones, Fuerza Mayor y Caso Fortuito'
    assert own['Noveno'] == 'Límite de Responsabilidad del Servicio'
    assert f'la salida ordenada prevista en el PARÁGRAFO CUARTO de la CLÁUSULA {exit_ordinal}.' in paragraph
    assert exit_clause['Cuarto'] == 'Salida Ordenada'


def test_product_contract_does_not_receive_the_paragraph(default_template):
    """Fails if the service-only paragraph leaks into the software development contract."""
    product = variants.template_markdown(default_template, variants.PRODUCT)

    assert len(re.findall(r'^## CLÁUSULA ', product, re.MULTILINE)) == 20
    assert TITLE not in product
    assert 'EVENTO DE PROVEEDOR' not in product


def test_forward_twice_inserts_the_paragraph_once(default_template, schema_editor):
    """Fails if re-running the migration repeats the paragraph."""
    migrated = _texts(default_template)

    migration.add_provider_dependency_paragraph(apps, schema_editor)

    assert _texts(default_template) == migrated


def test_reverse_removes_only_the_paragraph(default_template, schema_editor):
    """Fails if rolling back leaves the paragraph behind or touches any other text."""
    migrated = _texts(default_template)
    expected = {
        field: migrated[field].replace(f'\n\n{paragraph}', '', 1)
        for field, _end, _next, paragraph in migration.INSERTIONS
    }

    migration.remove_provider_dependency_paragraph(apps, schema_editor)

    assert _texts(default_template) == expected
    assert [TITLE in text for text in expected.values()] == [False, False]


def test_forward_after_reverse_restores_the_migrated_texts(default_template, schema_editor):
    """Fails if the rollback and the migration disagree on where the paragraph goes."""
    migrated = _texts(default_template)
    migration.remove_provider_dependency_paragraph(apps, schema_editor)

    migration.add_provider_dependency_paragraph(apps, schema_editor)

    assert _texts(default_template) == migrated


def test_forward_preserves_a_curated_contract(schema_editor, caplog):
    """Fails if the migration rewrites a default text curated away from the shipped anchor."""
    curated = ContractTemplate.objects.create(
        name='Contrato negociado', content_markdown='Texto negociado.',
        service_content_markdown='Servicio negociado.', is_default=True,
    )

    migration.add_provider_dependency_paragraph(apps, schema_editor)

    assert _texts(curated) == {
        'content_markdown': 'Texto negociado.',
        'service_content_markdown': 'Servicio negociado.',
    }
    assert caplog.text.count('anchor not found') == 2
