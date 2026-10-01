"""
Business rules for collection account documents: numbering, totals, lifecycle transitions.
"""
from content.services.entity_history import historical_write
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date

from content.models import (
    AccountingChangeLog,
    CompanySettings,
    Document,
    DocumentCollectionAccount,
    DocumentNumberSequence,
    DocumentPaymentMethod,
    EmailLog,
    EmailLogTarget,
    IssuerProfile,
)
from content.services.document_type_codes import COLLECTION_ACCOUNT
from content.services.generated_document_filing_service import (
    file_collection_account,
)
from content.utils import today_bogota


class CollectionAccountError(Exception):
    """Invalid state or input for collection account operations."""


def get_default_issuer():
    """First IssuerProfile by pk — the module's single-issuer convention."""
    issuer = IssuerProfile.objects.order_by('pk').first()
    if issuer is None:
        raise CollectionAccountError(
            'No hay un perfil emisor (IssuerProfile) configurado.',
        )
    return issuer


def default_payment_methods_config(issuer):
    """Payment methods a new collection account starts with.

    The bank transfer comes from ``CompanySettings`` — the same singleton that
    fills the contract's payment clause — so the account only has to be updated
    in one place to change every document that names it. The issuer's own
    ``default_payment_methods`` are kept and appended after it: that JSON stays
    the place to add a second channel (Nequi, Daviplata) without a migration.
    """
    company = CompanySettings.load()
    methods = []
    # A half-configured install would otherwise print a payment block with the
    # labels and no data, which reads worse than no block at all.
    if company.bank_name and company.bank_account_number:
        id_label, id_number = company.contractor_identity
        methods.append({
            'payment_method_type': DocumentPaymentMethod.MethodType.BANK_TRANSFER,
            'bank_name': company.bank_name,
            'account_type': company.bank_account_type,
            'account_number': company.bank_account_number,
            'account_holder_name': company.contractor_full_name,
            'account_holder_identification': f'{id_label} {id_number}'.strip(),
        })
    methods.extend(issuer.default_payment_methods or [])
    return methods


def seed_default_payment_methods(document, issuer):
    """Snapshot the configured payment methods onto the document.

    A snapshot, not a live read: a cuenta de cobro already freezes its payer and
    customer at issue time, and a document reissued after the bank account
    changed must keep naming the account the client was told to pay into.
    """
    for position, method in enumerate(default_payment_methods_config(issuer)):
        DocumentPaymentMethod.objects.create(
            document=document,
            payment_method_type=method.get('payment_method_type', 'bank_transfer'),
            bank_name=method.get('bank_name', ''),
            account_type=method.get('account_type', ''),
            account_number=method.get('account_number', ''),
            account_holder_name=method.get('account_holder_name', ''),
            account_holder_identification=method.get(
                'account_holder_identification', '',
            ),
            payment_instructions=method.get('payment_instructions', ''),
            is_primary=position == 0,
        )


def is_collection_account(document):
    dt = document.document_type
    return dt is not None and dt.code == COLLECTION_ACCOUNT


def commercial_is_overdue(document):
    """
    Derived overdue: issued, past due_date, not paid or cancelled.
    """
    if not is_collection_account(document):
        return False
    if document.commercial_status != Document.CommercialStatus.ISSUED:
        return False
    due = document.due_date
    if not due:
        return False
    if isinstance(due, str):
        due = parse_date(due)
        if due is None:
            return False
    return due < today_bogota()


def recalculate_document_totals(document):
    """Aggregate line items into document money fields."""
    lines = list(document.items.all())
    if not lines:
        document.subtotal = Decimal('0')
        document.tax_total = Decimal('0')
        document.total = Decimal('0') - document.discount_total
        return

    subtotal = sum(
        (li.quantity * li.unit_price - li.discount_amount for li in lines),
        Decimal('0'),
    )
    tax_total = sum((li.tax_amount for li in lines), Decimal('0'))
    line_sum = sum((li.line_total for li in lines), Decimal('0'))
    document.subtotal = subtotal
    document.tax_total = tax_total
    document.total = line_sum - document.discount_total


