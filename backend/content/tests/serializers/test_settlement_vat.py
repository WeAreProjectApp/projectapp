"""Settlement tax contracts reject ambiguous or unrelated per-income inputs."""
import pytest

from content.serializers.accounting import IncomeBulkSettlementSerializer


def payload(updates):
    return {
        'income_ids': [1], 'total_amount': '119.00', 'period_date': '2026-10-21',
        'vat_updates': updates,
    }


@pytest.mark.parametrize('updates', [
    [{'income_id': 2, 'vat_rate': '19'}],
    [{'income_id': 1, 'vat_rate': '19'}, {'income_id': 1, 'vat_rate': '0'}],
    [{'income_id': 1, 'vat_rate': '-1'}],
    [{'income_id': 1, 'vat_rate': '100.01'}],
    [{'income_id': 1, 'vat_rate': '19.001'}],
    [{'income_id': 1, 'vat_rate': '19', 'amount_mode': 'before_vat'}],
    [{'income_id': 1, 'vat_rate': None, 'amount': '100', 'amount_mode': 'before_vat'}],
    [{'income_id': 1, 'vat_rate': '19', 'amount': '100.001'}],
])
def test_invalid_vat_configuration_is_rejected(updates):
    """Falla si una configuración fiscal ambigua alcanza el escritor contable."""
    serializer = IncomeBulkSettlementSerializer(data=payload(updates))

    assert not serializer.is_valid()
    assert 'vat_updates' in serializer.errors


def test_explicit_unknown_rate_remains_distinct_from_zero():
    """Falla si el contrato transforma una tasa desconocida en Sin IVA."""
    serializer = IncomeBulkSettlementSerializer(data=payload([{'income_id': 1, 'vat_rate': None}]))

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['vat_updates'][0]['vat_rate'] is None
