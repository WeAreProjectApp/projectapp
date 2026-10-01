"""Cuenta de cobro (collection account) flow for accounting hostings.

The panel action "Enviar cuenta de cobro" on a HostingRecord:
1. Creates a draft Document + DocumentCollectionAccount for the next
   billing period (valid_to → valid_to + modality months).
2. Issues it (public number, payer/customer snapshots — the customer
   comes from the hosting's client fields, not a platform user).
3. Emails the client the branded message with the PDF attached.
4. Stamps `billing_requested_at` on the hosting, silencing the expiry
   notice cadence until the next renewal (hosting_expiry_service).

The document stays issued even when the email fails: the admin re-sends
it from the Cobros tab.
"""
import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from content.models import (
    Document,
    DocumentCollectionAccount,
    DocumentItem,
    HostingRecord,
)
from content.services.collection_account_email_service import (
    TEMPLATE_KEY,
    send_collection_account_email,
)
from content.services.collection_account_create_service import (
    client_legal_identity,
)
from content.services.collection_account_numbering import allocate_client_number
from content.services.collection_account_service import (
    CollectionAccountError,
    get_default_issuer,
    issue_collection_account,
    seed_default_payment_methods,
)
from content.services.collection_account_snapshot_service import (
    CollectionAccountSnapshotError,
    discard_stored_collection_account_pdf,
    persist_collection_account_pdf,
)
from content.services.document_type_utils import (
    get_collection_account_document_type,
)
from content.utils import add_months, today_bogota

__all__ = [
    'HostingBillingError',
    'TEMPLATE_KEY',
    'create_hosting_collection_account',
    'next_billing_period',
    'resend_collection_account_email',
    'send_hosting_collection_account',
]

logger = logging.getLogger(__name__)

PAYMENT_TERM_DAYS = 8


class HostingBillingError(Exception):
    """Invalid state or input for the hosting cuenta de cobro flow."""


def next_billing_period(hosting):
    """(from, to) of the period being billed: valid_to plus one modality."""
    months = HostingRecord.MODALITY_MONTHS.get(hosting.payment_modality, 1)
    period_from = hosting.valid_to or today_bogota()
    return period_from, add_months(period_from, months)


def _default_issuer():
    try:
        return get_default_issuer()
    except CollectionAccountError as exc:
        raise HostingBillingError(str(exc)) from exc


@transaction.atomic
def create_hosting_collection_account(hosting, *, acting_user=None, hosting_payment_id=None):
    """Draft Document + extension + line item + default payment methods."""
    period_from, period_to = next_billing_period(hosting)
    # What is being hosted, not who pays for it: with no domain the project
    # names the service ("hosting Kore"), the client half never did.
    label = hosting.domain_url or hosting.project_name or hosting.client_name
    document = Document.objects.create(
        title=f'Cuenta de cobro — hosting {label}',
        document_type=get_collection_account_document_type(),
        commercial_status=Document.CommercialStatus.DRAFT,
        hosting_record=hosting,
        client_user=hosting.client.user if hosting.client_id else None,
        project=hosting.project,
        currency='COP',
        created_by=acting_user,
        updated_by=acting_user,
    )
    if hosting.project_id:
        from accounts.models import ProjectHostingAccountingSource
        from accounts.services.billing_context import associate_account
        source = ProjectHostingAccountingSource.objects.filter(hosting_record=hosting).first()
        if not source:
            raise HostingBillingError('Hosting pendiente de asociar: concilia el origen del proyecto antes de emitir.')
        associate_account(document.pk, acting_user, {
            'billing_nature': 'hosting', 'project_hosting_id': source.hosting_id,
            'hosting_payment_id': hosting_payment_id,
        }, creating=True)
    DocumentCollectionAccount.objects.create(
        document=document,
        billing_concept=f'Servicio de hosting {label}',
        payment_term_type=DocumentCollectionAccount.PaymentTermType.DAYS_AFTER_ISSUE,
        payment_term_days=PAYMENT_TERM_DAYS,
    )
    DocumentItem.objects.create(
        document=document,
        position=1,
        item_type=DocumentItem.ItemType.HOSTING,
        description=(
            f'Servicio de hosting {label} — período '
            f'{period_from:%d/%m/%Y} a {period_to:%d/%m/%Y}'
        ),
        quantity=1,
        unit_price=hosting.payment_per_cycle,
        line_total=hosting.payment_per_cycle,
        period_start=period_from,
        period_end=period_to,
        reference_type='hosting_record',
        reference_id=hosting.pk,
    )
    seed_default_payment_methods(document, _default_issuer())
    return document


