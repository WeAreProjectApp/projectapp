"""The clauses do not change when a deal closes with two documents; only the separation does."""
import re
from types import SimpleNamespace

import pytest

from content.models import BusinessProposal, ContractTemplate
from content.services import contract_variants as variants

pytestmark = pytest.mark.django_db

_HEADING_RE = re.compile(r'^## CLÁUSULA ((?:DÉCIMA |VIGÉSIMA )?[A-ZÁÉÍÓÚ]+) — (.+)$', re.MULTILINE)
_PARAGRAPH_TITLE_RE = re.compile(r'^### Parágrafo [A-Za-zéÉ]+ — (.+)$', re.MULTILINE)


@pytest.fixture
def default_template():
    template = ContractTemplate.get_default()
    assert template is not None, 'No default ContractTemplate in DB'
    return template


def _headings(markdown):
    return dict(_HEADING_RE.findall(markdown))


def test_product_is_the_combined_text_without_clauses_21_to_24(default_template):
    """Fails if the product contract differs from the combined one beyond the three adjustments."""
    combined = default_template.content_markdown
    product = variants.derive_product_markdown(combined)
    assert product is not None, 'An anchor of the product derivation is missing from the default text'

    assert [product.count(new) for _, new in variants.PRODUCT_ADJUSTMENTS] == [1, 1, 1]
    restored = product
    for old, new in variants.PRODUCT_ADJUSTMENTS:
        restored = restored.replace(new, old, 1)
    assert restored == combined[:combined.index(variants.PRODUCT_CUT)]


def test_product_keeps_twenty_clauses_and_never_cites_the_service_block(default_template):
    """Fails if a service clause, or a reference to one, survives in the product contract."""
    product = variants.template_markdown(default_template, variants.PRODUCT)

    assert len(_headings(product)) == 20
    assert 'VIGÉSIMA PRIMERA' not in product
    assert 'VIGÉSIMA SEGUNDA' not in product
    assert 'VIGÉSIMA TERCERA' not in product
    assert 'VIGÉSIMA CUARTA' not in product
    assert 'se entiende por día hábil el comprendido de lunes a viernes' in product


def test_derivation_refuses_a_default_text_that_drifted():
    """Fails if a customized default text silently yields a half-adjusted product contract."""
    combined = (
        'Preámbulo\n\n---\n\n## CLÁUSULA PRIMERA — OBJETO\n\nTexto.'
        + variants.PRODUCT_CUT + ' — SERVICIO\n\nCláusulas del servicio.'
    )

    assert variants.derive_product_markdown(combined) is None
    assert variants.derive_product_markdown('') is None


def test_service_contract_carries_every_service_paragraph(default_template):
    """Fails if a paragraph of clauses 21-24 is dropped from the standalone service contract."""
    combined = default_template.content_markdown
    service_block = combined[combined.index(variants.PRODUCT_CUT):]
    service = variants.template_markdown(default_template, variants.SERVICE)
    # A paragraph of clause 21 (Responsabilidad Operativa) became a clause of its own.
    service_titles = {
        title.lower()
        for title in [*_PARAGRAPH_TITLE_RE.findall(service), *_headings(service).values()]
    }

    expected = {title.lower() for title in _PARAGRAPH_TITLE_RE.findall(service_block)}
    assert len(expected) == 23
    assert expected <= service_titles
    assert len(_headings(service)) == 17


