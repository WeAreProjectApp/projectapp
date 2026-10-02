"""Create + issue a cuenta de cobro linked to an income (panel modal flow).

Every modal-created cuenta requires an income (expected or liquid) and a
platform client. The customer snapshot defaults come from the client's
profile — NIT preferred over cédula — overlaid with the form's editable
overrides; the per-client PA-{CODE}-{NNN} series numbers the document.
"""
from decimal import Decimal

from django.db import transaction

from accounts.models import UserProfile
from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    IncomeRecord,
)
from content.services import accounting_service
from content.services.accounting_vat import vat_breakdown, quantize_money
from content.serializers.accounting import IncomeRecordCreateUpdateSerializer, paid_total_for_income, split_half
from content.services.collection_account_numbering import allocate_client_number
from content.services.collection_account_service import (
    CollectionAccountError,
    get_default_issuer,
    issue_collection_account,
    recalculate_document_totals,
    seed_default_payment_methods,
)
from content.services.document_type_utils import (
    get_collection_account_document_type,
)

PAYMENT_TERM_DAYS = 8


def client_legal_identity(profile):
    """Who the cuenta de cobro is legally issued to.

    The name has to agree with the identification printed beside it: a NIT
    belongs to a company, a cédula to a person. Preferring `company_name`
    unconditionally — as this did — printed a brand next to a personal
    cédula, which is what made a cobro read "MIMITTOS · C.C. 1049654583"
    while the actual debtor's name sat unused in `contact_name`.

    `company_name` is where operators keep the brand, so it is exactly the
    field that must NOT decide the legal name on its own.

    Returns (name, identification, identification_type, contact_name).
    """
    user = profile.user
    full_name = f'{user.first_name} {user.last_name}'.strip()
    if profile.nit:
        identification, identification_type = profile.nit, 'NIT'
    elif profile.cedula:
        identification, identification_type = profile.cedula, 'CC'
    else:
        identification, identification_type = '', ''
    name = legal_name_for(profile) or (user.email or '')
    return name, identification, identification_type, full_name


def legal_name_for(profile):
    """The client's legal name by identification type, or '' when unknown.

    Split out from `client_legal_identity` because the numbering code needs
    the name WITHOUT its email fallback: falling back to a full address
    there would yield a code like 'ANAACMEC' instead of dropping through to
    the email local part.
    """
    user = profile.user
    full_name = f'{user.first_name} {user.last_name}'.strip()
    if profile.nit:
        return profile.company_name or full_name
    return full_name or profile.company_name


def customer_snapshot_defaults(profile):
    """Editable snapshot prefill from the client profile (NIT over cédula)."""
    name, identification, identification_type, full_name = (
        client_legal_identity(profile)
    )
    return {
        'name': name,
        'email': profile.user.email or '',
        'identification': identification,
        'identification_type': identification_type,
        'contact_name': full_name,
        'address': profile.address or '',
    }


def _resolve_customer(profile, overrides):
    customer = customer_snapshot_defaults(profile)
    for key, value in (overrides or {}).items():
        if value is not None:
            customer[key] = value
    email = (customer.get('email') or '').strip()
    if not email or email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN):
        raise CollectionAccountError(
            'El cliente no tiene un email real configurado. Actualízalo en '
            'el módulo de clientes o escríbelo en el formulario.',
        )
    customer['email'] = email
    return customer


