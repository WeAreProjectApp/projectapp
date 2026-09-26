"""Contract v8 rewrites IP and confidentiality and letters every list, all or nothing."""

import re
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.db import connection
from freezegun import freeze_time

from content.models import ContractTemplate, ProposalDocument
from content.tests.test_migration_contract_ownership import contract_before_update

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0259_update_default_contract_template_v8')
ownership = import_module('content.migrations.0257_update_contract_ownership_and_termination')


def contract_before_v8():
    """The template as shipped after 0257, rebuilt from immutable migrations."""
    markdown = contract_before_update()
    for label, pairs in ownership.PATCH_GROUPS:
        markdown = ownership._apply_group(markdown, pairs, label)
    return markdown


@pytest.fixture
def legacy_template():
    return ContractTemplate.objects.create(
        name='Contrato antes de v8',
        content_markdown=contract_before_v8(),
        is_default=True,
    )


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


def migrated(template, schema_editor):
    migration.update_default_template(apps, schema_editor)
    template.refresh_from_db()
    return template.content_markdown


def test_every_anchor_matches_the_shipped_template_once():
    markdown = contract_before_v8()

    for old, _new in migration.PAIRS:
        assert markdown.count(old) == 1, old[:80]


def test_forward_rewrites_confidentiality_as_mutual_with_non_circumvention(
    legacy_template, schema_editor,
):
    markdown = migrated(legacy_template, schema_editor)

    assert '## CLÁUSULA DÉCIMA PRIMERA — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' in markdown
    assert 'protegen por igual a EL CONTRATANTE y a EL CONTRATISTA' in markdown
    assert 'No usar, explotar, implementar, reproducir ni aprovechar, directa o indirectamente' in markdown
    assert 'alianzas derivados de la oportunidad comercial revelada' in markdown
    assert '### Parágrafo Cuarto — No Circunvención' in markdown
    assert 'inversionistas, empleados, subcontratistas, colaboradores' in markdown


def test_forward_splits_know_how_and_reusable_components(legacy_template, schema_editor):
    markdown = migrated(legacy_template, schema_editor)

    assert '## CLÁUSULA DÉCIMA — PROPIEDAD INTELECTUAL Y DERECHOS PATRIMONIALES' in markdown
    assert '### Parágrafo Segundo — Conocimiento Técnico y Experiencia Acumulada' in markdown
    assert '### Parágrafo Tercero — Componentes Técnicos Reutilizables y Estándares de la Industria' in markdown
    assert '### Parágrafo Quinto — Licencia Temporal de Uso' in markdown
    assert 'no excluye de la cesión las implementaciones originales' not in markdown
    assert 'licencia temporal prevista en el PARÁGRAFO QUINTO de la CLÁUSULA DÉCIMA' in markdown


def test_forward_letters_every_list_and_reference(legacy_template, schema_editor):
    markdown = migrated(legacy_template, schema_editor)

    assert not re.findall(r'^\s*(?:\d+\.|[a-z]{1,4}\)|-) ', markdown, re.MULTILINE)
    assert 'numeral' not in markdown.lower()
    assert 'establecidas en los literales f) y g) de dicho parágrafo' in markdown
    assert '**a) Negociación directa:**' in markdown
    assert '### Parágrafo Segundo — Intereses de Mora' in markdown


def test_forward_keeps_the_24_clause_headings(legacy_template, schema_editor):
    """The public reader numbers clauses by heading position."""
    before = re.findall(r'^## .+$', legacy_template.content_markdown, re.MULTILINE)

    after = re.findall(r'^## .+$', migrated(legacy_template, schema_editor), re.MULTILINE)

    assert len(after) == len(before) == 24


def test_forward_preserves_unrelated_manual_text(legacy_template, schema_editor):
    legacy_template.content_markdown += '\n\nNota particular pactada.'
    legacy_template.save(update_fields=['content_markdown'])

    markdown = migrated(legacy_template, schema_editor)

    assert markdown.endswith('Nota particular pactada.')
    assert 'CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN' in markdown


@pytest.mark.parametrize('old,new', [
    ('13. Inventario y/o manejo de inventarios', '13. Inventario negociado'),
    ('por un periodo de dos (2) años contados', 'por un periodo de tres (3) años contados'),
])
def test_forward_preserves_a_customized_template_whole(
    legacy_template, schema_editor, caplog, old, new,
):
    """One customized section keeps every other section, so references stay consistent."""
    legacy_template.content_markdown = legacy_template.content_markdown.replace(old, new)
    legacy_template.save(update_fields=['content_markdown'])
    previous = legacy_template.content_markdown

    assert migrated(legacy_template, schema_editor) == previous
    assert 'preserving custom or ambiguous provisions' in caplog.text


def test_forward_is_idempotent(legacy_template, schema_editor):
    migrated(legacy_template, schema_editor)
    previous = (legacy_template.content_markdown, legacy_template.updated_at)

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert (legacy_template.content_markdown, legacy_template.updated_at) == previous


def test_forward_does_not_create_a_missing_default(schema_editor):
    ContractTemplate.objects.all().delete()

    migration.update_default_template(apps, schema_editor)

    assert not ContractTemplate.objects.exists()


def test_forward_preserves_non_default_templates(legacy_template, schema_editor):
    other = ContractTemplate.objects.create(
        name='Contrato negociado', content_markdown=legacy_template.content_markdown,
    )
    previous = other.content_markdown

    migration.update_default_template(apps, schema_editor)

    other.refresh_from_db()
    assert other.content_markdown == previous


def test_forward_preserves_generated_contract_snapshot(proposal, legacy_template, schema_editor):
    document = ProposalDocument.objects.create(
        proposal=proposal, document_type='contract', title='Contrato emitido',
        is_generated=True, content_markdown='Contrato histórico v7.',
        file=ContentFile(b'%PDF-1.4\nIssued contract bytes', name='issued-contract.pdf'),
    )

    migration.update_default_template(apps, schema_editor)

    document.refresh_from_db()
    assert document.content_markdown == 'Contrato histórico v7.'
    with document.file.open('rb') as stored:
        assert stored.read() == b'%PDF-1.4\nIssued contract bytes'


def test_forward_refreshes_the_public_template_timestamp(legacy_template, schema_editor):
    with freeze_time('2030-01-02 12:00:00'):
        migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.updated_at.isoformat() == '2030-01-02T12:00:00+00:00'


def test_reverse_restores_the_previous_contract(legacy_template, schema_editor):
    previous = legacy_template.content_markdown
    migration.update_default_template(apps, schema_editor)

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == previous


def test_reverse_preserves_later_negotiated_terms(legacy_template, schema_editor, caplog):
    migrated(legacy_template, schema_editor)
    legacy_template.content_markdown = legacy_template.content_markdown.replace(
        'por el término de dos (2) años', 'por el término de un (1) año',
    )
    legacy_template.save(update_fields=['content_markdown'])
    previous = legacy_template.content_markdown

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == previous
    assert 'preserving custom or ambiguous provisions' in caplog.text
