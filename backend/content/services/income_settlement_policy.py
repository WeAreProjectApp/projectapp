"""Payment eligibility and the separate documentary state of an income."""

ISSUED_ACCOUNT_STATUSES = frozenset({'issued', 'paid'})
MISSING_ACCOUNT_REASON = 'Primero genera y emite una cuenta de cobro para este ingreso.'


def settlement_blocked_reason(*, kind, pending):
    if kind != 'expected':
        return 'Solo se puede liquidar un ingreso esperado.'
    if pending <= 0:
        return 'Este ingreso esperado ya está completamente pagado.'
    return ''


def issued_collection_account(income):
    """The matching issued or paid cuenta, independently of payment eligibility.

    Documentary state: a cuenta de cobro of this
    income, issued or paid, for its project and its client's user. Newest
    first, so a re-issue after a cancellation is the one that answers.
    """
    from content.models import Document

    if not income.client_id:
        return None
    return (
        Document.objects
        .filter(
            income_record=income,
            document_type__code='collection_account',
            commercial_status__in=ISSUED_ACCOUNT_STATUSES,
            project_id=income.project_id,
            client_user_id=income.client.user_id,
        )
        .select_related('collection_account')
        .order_by('-created_at', '-pk')
        .first()
    )