@historical_write
@transaction.atomic
def allocate_public_number(issuer):
    """Thread-safe next public_number for issuer and current Bogotá year."""
    year = today_bogota().year
    seq, _ = DocumentNumberSequence.objects.select_for_update().get_or_create(
        issuer=issuer,
        year=year,
        defaults={'last_value': 0},
    )
    DocumentNumberSequence.objects.filter(pk=seq.pk).update(last_value=F('last_value') + 1)
    seq.refresh_from_db()
    prefix = (issuer.public_number_prefix or 'PA').strip() or 'PA'
    return f'{prefix}-{year}-{seq.last_value:04d}'


def resolve_client_user(document):
    """The client behind a document: linked directly, or through its project.

    Public because the numbering helper answers "whose series is this?" from
    the same two places, and the two answers must never diverge.
    """
    if document.client_user_id:
        return document.client_user
    if document.project_id:
        return document.project.client
    return None


def _fill_payer_from_issuer(extension, issuer):
    extension.payer_name = issuer.legal_name or issuer.name
    extension.payer_identification = issuer.identification_number
    extension.payer_identification_type = issuer.identification_type
    extension.payer_address = issuer.address
    extension.payer_phone = issuer.phone
    extension.payer_email = issuer.email or ''


def _fill_customer_from_data(extension, customer):
    """Snapshot customer fields from an explicit dict (no platform user)."""
    extension.customer_name = customer.get('name', '')
    extension.customer_email = customer.get('email', '')
    extension.customer_identification = customer.get('identification', '')
    extension.customer_identification_type = customer.get('identification_type', '')
    extension.customer_contact_name = customer.get('contact_name', '')
    extension.customer_address = customer.get('address', '')
    extension.customer_project_name = customer.get('project_name', '')


def _fill_customer_from_user(extension, user, project=None):
    """Snapshot the customer from a platform user.

    Defers to the same legal-identity rule the panel flow uses, so the
    platform-issued document cannot name the party differently from a
    panel-issued one for the same client.
    """
    from content.services.collection_account_create_service import (
        client_legal_identity,
    )

    profile = getattr(user, 'profile', None)
    full_name = f'{user.first_name} {user.last_name}'.strip()
    if profile is None:
        extension.customer_name = full_name or user.email
        extension.customer_email = user.email or ''
        extension.customer_identification = ''
        extension.customer_identification_type = ''
        extension.customer_contact_name = full_name
    else:
        name, identification, identification_type, contact_name = (
            client_legal_identity(profile)
        )
        extension.customer_name = name
        extension.customer_email = user.email or ''
        extension.customer_identification = identification
        extension.customer_identification_type = identification_type
        extension.customer_contact_name = contact_name
    extension.customer_project_name = project.name if project else ''


