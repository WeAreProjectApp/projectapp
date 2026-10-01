"""The standalone service contract is seeded once and never overwrites a curated text."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ContractTemplate

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0266_seed_service_contract_text')
paragraph_ten = import_module('content.migrations.0267_add_provider_dependency_paragraph')


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


@pytest.fixture
def unseeded_template():
    return ContractTemplate.objects.create(
        name='Contrato sin servicio', content_markdown='Texto.', is_default=True,
    )


def test_migrated_default_holds_the_standalone_service_contract():
    """Fails if a fresh database cannot close a deal with two documents."""
    service = ContractTemplate.get_default().service_content_markdown
    # Later migrations add provider dependencies and move economics into this contract.
    assert paragraph_ten.SERVICE_CONTRACT_PARAGRAPH in service
    assert '{service_conditions}' in service
    assert 'Documento Propuesta Comercial' not in service
    assert service.startswith('Entre las partes, por un lado **{client_full_name}**')
    assert '## CLÁUSULA DÉCIMA SÉPTIMA — MÉRITO EJECUTIVO' in service
    assert 'duración inicial de {service_initial_term}' in service


def test_forward_fills_an_empty_default_only(unseeded_template, schema_editor):
    """Fails if the seed skips the default template or touches another template."""
    other = ContractTemplate.objects.create(name='Otra', content_markdown='Otro texto.')

    migration.seed_service_contract(apps, schema_editor)

    unseeded_template.refresh_from_db()
    other.refresh_from_db()
    assert unseeded_template.service_content_markdown == migration.SERVICE_CONTRACT_MARKDOWN
    assert other.service_content_markdown == ''


def test_forward_preserves_a_curated_service_text(unseeded_template, schema_editor):
    """Fails if re-running the seed replaces a service text curated after the deploy."""
    unseeded_template.service_content_markdown = 'Texto negociado.'
    unseeded_template.save(update_fields=['service_content_markdown'])

    migration.seed_service_contract(apps, schema_editor)

    unseeded_template.refresh_from_db()
    assert unseeded_template.service_content_markdown == 'Texto negociado.'


def test_reverse_empties_the_service_text(unseeded_template, schema_editor):
    """Fails if rolling back leaves the separation available without its migration."""
    migration.seed_service_contract(apps, schema_editor)

    migration.clear_service_contract(apps, schema_editor)

    unseeded_template.refresh_from_db()
    assert unseeded_template.service_content_markdown == ''