def _create_income_collection_account(
    data, *, acting_user=None, issue_document=True, issued_on=None,
):
    """Build an income-linked account inside the public wrapper transaction."""
    issuer = get_default_issuer()

    profile = (
        UserProfile.objects.select_related('user')
        .filter(pk=data['client_profile_id'])
        .first()
    )
    if profile is None:
        raise CollectionAccountError('El cliente seleccionado no existe.')
    client = profile.user

    # Row lock: serializes concurrent creates over the same income, making
    # the one-non-cancelled-cuenta guard race-safe (MySQL cannot express it
    # as a conditional unique constraint).
    from accounts.services.billing_locks import lock_billing_rows
    locked = lock_billing_rows(income_ids=[data['income_record_id']],
                               include_income_children=True, include_origin_documents=True)
    income = locked.incomes.get(data['income_record_id'])
    if income is None:
        raise CollectionAccountError('El ingreso seleccionado no existe.')
    if income.kind == IncomeRecord.Kind.LOST:
        raise CollectionAccountError(
            'No se puede generar una cuenta de cobro sobre un ingreso perdido.',
        )
    if income.collection_documents.exclude(
        commercial_status=Document.CommercialStatus.CANCELLED,
    ).exists():
        raise CollectionAccountError(
            'Este ingreso ya tiene una cuenta de cobro. Anúlala para '
            'generar otra.',
        )

    # The cuenta de cobro is the strongest ownership signal available:
    # refuse a mismatch outright (client B's cuenta over client A's income
    # would split one deal across two clients) and adopt the client when
    # the income never got one — audited through the same pathway as the
    # bulk completion tool, which also cascades to settled liquids.
    if income.client_id and income.client_id != profile.pk:
        raise CollectionAccountError(
            'El ingreso seleccionado pertenece a otro cliente. Revisa el '
            'ingreso o cambia el cliente de la cuenta.',
        )
    if income.project_id and income.project.client_id != client.pk:
        raise CollectionAccountError('El proyecto del ingreso pertenece a otro cliente.')
    if income.client_id is None:
        accounting_service.bulk_assign_client(
            accounting_service.EntityType.INCOME, [income.pk], profile,
            acting_user,
        )
        income.client = profile

    rate = data.get('vat_rate', income.vat_rate)
    prepared_items = []
    for item in data['items']:
        quantity = item.get('quantity') or Decimal('1')
        try:
            if 'amount' in item:
                base, tax, total = vat_breakdown(
                    item['amount'], rate, item.get('amount_mode', 'vat_included'),
                )
                base = total if base is None else base
            else:
                base, tax, total = vat_breakdown(
                    item['unit_price'], rate, 'before_vat' if rate is not None else 'vat_included',
                )
                base = total if base is None else base
        except ValueError as exc:
            raise CollectionAccountError(str(exc)) from exc
        line_total = quantize_money(total * quantity)
        line_base = quantize_money(base * quantity)
        prepared_items.append({
            **item, 'quantity': quantity, 'unit_price': base,
            'tax_amount': line_total - line_base,
            'line_total': line_total,
        })
    document_total = sum((item['line_total'] for item in prepared_items), Decimal('0'))
    try:
        vat_breakdown(document_total, rate)
    except ValueError as exc:
        raise CollectionAccountError(str(exc)) from exc
    paid = paid_total_for_income(income) if income.kind == IncomeRecord.Kind.EXPECTED else income.total_amount
    if rate is not None or 'vat_rate' in data or any('amount' in item for item in data['items']):
        target = income.total_amount - paid if income.kind == IncomeRecord.Kind.EXPECTED else income.total_amount
        financial_change = rate != income.vat_rate or document_total != target
        if financial_change and paid:
            raise CollectionAccountError('Este ingreso ya tiene pagos o deducciones. La cuenta debe conservar el IVA y el saldo del ingreso.')
        if financial_change:
            update = {'total_amount': document_total, 'vat_rate': rate}
            # Retain the current partner proportions when the gross charge changes.
            if income.total_amount:
                update['gustavo_amount'] = quantize_money(document_total * income.gustavo_amount / income.total_amount)
                update['carlos_amount'] = min(document_total - update['gustavo_amount'], quantize_money(document_total * income.carlos_amount / income.total_amount))
            else:
                update['gustavo_amount'], update['carlos_amount'] = split_half(document_total)
            serializer = IncomeRecordCreateUpdateSerializer(instance=income, data=update, partial=True)
            serializer.is_valid(raise_exception=True)
            income = accounting_service.update_record(accounting_service.EntityType.INCOME, income, serializer, acting_user, notify=False)

    customer = _resolve_customer(profile, data.get('customer'))
    # The cuenta inherits the project from its income exactly as it inherits
    # the client: the income is the origin record, and the two must never
    # disagree about which deal is being charged.
    if income.project_id:
        customer['project_name'] = income.project.name
    billing_concept = (
        (data.get('billing_concept') or '').strip() or income.concept
    )

    document_fields = {
        'title': f'Cuenta de cobro — {billing_concept}',
        'document_type': get_collection_account_document_type(),
        'commercial_status': Document.CommercialStatus.DRAFT,
        'client_user': client,
        'income_record': income,
        'project': income.project,
        'client_name': customer['name'],
        'currency': (data.get('currency') or 'COP').upper(),
        'city': data.get('city') or '',
        'notes': data.get('notes') or '',
        'terms_and_conditions': data.get('terms_and_conditions') or '',
        'created_by': acting_user,
        'updated_by': acting_user,
    }
    if data.get('uuid'):
        document_fields['uuid'] = data['uuid']
    document = Document.objects.create(
        **document_fields,
    )
    from accounts.services.billing_context import associate_account
    if document.project_id:
        associate_account(document.pk, acting_user, data, creating=True)
    due_date = data.get('due_date')
    if due_date:
        term_type = DocumentCollectionAccount.PaymentTermType.FIXED_DATE
        term_days = None
        document.due_date = due_date
        document.save(update_fields=['due_date'])
    else:
        term_type = DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE
        # `or` would read a deliberate 0 (immediate payment) as "unset" and
        # silently bill it at the 8-day default, so the term has to be tested
        # against None instead.
        term_days = data.get('payment_term_days')
        if term_days is None:
            term_days = PAYMENT_TERM_DAYS
    DocumentCollectionAccount.objects.create(
        document=document,
        vat_rate=rate,
        billing_concept=billing_concept,
        payment_term_type=term_type,
        payment_term_days=term_days,
        observations=data.get('observations') or '',
    )
    for position, item in enumerate(prepared_items, start=1):
        quantity = item.get('quantity') or Decimal('1')
        unit_price = item['unit_price']
        DocumentItem.objects.create(
            document=document,
            position=position,
            item_type=DocumentItem.ItemType.SERVICE,
            description=(item.get('description') or '').strip() or billing_concept,
            quantity=quantity,
            unit_price=unit_price,
            tax_amount=item['tax_amount'],
            line_total=item['line_total'],
            period_start=item.get('period_start'),
            period_end=item.get('period_end'),
            reference_type='income_record',
            reference_id=income.pk,
        )
    seed_default_payment_methods(document, issuer)

    manual_number = (data.get('public_number') or '').strip() or None
    if issue_document:
        issue_collection_account(
            document,
            issuer=issuer,
            acting_user=acting_user,
            customer=customer,
            number_allocator=lambda: allocate_client_number(
                profile, issuer, manual_number=manual_number,
            ),
            issued_on=issued_on,
        )
    else:
        recalculate_document_totals(document)
        document.save(
            update_fields=['subtotal', 'tax_total', 'total', 'updated_at'],
        )
    # Re-read: creating the extension above primed the reverse one-to-one
    # cache on `document` with the pre-issue row (empty customer snapshot);
    # issue_collection_account saved a different instance.
    return (
        Document.objects.select_related('collection_account')
        .prefetch_related('items', 'payment_methods')
        .get(pk=document.pk)
    )


def create_income_collection_account(
    data, *, acting_user=None, persist_snapshot=True, issued_on=None,
):
    """Draft + issue atomically, archiving the definitive PDF by default.

    The preview endpoint opts out because its surrounding transaction is
    deliberately rolled back and filesystem writes are not transactional.
    """
    from content.services.collection_account_snapshot_service import (
        CollectionAccountSnapshotError,
        discard_stored_collection_account_pdf,
        persist_collection_account_pdf,
    )

    stored = None
    try:
        with transaction.atomic():
            document = _create_income_collection_account(
                data, acting_user=acting_user, issued_on=issued_on,
            )
            if persist_snapshot:
                stored = persist_collection_account_pdf(document)
        return document
    except CollectionAccountSnapshotError as exc:
        discard_stored_collection_account_pdf(stored)
        raise CollectionAccountError(str(exc)) from exc
    except Exception:
        discard_stored_collection_account_pdf(stored)
        raise


@transaction.atomic
def create_income_collection_account_draft(data, *, acting_user=None):
    """Create a coherent editable draft without allocating or archiving a PDF."""
    return _create_income_collection_account(
        data,
        acting_user=acting_user,
        issue_document=False,
    )