@historical_write
@transaction.atomic
def issue_collection_account(
    document,
    *,
    issuer,
    acting_user=None,
    customer=None,
    number_allocator=None,
    issued_on=None,
):
    """
    Transition draft -> issued: allocate public number, set dates, snapshot payer/customer.

    ``customer`` (optional dict: name, email, identification,
    identification_type, contact_name, address) snapshots the customer
    explicitly for documents without a platform user (e.g. hosting-driven
    cuentas de cobro). Without it, the customer resolves from
    ``client_user`` / ``project.client`` as before.

    ``number_allocator`` (optional zero-arg callable) overrides the default
    per-issuer series — the income flow passes the per-client allocator.
    """
    original_document = document
    from accounts.services.billing_locks import lock_billing_document
    document = lock_billing_document(document.pk)
    if document is None or not is_collection_account(document):
        raise CollectionAccountError('Document is not a collection account.')
    if document.commercial_status != Document.CommercialStatus.DRAFT:
        raise CollectionAccountError('Only draft documents can be issued.')

    from accounts.services.billing_context import validate_account_context
    from rest_framework.exceptions import ValidationError
    try:
        validate_account_context(document)
    except ValidationError as exc:
        detail = exc.detail.get('detail', exc.detail) if isinstance(exc.detail, dict) else exc.detail
        raise CollectionAccountError(str(detail)) from exc
    ext, _ = DocumentCollectionAccount.objects.get_or_create(document=document)

    _fill_payer_from_issuer(ext, issuer)

    if customer is not None:
        if not customer.get('name') or not customer.get('email'):
            raise CollectionAccountError('customer requires name and email.')
        _fill_customer_from_data(ext, customer)
    else:
        client_user = resolve_client_user(document)
        if not client_user:
            raise CollectionAccountError('client_user or project with client is required to issue.')
        _fill_customer_from_user(
            ext, client_user, project=document.project if document.project_id else None,
        )

    today = issued_on or today_bogota()
    document.issue_date = today
    document.issuer = issuer
    if not document.city:
        document.city = issuer.city or ''
    document.public_number = (
        number_allocator() if number_allocator else allocate_public_number(issuer)
    )

    ptt = ext.payment_term_type
    if ptt == DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE:
        # A zero-day term is immediate payment against presentation, so there is
        # no deadline to state. Storing the issue date as the due date printed
        # the same date twice on the PDF and, worse, turned the cuenta overdue
        # the very next day. No date is what "no plazo" actually means.
        days = ext.payment_term_days or 0
        document.due_date = today + timedelta(days=days) if days else None
    elif ptt == DocumentCollectionAccount.PaymentTermType.FIXED_DATE:
        if not document.due_date:
            raise CollectionAccountError('due_date is required for fixed_date payment term.')
    # against_delivery is that same immediate payment reached through the term
    # type instead of through a zero, so it no longer invents the issue date as
    # a deadline either. A date set explicitly on the draft still stands.

    recalculate_document_totals(document)
    old_values = _status_snapshot(document)
    document.commercial_status = Document.CommercialStatus.ISSUED
    document.updated_by = acting_user
    file_collection_account(document)
    document.save()
    ext.save()
    _log_status_transition(document, old_values, acting_user)
    # Preserve the public service's in-memory update contract for callers that
    # archive the PDF from the supplied instance. This is a current read too.
    original_document.refresh_from_db(from_queryset=Document.objects.select_for_update())
    return original_document


def _status_snapshot(document):
    from content.services import accounting_service

    return accounting_service.snapshot_values(
        document, accounting_service.EntityType.COLLECTION_ACCOUNT,
    )


def _log_status_transition(document, old_values, acting_user):
    """Audit row for a lifecycle transition (issue/paid/cancel).

    This is what makes anular-y-reemitir reconstructable next to the
    client/project reassignments: the trail says WHEN each cuenta changed
    state and by whom, in the same table. Local import — this module is
    itself imported from accounting paths.
    """
    from content.services import accounting_service

    accounting_service.log_entity_diff(
        accounting_service.EntityType.COLLECTION_ACCOUNT,
        document, old_values, acting_user,
    )


@historical_write
@transaction.atomic
def mark_collection_account_paid(document, *, acting_user=None):
    if not is_collection_account(document):
        raise CollectionAccountError('Document is not a collection account.')
    if document.commercial_status == Document.CommercialStatus.PAID:
        return document
    if document.commercial_status != Document.CommercialStatus.ISSUED:
        raise CollectionAccountError('Only issued accounts can be marked paid.')
    old_values = _status_snapshot(document)
    document.commercial_status = Document.CommercialStatus.PAID
    document.updated_by = acting_user
    document.save(update_fields=['commercial_status', 'updated_by', 'updated_at'])
    _log_status_transition(document, old_values, acting_user)
    return document


@historical_write
@transaction.atomic
def mark_collection_account_cancelled(document, *, acting_user=None):
    if not is_collection_account(document):
        raise CollectionAccountError('Document is not a collection account.')
    if document.commercial_status == Document.CommercialStatus.CANCELLED:
        file_collection_account(document)
        return document
    if document.commercial_status == Document.CommercialStatus.PAID:
        raise CollectionAccountError('Paid documents cannot be cancelled.')
    if document.commercial_status not in (
        Document.CommercialStatus.DRAFT,
        Document.CommercialStatus.ISSUED,
    ):
        raise CollectionAccountError('Only draft or issued accounts can be cancelled.')
    old_values = _status_snapshot(document)
    document.commercial_status = Document.CommercialStatus.CANCELLED
    document.updated_by = acting_user
    file_collection_account(document)
    document.save(update_fields=['commercial_status', 'updated_by', 'updated_at'])
    _log_status_transition(document, old_values, acting_user)
    return document


