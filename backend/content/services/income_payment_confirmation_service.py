"""Client confirmation that a payment was received, sent while settling an income.

The operator opts in from the Liquidar modal, which shows a last notice with
these same values before the request leaves. The settle view sends only after
the settlement committed, so the client is never told about a payment that a
failed transaction undid.

Split like the cuenta de cobro email: ``build_payment_confirmation_email``
renders with zero side effects and ``send_payment_confirmation_email``
delivers and records. Everything the message states travels in one JSON-safe
``values`` dict that is also stored as the log's metadata, so a retry from
Historial renders the same message instead of re-reading balances that moved.
"""
import logging
from datetime import date
from decimal import Decimal

from content.models import EmailLog, IncomeRecord
from content.serializers.accounting import money_str, paid_total_for_income
from content.services import email_log_service
from content.services.collection_account_email_service import (
    _plain,
    format_cop_email,
)
from content.services.email_delivery_service import (
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.services.email_markdown import markdown_to_email_html
from content.services.income_settlement_policy import (
    MISSING_ACCOUNT_REASON,
    issued_collection_account,
)
from content.utils import SPANISH_MONTHS, format_bogota_date
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'income_payment_received_client'

# A follow-up can itself be settled short and rescheduled again. The chain is
# walked to this depth, far beyond anything the book has produced.
MAX_FOLLOW_UP_DEPTH = 10

NO_CLIENT_REASON = (
    'Este ingreso no tiene cliente: no hay a quién enviar la confirmación.'
)
NO_AMOUNT_REASON = 'Sin valor recibido no hay pago que confirmar.'
SEND_FAILED_REASON = (
    'El correo no salió. Puedes reintentarlo desde Historial › Correos.'
)
UNEXPECTED_REASON = (
    'No se pudo preparar la confirmación de pago; la liquidación sí quedó '
    'registrada.'
)


def rescheduled_pending(income):
    """What the client still owes on follow-ups rescheduled from this income.

    A short settlement can move part of the balance into its own expected
    income, which shrinks this one. Leaving them out, the confirmation of a
    later payment would announce "al día" while a rescheduled installment is
    still due. Each level's pending already excludes its own follow-ups, so
    summing every descendant counts each rescheduled amount once.
    """
    from content.services.accounting_service import paid_amount_subquery

    total = Decimal('0')
    frontier = [income.pk]
    seen = {income.pk}
    for _ in range(MAX_FOLLOW_UP_DEPTH):
        rows = (
            IncomeRecord.objects
            .filter(
                source_ref__in=[f'income:{pk}:settlement' for pk in frontier],
                kind=IncomeRecord.Kind.EXPECTED,
            )
            .annotate(paid_amount=paid_amount_subquery())
            .values_list('pk', 'total_amount', 'paid_amount')
        )
        frontier = []
        for pk, total_amount, paid_amount in rows:
            if pk in seen:
                continue
            seen.add(pk)
            frontier.append(pk)
            total += max(total_amount - paid_amount, Decimal('0'))
        if not frontier:
            break
    return total


def _recipient_problem(recipient):
    """Why this address cannot receive the confirmation, or ''."""
    from accounts.models import UserProfile

    if not recipient:
        return 'La cuenta de cobro no tiene el correo del cliente.'
    if recipient.lower().endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN):
        return (
            f'El correo del cliente ({recipient}) es provisional; '
            'actualízalo en su ficha.'
        )
    try:
        validate_email(recipient)
    except ValidationError:
        return f'El correo del cliente ({recipient}) no es válido.'
    return ''


def confirmation_context(income):
    """Who would receive the confirmation, or why it cannot go. Read-only.

    The single source for the panel's checkbox and last notice, the send
    itself and the MCP preview, so the three always name the same address:
    the one the issued cuenta de cobro went to.
    """
    from accounts.services.proposal_client_service import (
        build_client_display_name,
    )

    context = {
        'can_send': False,
        'blocked_reason': '',
        'recipient': '',
        'client_name': '',
        'project_name': income.project.name if income.project_id else '',
        'collection_account_id': None,
        'collection_account_number': '',
        'greeting_name': '',
        'rescheduled_pending': money_str(0),
    }
    if not income.client_id:
        context['blocked_reason'] = NO_CLIENT_REASON
        return context
    context['client_name'] = build_client_display_name(income.client)
    context['rescheduled_pending'] = money_str(rescheduled_pending(income))
    account = issued_collection_account(income)
    if account is None:
        context['blocked_reason'] = MISSING_ACCOUNT_REASON
        return context
    extension = account.collection_account
    recipient = (extension.customer_email or '').strip()
    context.update({
        'recipient': recipient,
        'collection_account_id': account.pk,
        'collection_account_number': account.public_number or '',
        'greeting_name': (
            extension.customer_contact_name or extension.customer_name
            or context['client_name']
        ),
    })
    problem = _recipient_problem(recipient)
    context['blocked_reason'] = problem
    context['can_send'] = not problem
    return context


