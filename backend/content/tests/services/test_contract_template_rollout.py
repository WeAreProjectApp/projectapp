import pytest

from content.models import ContractTemplate
from content.services.contract_template_consistency import SERVICE_PAYMENT_SENTENCE, check_consistency
from content.services.contract_template_rollout import approved_adjustments
from content.services.contract_template_validation import TEXT_FIELDS, heading_span

pytestmark = pytest.mark.django_db


@pytest.fixture
def adjusted_texts(source_237_markdown):
    template = ContractTemplate.get_default()
    source = source_237_markdown
    return approved_adjustments({key: getattr(template, field) for key, field in TEXT_FIELDS.items()}, source)


@pytest.mark.parametrize('variant', ['combined', 'product'])
def test_adjustment_preserves_the_warranty_conditions_with_a_three_year_term(adjusted_texts, variant):
    original = getattr(ContractTemplate.get_default(), TEXT_FIELDS[variant])
    heading = 'Parágrafo Sexto — Garantía y Soporte'
    clause = 'CLÁUSULA SEGUNDA — EJECUCIÓN DEL CONTRATO'
    start, end = heading_span(original, heading, clause=clause)
    expected = original[start:end].replace('garantía por un periodo de un (1) año', 'garantía por un periodo de tres (3) años')
    start, end = heading_span(adjusted_texts[variant], heading, clause=clause)

    assert adjusted_texts[variant][start:end] == expected


def test_adjustment_preserves_combined_service_duration(adjusted_texts):
    assert 'duración inicial de {service_initial_term}' in adjusted_texts['combined']


@pytest.mark.parametrize('variant', ['combined', 'product', 'service'])
def test_adjustment_uses_three_year_confidentiality_obligations(adjusted_texts, variant):
    heading = ('CLÁUSULA NOVENA' if variant == 'service' else 'CLÁUSULA DÉCIMA PRIMERA') + ' — CONFIDENCIALIDAD Y NO CIRCUNVENCIÓN'
    start, end = heading_span(adjusted_texts[variant], heading)
    clause = adjusted_texts[variant][start:end]

    assert '### Parágrafo Cuarto — No Circunvención' in clause
    assert clause.count('tres (3) años') == 2
    assert 'dos (2) años' not in clause


def test_adjustment_applies_the_service_payment_protocol_in_breach(adjusted_texts):
    start, end = heading_span(adjusted_texts['combined'], 'Parágrafo Primero — Plazo para Subsanar', clause='CLÁUSULA DÉCIMA SÉPTIMA — INCUMPLIMIENTO')

    assert SERVICE_PAYMENT_SENTENCE in adjusted_texts['combined'][start:end]


@pytest.mark.parametrize('variant', ['combined', 'product'])
def test_adjustment_includes_service_billing_evidence(adjusted_texts, variant):
    start, end = heading_span(adjusted_texts[variant], 'CLÁUSULA DÉCIMA NOVENA — MÉRITO EJECUTIVO')

    assert 'junto con sus anexos, las actas de entrega, las cuentas de cobro o facturas y los comprobantes de pago' in adjusted_texts[variant][start:end]


def test_adjustment_routes_service_termination_in_the_delinquency_protocol(adjusted_texts):
    start, end = heading_span(adjusted_texts['combined'], 'CLÁUSULA VIGÉSIMA CUARTA — PROTOCOLO DE MORA Y SUSPENSIÓN DEL SERVICIO')
    clause = adjusted_texts['combined'][start:end]

    assert 'y para dar por terminado el servicio conforme al PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA, o el contrato conforme a la CLÁUSULA DÉCIMA SEXTA' in clause
    assert 'las obligaciones del desarrollo, la terminación del servicio prevista en el PARÁGRAFO SEXTO de la CLÁUSULA VIGÉSIMA PRIMERA' in clause


def test_approved_adjustment_produces_coherent_variants(adjusted_texts):
    result = check_consistency(adjusted_texts)
    assert result['consistent'], result['findings']


def test_approved_adjustment_is_idempotent(adjusted_texts, source_237_markdown):
    assert approved_adjustments(adjusted_texts, source_237_markdown) == adjusted_texts
