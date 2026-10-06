"""One billing prerequisite shared by API projections and settlement writers."""

ISSUED_ACCOUNT_STATUSES = frozenset({'issued', 'paid'})
MISSING_ACCOUNT_REASON = 'Primero genera y emite una cuenta de cobro para este ingreso.'


def settlement_blocked_reason(*, kind, pending, client_id, account_status):
    if kind != 'expected':
        return 'Solo se puede liquidar un ingreso esperado.'
    if pending <= 0:
        return 'Este ingreso esperado ya está completamente pagado.'
    if client_id and account_status not in ISSUED_ACCOUNT_STATUSES:
        return MISSING_ACCOUNT_REASON
    return ''


def require_issued_accounts(incomes, documents):
    """Called after billing locks and before any financial write."""
    from accounts.models import UserProfile
    from content.models import DocumentType
    required = {income.pk: income for income in incomes if income.client_id}
    if not required:
        return
    client_users = dict(UserProfile.objects.filter(
        pk__in={income.client_id for income in required.values()},
    ).values_list('pk', 'user_id'))
    documents = list(documents)
    types = set(DocumentType.objects.filter(
        pk__in={doc.document_type_id for doc in documents}, code='collection_account',
    ).values_list('pk', flat=True))
    covered = set()
    for doc in documents:
        income = required.get(doc.income_record_id)
        if (
            income and doc.document_type_id in types
            and doc.commercial_status in ISSUED_ACCOUNT_STATUSES
            and doc.project_id == income.project_id
            and doc.client_user_id == client_users.get(income.client_id)
        ):
            covered.add(income.pk)
    if covered != required.keys():
        raise ValueError(MISSING_ACCOUNT_REASON)