# Every fact the email states; the log's metadata stores exactly these, next
# to whatever bookkeeping the delivery gateway adds on its own.
VALUE_KEYS = (
    'income_id', 'liquid_id', 'document_id', 'public_number', 'greeting_name',
    'concept', 'project_name', 'amount', 'payment_date',
    'payment_date_precision', 'pending_after',
)


def values_from_metadata(metadata):
    """The stored facts of a sent confirmation, for an identical retry."""
    metadata = metadata or {}
    return {key: metadata.get(key) for key in VALUE_KEYS}


def payment_date_label(value, precision):
    """'Jue, 16 jul 2026', or 'julio de 2026' when only the month is known."""
    if precision == 'month':
        return f'{SPANISH_MONTHS[value.month]} de {value.year}'
    return format_bogota_date(value)


def settlement_values(income, liquid, data, context):
    """The JSON-safe facts one confirmation states, read after the commit."""
    parent_pending = max(
        income.total_amount - paid_total_for_income(income), Decimal('0'),
    )
    pending_after = parent_pending + Decimal(context['rescheduled_pending'])
    return {
        'income_id': income.pk,
        'liquid_id': liquid.pk,
        'document_id': context['collection_account_id'],
        'public_number': context['collection_account_number'],
        'greeting_name': context['greeting_name'],
        'concept': liquid.concept,
        'project_name': context['project_name'],
        'amount': money_str(liquid.total_amount),
        'payment_date': liquid.period_date.isoformat(),
        'payment_date_precision': data.get('period_date_precision', 'day'),
        'pending_after': money_str(pending_after),
    }


def build_payment_confirmation_email(values):
    """Subject + rendered bodies for the client confirmation. No side effects."""
    number = values.get('public_number') or ''
    payment_date = date.fromisoformat(values['payment_date'])
    pending = Decimal(values['pending_after'])

    # One field per list item: the Markdown parser folds single newlines into
    # one paragraph, so the list is what keeps each figure on its own line.
    details = []
    if number:
        details.append(f'- Cuenta de cobro: **{number}**')
    details.append(f'- Concepto: **{values["concept"]}**')
    if values.get('project_name'):
        details.append(f'- Proyecto: **{values["project_name"]}**')
    details.append(
        f'- Valor recibido: **${format_cop_email(Decimal(values["amount"]))} COP**'
    )
    details.append(
        '- Fecha de pago: '
        f'**{payment_date_label(payment_date, values.get("payment_date_precision"))}**'
    )
    markdown_sections = [
        'Te confirmamos que recibimos tu pago. ¡Muchas gracias!',
        '\n'.join(details),
        (
            f'Saldo pendiente: **${format_cop_email(pending)} COP**.'
            if pending > 0 else 'Con este pago quedaste **al día**.'
        ),
        (
            'Si tienes alguna pregunta sobre este pago, responde este correo '
            'y con gusto te ayudamos.'
        ),
    ]
    text_sections = [_plain(section) for section in markdown_sections]
    html_sections = [
        {'html': html} if (html := markdown_to_email_html(section)) else plain
        for section, plain in zip(markdown_sections, text_sections)
    ]

    subject = (
        f'Confirmación de pago — Cuenta de cobro {number}' if number
        else 'Confirmación de pago — ProjectApp'
    )
    greeting_name = values.get('greeting_name') or ''
    greeting = f'Hola {greeting_name}' if greeting_name else 'Hola'
    context = {
        'subject': subject,
        'greeting': greeting,
        'footer': '',
        'attachment_names': [],
    }
    from content.services.proposal_email_service import _build_design_context

    context.update(_build_design_context())
    return {
        'subject': subject,
        'greeting': greeting,
        'sections': text_sections,
        'html_body': render_to_string(
            'emails/branded_email.html', {**context, 'sections': html_sections},
        ),
        'text_body': render_to_string(
            'emails/branded_email.txt', {**context, 'sections': text_sections},
        ),
    }


def _targets(values):
    targets = [
        ('income', values['income_id'], ''),
        ('income', values['liquid_id'], ''),
    ]
    if values.get('document_id'):
        targets.append((
            'collection_account', values['document_id'],
            values.get('public_number') or '',
        ))
    return targets


