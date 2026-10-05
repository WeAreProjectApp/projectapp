"""Contract edits preserve negotiated text and apply coupled terms together."""

from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.files.base import ContentFile
from django.db import connection
from freezegun import freeze_time

from content.models import ContractTemplate, ProposalDocument

pytestmark = pytest.mark.django_db
migration = import_module('content.migrations.0257_update_contract_ownership_and_termination')


def contract_before_update():
    """Reconstruct the previously shipped template from immutable migrations."""
    v3 = import_module('content.migrations.0077_update_default_contract_template_v3')
    v4 = import_module('content.migrations.0111_update_default_contract_template_v4')
    v5 = import_module('content.migrations.0165_update_default_contract_template_v5')
    v6 = import_module('content.migrations.0179_update_default_contract_template_v6')
    v7 = import_module('content.migrations.0181_update_default_contract_template_v7')
    adjustment = import_module('content.migrations.0255_update_contract_service_adjustment')
    markdown = v3.NEW_CONTRACT_MARKDOWN
    markdown = markdown.replace(v4.PRODUCTOS_OLD, v4.PRODUCTOS_NEW)
    markdown = markdown.replace(v4.CRONOGRAMA_OLD, v4.CRONOGRAMA_NEW)
    markdown = markdown.replace('Documento Propuesta de Negocio', 'Documento Propuesta Comercial')
    markdown = markdown.replace('{contractor_cedula}', '{contractor_nit}')
    markdown = v5.apply_pairs(markdown, v5.FORWARD_PAIRS)
    markdown = v6.apply_pairs(markdown, v6.FORWARD_PAIRS)
    markdown = v7.apply_pairs(markdown, v7.CONTRACT_PAIRS, 'contract')
    return markdown.replace(adjustment.OLD_PARAGRAPH, adjustment.NEW_PARAGRAPH)


@pytest.fixture
def legacy_template():
    return ContractTemplate.objects.create(
        name='Contrato antes de la actualización',
        content_markdown=contract_before_update(),
        is_default=True,
    )


@pytest.fixture
def schema_editor():
    return SimpleNamespace(connection=connection)


def test_forward_updates_the_unilateral_exit_price(legacy_template, schema_editor):
    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert 'treinta por ciento (30%) del valor de las fases restantes' in legacy_template.content_markdown
    assert 'veinte por ciento (20%) del valor de las fases restantes' not in legacy_template.content_markdown
    assert 'no por una postergación o suspensión del proyecto' in legacy_template.content_markdown


def test_forward_preserves_unrelated_manual_text(legacy_template, schema_editor):
    legacy_template.content_markdown += '\n\nNota particular de garantía pactada.'
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown.endswith('Nota particular de garantía pactada.')
    assert 'Condiciones Mínimas de Reajuste del Valor del Servicio' in legacy_template.content_markdown
    assert '{contractor_id_number}' in legacy_template.content_markdown


def test_forward_preserves_other_termination_grounds(legacy_template, schema_editor):
    """Changing the client's unilateral exit must not change the contractor's exit."""
    previous = legacy_template.content_markdown.split(
        '### Parágrafo Tercero — Terminación Unilateral por EL CONTRATISTA',
    )[1]

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    actual = legacy_template.content_markdown.split(
        '### Parágrafo Tercero — Terminación Unilateral por EL CONTRATISTA',
    )[1]
    assert actual == previous


def test_forward_preserves_non_default_templates(legacy_template, schema_editor):
    other = ContractTemplate.objects.create(
        name='Contrato negociado', content_markdown=legacy_template.content_markdown,
    )
    previous = other.content_markdown

    migration.update_default_template(apps, schema_editor)

    other.refresh_from_db()
    assert other.content_markdown == previous


def test_forward_preserves_custom_proposal_contract(proposal, legacy_template, schema_editor):
    proposal.contract_params = {
        'contract_source': 'custom',
        'custom_contract_markdown': 'Contrato negociado con penalidad del 20%.',
    }
    proposal.save(update_fields=['contract_params'])

    migration.update_default_template(apps, schema_editor)

    proposal.refresh_from_db()
    assert proposal.contract_params == {
        'contract_source': 'custom',
        'custom_contract_markdown': 'Contrato negociado con penalidad del 20%.',
    }