def send_hosting_collection_account(hosting, *, acting_user=None, hosting_payment_id=None):
    """Create + issue + email the cuenta de cobro. Returns
    {'document': Document, 'email_sent': bool}."""
    from content.services.project_state_service import project_allows_billing

    if hosting.project_id and not project_allows_billing(hosting.project):
        raise HostingBillingError(
            'El estado actual del proyecto no permite generar nuevos cobros.'
        )
    recipient = hosting.billing_email
    if not recipient:
        raise HostingBillingError(
            'El hosting no tiene a quién enviarle la cuenta: vincula un '
            'cliente con correo o escribe un email de facturación.',
        )
    if not hosting.payment_per_cycle or hosting.payment_per_cycle <= 0:
        raise HostingBillingError(
            'El hosting no tiene un pago por ciclo configurado.',
        )
    already_billed = (
        hosting.billing_requested_at is not None
        and hosting.collection_documents.exclude(
            commercial_status=Document.CommercialStatus.CANCELLED,
        ).exists()
    )
    if already_billed:
        raise HostingBillingError(
            'Ya se envió la cuenta de cobro de este período; '
            'usa "Reenviar" en el tab Cuentas de cobro.',
        )

    issuer = _default_issuer()
    profile = hosting.client
    # With a client linked the cuenta joins that client's own series, so
    # "how many cuentas have I issued to them" finally counts its hostings.
    # Records still pending assignment keep the legacy per-issuer series.
    allocator = (
        (lambda: allocate_client_number(profile, issuer)) if profile else None
    )
    # `client_name` is a free-text label following the house convention
    # `Persona - Marca` ("German - Kore"), so using it as the legal name put
    # a person and a brand fused together on the cobro. With a client linked,
    # the legal holder comes from the profile — the same rule the panel flow
    # uses — and the brand half now travels as the project line instead.
    # Unlinked legacy records keep the label: it is all they have.
    if profile:
        legal_name, legal_id, legal_id_type, contact = client_legal_identity(
            profile,
        )
    else:
        legal_name, legal_id, legal_id_type, contact = (
            hosting.client_name,
            hosting.client_identification,
            '',
            hosting.client_contact_name,
        )
    stored = None
    try:
        with transaction.atomic():
            document = create_hosting_collection_account(
                hosting, acting_user=acting_user, hosting_payment_id=hosting_payment_id,
            )
            issue_collection_account(
                document,
                issuer=issuer,
                acting_user=acting_user,
                customer={
                    'name': legal_name,
                    'email': recipient,
                    'identification': hosting.client_identification or legal_id,
                    'identification_type': legal_id_type,
                    'contact_name': hosting.client_contact_name or contact,
                    'project_name': (
                        hosting.project.name if hosting.project_id else ''
                    ),
                },
                number_allocator=allocator,
            )

            # Re-read: the in-memory document may cache the pre-issue extension
            # (empty customer snapshot) via the reverse one-to-one descriptor.
            document = (
                Document.objects.select_related('collection_account')
                .prefetch_related('items', 'payment_methods')
                .get(pk=document.pk)
            )
            stored = persist_collection_account_pdf(document)
    except (CollectionAccountError, CollectionAccountSnapshotError) as exc:
        discard_stored_collection_account_pdf(stored)
        raise HostingBillingError(str(exc)) from exc
    except Exception:
        discard_stored_collection_account_pdf(stored)
        raise

    email_sent = _send_client_email(document, hosting=hosting)

    # Silence the expiry cadence for this period even if the email failed:
    # the document is issued and can be re-sent from Cobros.
    HostingRecord.objects.filter(pk=hosting.pk).update(
        billing_requested_at=timezone.now(),
        expiry_notice_target=F('valid_to'),
    )
    return {'document': document, 'email_sent': email_sent}


def resend_collection_account_email(document, *, acting_user=None):
    """Re-send the client email of an issued/paid collection account."""
    extension = getattr(document, 'collection_account', None)
    if extension is None or not extension.customer_email:
        raise HostingBillingError(
            'La cuenta de cobro no tiene un email de cliente.',
        )
    if document.commercial_status not in (
        Document.CommercialStatus.ISSUED,
        Document.CommercialStatus.PAID,
    ):
        raise HostingBillingError(
            'Solo se pueden reenviar cuentas de cobro emitidas.',
        )
    return _send_client_email(document, resend=True)


def _send_client_email(document, *, hosting=None, resend=False):
    """Delegation seam: existing tests patch this name to intercept sends."""
    return send_collection_account_email(
        document, hosting=hosting, resend=resend,
    )