def send_payment_confirmation_email(values, *, recipient, client=None, retry_of=None):
    """Build, deliver and record one confirmation. True on success.

    A transport failure is recorded as a FAILED row with the full body, which
    is what lets Historial retry it, and returns False instead of raising.
    """
    email_parts = build_payment_confirmation_email(values)
    log_fields = {
        'template_key': TEMPLATE_KEY,
        'recipients': [recipient],
        'subject': email_parts['subject'],
        'metadata': values,
        'targets': _targets(values),
        'html_body': email_parts['html_body'],
        'text_body': email_parts['text_body'],
        'retry_of': retry_of,
        'client': client,
        'audience': EmailLog.Audience.CLIENT,
    }
    try:
        # A finite SMTP deadline: this send runs inside the settle request.
        email = EmailMultiAlternatives(
            subject=email_parts['subject'],
            body=email_parts['text_body'],
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co'),
            to=[recipient],
            connection=EmailDeliveryGateway.bounded_connection(timeout_seconds=20),
        )
        email.attach_alternative(email_parts['html_body'], 'text/html')
        if not EmailDeliveryGateway.send(email, template_key=TEMPLATE_KEY):
            raise RuntimeError('El servidor de correo no aceptó el mensaje.')
    except Exception as exc:
        logger.warning(
            'Failed to send the payment confirmation of income %s to %s: %s',
            values.get('income_id'), recipient, exc,
        )
        email_log_service.record_send(
            status=EmailLog.Status.FAILED, error_message=str(exc), **log_fields,
        )
        return False
    email_log_service.record_send(status=EmailLog.Status.SENT, **log_fields)
    logger.info(
        'Sent the payment confirmation of income %s to %s',
        values.get('income_id'), recipient,
    )
    return True


def _block(status, *, requested=True, recipient='', error=''):
    return {
        'requested': requested,
        'status': status,
        'recipient': recipient,
        'error': error,
    }


def _reloaded(income):
    return (
        IncomeRecord.objects
        .select_related('client__user', 'project')
        .get(pk=income.pk)
    )


def confirm_settlement(result, data):
    """Send the confirmation the operator asked for. Never raises.

    Call it only after the settlement committed. A settlement that cannot be
    confirmed still stands — the payment is real and registering it is the
    operation, the email its courtesy — so the block says what happened and
    the panel warns instead of reporting a silent success. Raising here would
    turn a committed settlement into a 500 and invite a second one.
    """
    if not data.get('send_payment_confirmation'):
        return _block('not_requested', requested=False)
    liquid = result.get('liquid')
    if liquid is None:
        return _block('skipped', error=NO_AMOUNT_REASON)
    try:
        income = _reloaded(result['income'])
        context = confirmation_context(income)
        if not context['can_send']:
            return _block('skipped', error=context['blocked_reason'])
        values = settlement_values(income, liquid, data, context)
        sent = send_payment_confirmation_email(
            values, recipient=context['recipient'], client=income.client,
        )
    except Exception:
        logger.exception(
            'Payment confirmation for income %s could not be prepared.',
            result['income'].pk,
        )
        return _block('skipped', error=UNEXPECTED_REASON)
    if not sent:
        return _block(
            'failed', recipient=context['recipient'], error=SEND_FAILED_REASON,
        )
    return _block('sent', recipient=context['recipient'])


def schedule_confirmation(result, data):
    """MCP variant: the tool call runs inside a transaction, so wait for it.

    The result cannot know the outcome yet; it reports ``scheduled`` and the
    delivery lands in the email history like any other send.
    """
    if not data.get('send_payment_confirmation'):
        return _block('not_requested', requested=False)
    if result.get('liquid') is None:
        return _block('skipped', error=NO_AMOUNT_REASON)
    context = confirmation_context(_reloaded(result['income']))
    if not context['can_send']:
        return _block('skipped', error=context['blocked_reason'])
    transaction.on_commit(lambda: confirm_settlement(result, data), robust=True)
    return _block('scheduled', recipient=context['recipient'])


def preview_confirmation(income, data):
    """What a confirmed settlement would send, estimated before any write.

    ``data`` is validated settlement data. The pending balance mirrors the
    panel's last notice: received money and deductions reduce it, while
    follow-ups only move part of it into another expected income.
    """
    context = confirmation_context(income)
    preview = {
        'can_send': context['can_send'],
        'blocked_reason': context['blocked_reason'],
        'recipient': context['recipient'],
        'collection_account_number': context['collection_account_number'],
    }
    if not context['can_send']:
        return preview
    received = data['total_amount']
    if received <= 0:
        return {**preview, 'can_send': False, 'blocked_reason': NO_AMOUNT_REASON}
    deducted = sum(
        (deduction['amount'] for deduction in data.get('deductions') or []),
        Decimal('0'),
    )
    parent_pending = max(
        income.total_amount - paid_total_for_income(income), Decimal('0'),
    )
    pending_after = (
        max(parent_pending - received - deducted, Decimal('0'))
        + Decimal(context['rescheduled_pending'])
    )
    values = {
        'income_id': income.pk,
        'liquid_id': None,
        'document_id': context['collection_account_id'],
        'public_number': context['collection_account_number'],
        'greeting_name': context['greeting_name'],
        'concept': data['concept'],
        'project_name': context['project_name'],
        'amount': money_str(received),
        'payment_date': data['period_date'].isoformat(),
        'payment_date_precision': data.get('period_date_precision', 'day'),
        'pending_after': money_str(pending_after),
    }
    email = build_payment_confirmation_email(values)
    return {
        **preview,
        'subject': email['subject'],
        'text_body': email['text_body'],
        'pending_after': values['pending_after'],
    }
