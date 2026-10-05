"""The import migration records the existing defaults without rewriting deals."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from content.models import ContractTemplate, ContractTemplateVersion
from content.services.contract_variants import derive_product_markdown

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0280_import_contract_template_versions')


def test_import_seeds_the_existing_default_texts(accepted_proposal):
    template = ContractTemplate.get_default()
    ContractTemplateVersion.objects.all().delete()
    original_combined = template.content_markdown
    original_service = template.service_content_markdown
    proposal_before = accepted_proposal.contract_params

    migration.import_versions(apps, SimpleNamespace(connection=connection))

    template.refresh_from_db()
    accepted_proposal.refresh_from_db()
    versions = {row.variant: row for row in template.versions.all()}
    assert template.product_content_markdown == derive_product_markdown(original_combined)
    assert {key: row.version for key, row in versions.items()} == {'combined': 1, 'product': 1, 'service': 1}
    assert versions['combined'].markdown == original_combined
    assert versions['service'].markdown == original_service
    assert accepted_proposal.contract_params == proposal_before


def test_import_refuses_an_ambiguous_default_anchor():
    template = ContractTemplate.get_default()
    ContractTemplateVersion.objects.all().delete()
    template.content_markdown = 'Sin las cláusulas necesarias para importar el producto.'
    template.save(update_fields=['content_markdown'])

    with pytest.raises(RuntimeError, match='anclas'):
        migration.import_versions(apps, SimpleNamespace(connection=connection))

    assert template.versions.count() == 0