def test_forward_preserves_generated_contract_snapshot(proposal, legacy_template, schema_editor):
    """Previously issued contractual evidence keeps its text and stored file bytes."""
    document = ProposalDocument.objects.create(
        proposal=proposal, document_type='contract', title='Contrato emitido',
        is_generated=True, content_markdown='Contrato histórico con penalidad del 20%.',
        file=ContentFile(b'%PDF-1.4\nIssued contract bytes', name='issued-contract.pdf'),
    )

    migration.update_default_template(apps, schema_editor)

    document.refresh_from_db()
    assert document.content_markdown == 'Contrato histórico con penalidad del 20%.'
    with document.file.open('rb') as stored:
        assert stored.read() == b'%PDF-1.4\nIssued contract bytes'


@pytest.mark.parametrize('old,new', [
    ('veinte por ciento (20%)', 'quince por ciento (15%)'),
    ('### Parágrafo Sexto — Terminación Anticipada', '### Entrega negociada'),
    ('d) Conocimiento técnico (know-how)', 'd) Conocimiento reservado'),
])
def test_forward_preserves_custom_ownership_group(
    legacy_template, schema_editor, caplog, old, new,
):
    """A mismatching condition prevents a partially updated delivery agreement."""
    legacy_template.content_markdown = legacy_template.content_markdown.replace(old, new)
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert new in legacy_template.content_markdown
    assert 'se suma al precio contractual' not in legacy_template.content_markdown
    assert 'La incorporación de herramientas generales' not in legacy_template.content_markdown
    assert 'preserving custom or ambiguous ownership' in caplog.text
    assert 'treinta por ciento (30%) del valor de las fases restantes' not in legacy_template.content_markdown


def test_forward_preserves_ambiguous_ownership_group(legacy_template, schema_editor, caplog):
    legacy_template.content_markdown += '\n\n' + migration.OLD_TERMINATION
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown.count(migration.OLD_TERMINATION) == 2
    assert 'se suma al precio contractual' not in legacy_template.content_markdown
    assert 'preserving custom or ambiguous ownership' in caplog.text


def test_forward_keeps_hosting_removal_atomic(legacy_template, schema_editor, caplog):
    legacy_template.content_markdown = legacy_template.content_markdown.replace(
        '3. Se mantiene el acceso de solo lectura', '3. Se negocia el acceso de solo lectura',
    )
    legacy_template.save(update_fields=['content_markdown'])

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert '8. EL CONTRATANTE y el personal' in legacy_template.content_markdown
    assert '9. Cuando EL CONTRATANTE contrate' in legacy_template.content_markdown
    assert 'preserving custom or ambiguous hosting' in caplog.text


def test_forward_is_idempotent(legacy_template, schema_editor):
    migration.update_default_template(apps, schema_editor)
    legacy_template.refresh_from_db()
    previous = (legacy_template.content_markdown, legacy_template.updated_at)

    migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert (legacy_template.content_markdown, legacy_template.updated_at) == previous


def test_forward_does_not_create_a_missing_default(schema_editor):
    ContractTemplate.objects.update(is_default=False)

    migration.update_default_template(apps, schema_editor)

    assert ContractTemplate.get_default() is None


def test_forward_refreshes_the_public_template_timestamp(legacy_template, schema_editor):
    previous = legacy_template.updated_at

    with freeze_time('2030-01-02 12:00:00'):
        migration.update_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.updated_at > previous
    assert legacy_template.updated_at.isoformat() == '2030-01-02T12:00:00+00:00'


def test_reverse_restores_the_previous_contract(legacy_template, schema_editor):
    previous = legacy_template.content_markdown
    migration.update_default_template(apps, schema_editor)

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert legacy_template.content_markdown == previous


def test_reverse_preserves_later_negotiated_terms(legacy_template, schema_editor, caplog):
    """Rollback must retain the whole coupled group after a negotiated amendment."""
    migration.update_default_template(apps, schema_editor)
    legacy_template.refresh_from_db()
    legacy_template.content_markdown = legacy_template.content_markdown.replace(
        'treinta por ciento (30%)', 'veinticinco por ciento (25%)',
    )
    legacy_template.save(update_fields=['content_markdown'])

    migration.revert_default_template(apps, schema_editor)

    legacy_template.refresh_from_db()
    assert 'veinticinco por ciento (25%)' in legacy_template.content_markdown
    assert 'se suma al precio contractual' in legacy_template.content_markdown
    assert 'La incorporación de herramientas generales' in legacy_template.content_markdown
    assert 'preserving custom or ambiguous ownership' in caplog.text
