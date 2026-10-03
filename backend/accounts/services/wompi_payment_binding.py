"""Validate a provider transaction before it can change a local payment."""

import re


class WompiPaymentBindingError(ValueError):
    """The provider payload cannot be associated with the expected payment."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__('La transacción no corresponde a este pago.')


def validate_transaction_binding(
    payment, transaction, expected_transaction_id=None, expected_reference=None,
):
    """Check transaction identity, value and payment ownership without writes.

    Link transactions carry a provider-generated reference, so their ownership
    comes from ``payment_link_id``. Widget/card references contain both local
    IDs; the exact numeric payment reference remains supported for old charges.
    An immediate charge response must additionally echo its generated reference.
    """
    if not isinstance(transaction, dict):
        raise WompiPaymentBindingError('invalid-payload')

    transaction_id = transaction.get('id')
    if (
        not isinstance(transaction_id, str)
        or not transaction_id.strip()
        or len(transaction_id) > 100
    ):
        raise WompiPaymentBindingError('invalid-id')
    if (
        expected_transaction_id is not None
        and transaction_id != expected_transaction_id
    ):
        raise WompiPaymentBindingError('id-mismatch')

    amount_in_cents = transaction.get('amount_in_cents')
    if type(amount_in_cents) is not int or amount_in_cents != payment.amount * 100:
        raise WompiPaymentBindingError('amount-mismatch')
    if transaction.get('currency') != 'COP':
        raise WompiPaymentBindingError('currency-mismatch')

    reference = transaction.get('reference')
    if expected_reference is not None and reference != expected_reference:
        raise WompiPaymentBindingError('reference-mismatch')

    payment_link_id = transaction.get('payment_link_id')
    if payment_link_id is not None and payment_link_id != '':
        if (
            not isinstance(payment_link_id, str)
            or payment_link_id != payment.wompi_payment_link_id
        ):
            raise WompiPaymentBindingError('payment-link-mismatch')
        return

    if not isinstance(reference, str):
        raise WompiPaymentBindingError('invalid-reference')
    if reference == str(payment.id):
        return

    expected_pattern = rf'PA{payment.id}P{payment.subscription.project_id}T[0-9]+'
    if re.fullmatch(expected_pattern, reference) is None:
        raise WompiPaymentBindingError('reference-mismatch')
