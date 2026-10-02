"""The template migration moves service economics into the service contract."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ContractTemplate

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0276_service_contract_economic_conditions')


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


@pytest.fixture
def default_template():
    return ContractTemplate.objects.create(
        name='Contrato de servicio vigente',
        is_default=True,
        content_markdown='Contrato de producto sin términos de hosting.',
        service_content_markdown=(
            f'{migration.PRICE_HEADING}\n\n'
            'El valor, la periodicidad y las condiciones económicas del servicio se definen en el Documento Propuesta Comercial o en el documento que las partes suscriban para el efecto.\n\n'
            'conforme a la periodicidad definida en el Documento Propuesta Comercial, sea esta mensual, trimestral, semestral, anual u otra\n\n'
            'El presente contrato, junto con el Documento Propuesta Comercial en lo relativo al servicio de hosting, mantenimiento y soporte, rige la relación.\n\n'
            'la periodicidad de pago pactada en el Documento Propuesta Comercial\n\n'
            'la periodicidad definida en el Documento Propuesta Comercial\n\n'
            'Documento Propuesta Comercial aceptado por las partes\n\n'
            'El presente contrato, junto con el Documento Propuesta Comercial en lo relativo al servicio de hosting, mantenimiento y soporte, rige la relación.'
        ),
    )


def test_forward_inserts_dynamic_service_conditions_after_price_heading(default_template, schema_editor):
    """Fails if the default service template lacks its generated conditions block after the price heading."""
    migration.forwards(apps, schema_editor)
    default_template.refresh_from_db()

    assert '{service_conditions}' in default_template.service_content_markdown
    assert (
        migration.PRICE_HEADING + migration.CONDITIONS
    ) in default_template.service_content_markdown


def test_forward_replaces_commercial_economic_reference(default_template, schema_editor):
    """Fails if a default service template keeps its commercial-annex economic reference."""
    migration.forwards(apps, schema_editor)
    default_template.refresh_from_db()

    assert 'Documento Propuesta Comercial' not in default_template.service_content_markdown
    assert 'apartado de Condiciones particulares del servicio' in default_template.service_content_markdown


def test_forward_preserves_non_default_service_template(default_template, schema_editor):
    """Fails if migration 0276 overwrites a negotiated non-default service contract."""
    other = ContractTemplate.objects.create(
        name='Contrato negociado',
        service_content_markdown='Documento Propuesta Comercial',
    )

    migration.forwards(apps, schema_editor)
    other.refresh_from_db()

    assert other.service_content_markdown == 'Documento Propuesta Comercial'


def test_forward_is_idempotent(default_template, schema_editor):
    """Fails if rerunning migration 0276 duplicates the service conditions placeholder."""
    migration.forwards(apps, schema_editor)
    default_template.refresh_from_db()
    first = default_template.service_content_markdown

    migration.forwards(apps, schema_editor)
    default_template.refresh_from_db()

    assert default_template.service_content_markdown == first
    assert default_template.service_content_markdown.count('{service_conditions}') == 1
