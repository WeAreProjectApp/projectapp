"""Behavior tests for the side-effect-free Wompi payment binding guard."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from accounts.services.wompi_payment_binding import (
    WompiPaymentBindingError,
    validate_transaction_binding,
)


@pytest.fixture
def payment_double():
    """Provide a mutable payment-shaped binding subject."""
    return SimpleNamespace(
        id=17,
        amount=Decimal('250000.00'),
        wompi_payment_link_id='link-local-17',
        subscription=SimpleNamespace(project_id=88),
    )


def _transaction(**overrides):
    transaction = {
        'id': 'txn-canonical-17',
        'amount_in_cents': 25000000,
        'currency': 'COP',
        'reference': 'PA17P88T1700000000',
    }
    transaction.update(overrides)
    return transaction


def _transaction_without(field):
    transaction = _transaction()
    transaction.pop(field)
    return transaction


@pytest.mark.parametrize(
    ('transaction', 'expected_transaction_id', 'reason'),
    [
        (None, None, 'invalid-payload'),
        (_transaction(id='txn-other'), 'txn-canonical-17', 'id-mismatch'),
        (_transaction(reference='PA18P88T1700000000'), None, 'reference-mismatch'),
        (_transaction(reference='PA17P89T1700000000'), None, 'reference-mismatch'),
        (_transaction(amount_in_cents=24999999), None, 'amount-mismatch'),
        (_transaction(currency='USD'), None, 'currency-mismatch'),
        (_transaction(payment_link_id='link-for-other-payment'), None, 'payment-link-mismatch'),
        (_transaction_without('amount_in_cents'), None, 'amount-mismatch'),
        (_transaction_without('currency'), None, 'currency-mismatch'),
        (_transaction(id=None), None, 'invalid-id'),
        (_transaction(id=17), None, 'invalid-id'),
        (_transaction_without('reference'), None, 'invalid-reference'),
        (_transaction(reference=17), None, 'invalid-reference'),
    ],
    ids=[
        'malformed-payload', 'other-transaction-id', 'other-payment-reference',
        'other-project-reference', 'other-amount', 'other-currency', 'other-payment-link',
        'missing-amount', 'missing-currency', 'missing-id', 'non-string-id',
        'missing-reference', 'non-string-reference',
    ],
)
def test_binding_rejects_unrelated_transaction_without_mutating_payment(
    payment_double, transaction, expected_transaction_id, reason,
):
    """Fails if an unrelated provider transaction can alter a local payment."""
    original_payment = payment_double.__dict__.copy()

    with pytest.raises(WompiPaymentBindingError) as error:
        validate_transaction_binding(
            payment_double,
            transaction,
            expected_transaction_id=expected_transaction_id,
        )

    assert error.value.reason == reason
    assert payment_double.__dict__ == original_payment


def test_binding_accepts_transaction_with_matching_local_payment_link(payment_double):
    """Fails if a canonical transaction with the payment's link is rejected."""
    transaction = _transaction(
        reference='wompi-provider-reference',
        payment_link_id='link-local-17',
    )
    original_payment = payment_double.__dict__.copy()

    validate_transaction_binding(payment_double, transaction)

    assert payment_double.__dict__ == original_payment


def test_binding_accepts_card_reference_for_matching_payment_project_pair(payment_double):
    """Fails if a card transaction for the same payment and project is rejected."""
    transaction = _transaction(reference='PA17P88T1700000000')
    original_payment = payment_double.__dict__.copy()

    validate_transaction_binding(payment_double, transaction)

    assert payment_double.__dict__ == original_payment


def test_binding_accepts_historical_numeric_payment_reference(payment_double):
    """Fails if valid legacy numeric payment references stop being accepted."""
    transaction = _transaction(reference=str(payment_double.id))
    original_payment = payment_double.__dict__.copy()

    validate_transaction_binding(payment_double, transaction)

    assert payment_double.__dict__ == original_payment
