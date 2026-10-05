"""Missing clauses and changed obligations must block template updates."""
import pytest

from content.services.contract_template_consistency import check_consistency
from content.services.contract_template_validation import TEXT_FIELDS

pytestmark = pytest.mark.django_db


@pytest.fixture
def contract_texts(coherent_template):
    return {key: getattr(coherent_template, field) for key, field in TEXT_FIELDS.items()}


def test_warranty_change_is_reported_as_a_substantive_difference(contract_texts):
    contract_texts['combined'] = contract_texts['combined'].replace(
        'garantía por un periodo de tres (3) años', 'garantía por un periodo de cuatro (4) años',
    )

    result = check_consistency(contract_texts)

    assert result['consistent'] is False
    assert {'topic': 'EJECUCIÓN DEL CONTRATO', 'variants': ['combined', 'product'], 'kind': 'different'} in [
        {key: finding[key] for key in ('topic', 'variants', 'kind')} for finding in result['findings']
    ]


def test_renumbering_clause_references_preserves_consistency(contract_texts):
    contract_texts['combined'] = contract_texts['combined'].replace('CLÁUSULA VIGÉSIMA CUARTA', 'CLÁUSULA VIGÉSIMA QUINTA')

    result = check_consistency(contract_texts)

    assert result['consistent'] is True, result['findings']


@pytest.mark.parametrize(('variant', 'missing_in'), [('combined', 'service'), ('service', 'combined')])
def test_new_service_clause_requires_its_counterpart(contract_texts, variant, missing_in):
    contract_texts[variant] += '\n\n## CLÁUSULA VIGÉSIMA QUINTA — RESPALDOS\n\nSe conserva un respaldo adicional por treinta (30) días.\n'

    result = check_consistency(contract_texts)

    assert result['consistent'] is False
    assert {'topic': 'RESPALDOS', 'variants': ['combined', 'service'], 'kind': 'missing', 'missing_in': missing_in} in result['findings']