def collection_account_was_delivered(document):
    """True when a client email carrying this cuenta actually left the system.

    There is no "enviada" status to read: creating a cuenta issues and emails it
    in the same act, so the only record of the send is ``EmailLogTarget`` — a
    table deliberately keyed by ``entity_type`` + ``object_id`` with no FK, so
    the trail outlives the document it describes.

    Anything that is not an outright send FAILURE counts as delivered. A bounce
    cannot prove the client never got it, and for a document carrying a
    consecutivo the bias belongs on the side of NOT deleting.
    """
    return EmailLogTarget.objects.filter(
        entity_type=AccountingChangeLog.EntityType.COLLECTION_ACCOUNT,
        object_id=document.pk,
    ).exclude(email_log__status=EmailLog.Status.FAILED).exists()


@historical_write
@transaction.atomic
def delete_collection_account(document, *, acting_user=None):
    """Physically remove a cuenta that never should have existed.

    Eliminar is not anular. Anular says the document stopped being valid and
    keeps it in the list, which is what a document the client already holds
    deserves. Eliminar is for the one created by mistake — wrong client,
    duplicated, wrong amount — and it is only allowed when nobody outside can
    still be treating it as live: either the cuenta never reached the client,
    or it was already annulled, which is what told the client it no longer
    counts. A paid cuenta is a closed road: it cannot be deleted, and the
    cancel rule already refuses to annul it.

    The row goes; the trail stays. ``AccountingChangeLog`` and
    ``EmailLogTarget`` keep ``object_id`` + ``object_repr`` with no FK, so the
    history can still name the consecutivo that was removed. The number itself
    is never reclaimed — ``last_value`` only moves forward — so the series
    keeps an explainable hole instead of two documents sharing a number.

    Nothing has to be done about the linked income: "already billed" is derived
    from the existence of a non-cancelled cuenta, so the row's disappearance is
    what frees it.
    """
    if not is_collection_account(document):
        raise CollectionAccountError('Document is not a collection account.')
    if document.commercial_status == Document.CommercialStatus.PAID:
        raise CollectionAccountError('Una cuenta pagada no se puede eliminar.')
    if (
        document.commercial_status != Document.CommercialStatus.CANCELLED
        and collection_account_was_delivered(document)
    ):
        raise CollectionAccountError(
            'Esta cuenta de cobro ya se envió al cliente. Anúlala en vez de '
            'eliminarla.',
        )
    from accounts.models import HostingEvidence
    if HostingEvidence.objects.filter(document=document).exists():
        raise CollectionAccountError(
            'La cuenta tiene evidencia de hosting conciliada. Corrige su grupo '
            'administrativo antes de eliminarla; los pagos y ciclos se conservan.',
        )

    from content.services import accounting_service

    # Before the delete: the helper reads the pk and the repr off the instance.
    accounting_service.log_entity_removal(
        accounting_service.EntityType.COLLECTION_ACCOUNT,
        document,
        acting_user,
    )
    generated_storage = (
        document.generated_file.storage if document.generated_file else None
    )
    generated_name = document.generated_file.name if document.generated_file else ''
    document.delete()
    if generated_storage is not None and generated_name:
        # Filesystem/object storage is not transactional. Delete only after the
        # database removal commits; a rollback must leave the immutable PDF.
        transaction.on_commit(
            lambda: generated_storage.delete(generated_name),
            robust=True,
        )


def assert_draft_for_mutation(document):
    if not is_collection_account(document):
        raise CollectionAccountError('Document is not a collection account.')
    if document.commercial_status != Document.CommercialStatus.DRAFT:
        raise CollectionAccountError('Only draft collection accounts can be edited.')
