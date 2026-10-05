"""Literal patching and conservative comparisons protect contractual meaning."""
import pytest

from content.services.contract_template_consistency import normalize
from content.services.contract_template_validation import (
    ContractTemplateError, apply_patches, placeholders, validate_markdown,
)
from content.services.contract_template_service import read_template


@pytest.mark.django_db
@pytest.mark.parametrize('variant', ['combined', 'service'])
@pytest.mark.parametrize('field', ['service_initial_term', 'service_renewal_notice_days', 'service_termination_notice_days'])
def test_service_term_cannot_be_omitted(coherent_template, variant, field):
    markdown = read_template(variant)['markdown'].replace('{' + field + '}', '')

    with pytest.raises(ContractTemplateError) as exc_info:
        validate_markdown(markdown, variant)

    assert exc_info.value.details['missing_placeholders'] == [field]


@pytest.mark.parametrize('markdown', ['Contrato {client.email}', 'Contrato {client_email'])
def test_invalid_placeholder_syntax_is_rejected(markdown):
    with pytest.raises(ContractTemplateError):
        placeholders(markdown)


def test_heading_patch_replaces_only_the_scoped_paragraph():
    markdown = '## Cláusula Primera\n### Parágrafo Primero\nOriginal.\n## Cláusula Segunda\n### Parágrafo Primero\nIntacto.\n'

    result = apply_patches(markdown, [{
        'operation': 'replace', 'heading': 'Parágrafo Primero', 'clause_heading': 'Cláusula Primera',
        'markdown': '### Parágrafo Primero\nNuevo.\n',
    }])

    assert result == '## Cláusula Primera\n### Parágrafo Primero\nNuevo.\n## Cláusula Segunda\n### Parágrafo Primero\nIntacto.\n'


def test_exact_text_patch_inserts_after_the_selected_fragment():
    result = apply_patches('Obligación única.', [{
        'operation': 'insert_after', 'text': 'única', 'markdown': ' aprobada',
    }])

    assert result == 'Obligación única aprobada.'


def test_ambiguous_text_patch_is_rejected():
    with pytest.raises(ContractTemplateError) as exc_info:
        apply_patches('Texto. Texto.', [{'operation': 'replace', 'text': 'Texto.', 'markdown': 'Nuevo.'}])

    assert exc_info.value.code == 'PATCH_TARGET_ERROR'


def test_comparison_ignores_clause_references():
    assert normalize('De acuerdo con la CLÁUSULA VIGÉSIMA PRIMERA.') == normalize('De acuerdo con la CLÁUSULA CUARTA.')


def test_comparison_preserves_the_sign_of_an_economic_change():
    assert normalize('Reajuste de +5 %.') != normalize('Reajuste de -5 %.')