@pytest.mark.parametrize(('phrase', 'topic'), [
    ('el medio de notificación de la CLÁUSULA DÉCIMA TERCERA', 'NOTIFICACIÓN'),
    ('activa el protocolo previsto en la CLÁUSULA SÉPTIMA', 'PROTOCOLO DE MORA'),
    ('capacidad de infraestructura prevista en la CLÁUSULA SEXTA', 'RECURSOS DE INFRAESTRUCTURA'),
    ('descritos en el PARÁGRAFO SÉPTIMO de la CLÁUSULA QUINTA', 'ATENCIÓN DE INCIDENTES'),
    ('los niveles de atención de la CLÁUSULA QUINTA', 'NIVELES DE SERVICIO'),
    ('terminado el contrato conforme a la CLÁUSULA DÉCIMA CUARTA', 'TERMINACIÓN'),
    ('incidentes de seguridad conforme a la CLÁUSULA DÉCIMA', 'DATOS PERSONALES'),
    ('el valor del servicio conforme a la CLÁUSULA SEGUNDA', 'PRECIO'),
])
def test_service_cross_references_point_at_the_clause_they_describe(default_template, phrase, topic):
    """Fails if the renumbered service contract cites a clause that exists but is the wrong one."""
    service = variants.template_markdown(default_template, variants.SERVICE)
    ordinal = re.search(r'CLÁUSULA ((?:DÉCIMA |VIGÉSIMA )?[A-ZÁÉÍÓÚ]+)$', phrase).group(1)

    assert phrase in service
    assert topic in _headings(service)[ordinal]


def test_split_needs_both_standard_texts(default_template):
    """Fails if the switch offers a separation the default template cannot produce."""
    assert variants.split_available(default_template)

    default_template.service_content_markdown = ''
    assert not variants.split_available(default_template)


@pytest.mark.parametrize(('modality', 'expected'), [
    ('single', ('combined',)),
    ('split', ('product', 'service')),
    ('', ('combined',)),
    ('unknown', ('combined',)),
])
def test_active_variants_follow_the_closing_modality(modality, expected):
    """Fails if a proposal without a valid modality stops closing with the single contract."""
    proposal = SimpleNamespace(contract_modality=modality)

    assert variants.active_variants(proposal) == expected


COMPLETE_PARAMS = {
    'contractor_full_name': 'Contratista', 'contractor_email': 'c@example.com',
    'contractor_nit': '900', 'contract_city': 'Medellín', 'bank_name': 'Banco',
    'bank_account_number': '123', 'client_full_name': 'Cliente',
    'client_cedula': '456', 'client_email': 'cliente@example.com', 'contract_date': '2026-09-26',
}
SERVICE_TERMS = {
    'service_initial_term': 'doce (12) meses',
    'service_renewal_notice_days': 'treinta (30)',
    'service_termination_notice_days': 'treinta (30)',
}


def test_service_contract_waits_for_its_three_terms():
    """Fails if the service contract is generated with its duration and notices blank."""
    assert variants.can_generate(COMPLETE_PARAMS, variants.PRODUCT)
    assert variants.missing_generation_params(COMPLETE_PARAMS, variants.SERVICE) == list(variants.SERVICE_PARAM_KEYS)
    assert variants.can_generate({**COMPLETE_PARAMS, **SERVICE_TERMS}, variants.SERVICE)
    assert not variants.can_generate({}, variants.COMBINED)


def test_custom_document_needs_only_its_own_text():
    """Fails if a custom product text is blocked by the shared template parameters."""
    params = {'product_contract_source': 'custom', 'product_custom_contract_markdown': '# Texto'}

    assert variants.can_generate(params, variants.PRODUCT)
    assert not variants.can_generate(params, variants.SERVICE)
    assert variants.missing_final_params(params, variants.PRODUCT) == ['contract_date']


def test_final_service_contract_requires_its_terms_before_signature():
    """Fails if a service contract reaches the client with a blank term."""
    missing = variants.missing_final_params(
        {**COMPLETE_PARAMS, 'service_initial_term': 'doce (12) meses'}, variants.SERVICE,
    )

    assert missing == ['service_renewal_notice_days', 'service_termination_notice_days']
    assert variants.missing_final_params(COMPLETE_PARAMS, variants.COMBINED) == []


def test_modality_choices_are_the_registry_keys():
    """Fails if a closing modality exists that the variant registry cannot resolve."""
    assert set(BusinessProposal.ContractModality.values) == set(variants.MODALITY_VARIANTS)
