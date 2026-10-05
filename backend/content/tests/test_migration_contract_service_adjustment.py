"""The default contract follows commercial renewal terms without losing edits."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ContractTemplate
from content.services.contract_pdf_service import (
    render_default_contract_draft_markdown,
)

pytestmark = pytest.mark.django_db
migration = import_module(
    'content.migrations.0255_update_contract_service_adjustment',
)
legacy_migration = import_module(
    'content.migrations.0179_update_default_contract_template_v6',
)
LEGACY_CLAUSES = legacy_migration.HOSTING_SERVICE_CLAUSES.replace(
    'Documento Propuesta de Negocio', 'Documento Propuesta Comercial',
)


@pytest.fixture
def legacy_template():
    return ContractTemplate.objects.create(
        name='Contrato con condiciones anteriores',
        content_markdown=LEGACY_CLAUSES,
        is_default=True,
    )


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


def test_seeded_contract_renders_the_minimum_adjustment_terms():
    _, markdown = render_default_contract_draft_markdown()

    assert 'Condiciones Mínimas de Reajuste del Valor del Servicio' in markdown
    assert 'Como base mínima de reajuste' in markdown
    assert 'salario mínimo mensual legal vigente (SMMLV)' in markdown
    assert 'Índice de Precios al Consumidor (IPC) certificada por el DANE' in markdown
    assert 'Documento Propuesta de Negocio' not in markdown


def test_forward_defers_adjustment_timing_to_the_proposal(
    legacy_template, schema_editor,
):
    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    markdown = legacy_template.content_markdown
    assert 'se reajustará automáticamente cada primero (1.º) de enero' not in markdown
    assert 'La periodicidad de pago, la fecha del primer reajuste' in markdown
    assert 'Documento Propuesta Comercial aceptado por las partes' in markdown
    assert 'sin duplicarse por razón de la periodicidad de facturación' in markdown


def test_forward_preserves_other_contract_clauses(legacy_template, schema_editor):
    prefix, suffix = LEGACY_CLAUSES.split(migration.OLD_PARAGRAPH)
    legacy_template.content_markdown = f'Nota particular.\n\n{LEGACY_CLAUSES}'
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    actual_prefix, actual_suffix = legacy_template.content_markdown.split(
        migration.NEW_PARAGRAPH,
    )
    assert actual_prefix == f'Nota particular.\n\n{prefix}'
    assert actual_suffix == suffix


def test_forward_preserves_non_default_templates(legacy_template, schema_editor):
    other_template = ContractTemplate.objects.create(
        name='Contrato alternativo',
        content_markdown=LEGACY_CLAUSES,
    )

    migration.update_default_template(apps, schema_editor)

    other_template.refresh_from_db()
    assert other_template.content_markdown == LEGACY_CLAUSES


def test_forward_preserves_a_custom_adjustment_clause(
    legacy_template, schema_editor, caplog,
):
    custom_markdown = LEGACY_CLAUSES.replace(
        'cada primero (1.º) de enero', 'cada aniversario del servicio',
    )
    legacy_template.content_markdown = custom_markdown
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == custom_markdown
    assert 'preserving its custom wording' in caplog.text


def test_forward_is_idempotent(legacy_template, schema_editor):
    migration.update_default_template(apps, schema_editor)
    legacy_template.refresh_from_db()
    first_result = legacy_template.content_markdown

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == first_result


def test_forward_does_not_create_a_missing_default(schema_editor):
    ContractTemplate.objects.update(is_default=False)

    migration.update_default_template(apps, schema_editor)

    assert ContractTemplate.get_default() is None


def test_reverse_restores_the_previous_wording(legacy_template, schema_editor):
    migration.update_default_template(apps, schema_editor)

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == LEGACY_CLAUSES


def test_reverse_preserves_later_manual_edits(legacy_template, schema_editor):
    migration.update_default_template(apps, schema_editor)
    legacy_template.refresh_from_db()
    custom_markdown = legacy_template.content_markdown.replace(
        'Como base mínima de reajuste', 'Como base de reajuste negociada',
    )
    legacy_template.content_markdown = custom_markdown
    legacy_template.save(update_fields=['content_markdown'])

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == custom_markdown
