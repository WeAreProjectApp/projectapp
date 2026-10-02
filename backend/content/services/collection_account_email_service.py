"""Client email for a cuenta de cobro, split in build vs send.

``build_collection_account_email`` renders subject + bodies with zero side
effects — the preview endpoint reuses it, so what the operator previews is
by construction what ``send_collection_account_email`` sends (same sections,
same branded shell, same PDF service on the send side).

Sections are authored in Markdown so the figures the client has to act on —
period, amount, deadline, account number — can carry emphasis. The branded
shell renders a section as raw HTML when it arrives as ``{'html': ...}``
(emails/branded_email.html), and ``markdown_to_email_html`` escapes every
character before emitting a tag, so the conversion is safe by construction.
"""
import logging
import re

from django.conf import settings
from django.template.loader import render_to_string

from content.models import EmailLog
from content.services import email_log_service
from content.services.collection_account_snapshot_service import (
    stored_collection_account_pdf,
)
from content.services.email_markdown import markdown_to_email_html
from content.services.email_delivery_service import (
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.utils import format_bogota_date, format_cop_email

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'collection_account_sent'

_BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
_HEADING_RE = re.compile(r'^#{1,3} ', re.MULTILINE)


def _plain(markdown_text):
    """The same section without its Markdown markers, for the text/plain part.

    The multipart alternative is a real fallback, not a formality: leaving the
    asterisks in it would show them verbatim to anyone reading in plain text.
    """
    return _BOLD_RE.sub(r'\1', _HEADING_RE.sub('', markdown_text))


def _payment_methods_section(document):
    """Payment data as its own Markdown block, or '' when none is configured.

    Blank lines matter here: the Markdown parser folds single newlines into one
    paragraph, so a list is what keeps each field on its own line.
    """
    methods = list(document.payment_methods.all())
    if not methods:
        return ''
    parts = ['### Formas de pago']
    for method in methods:
        holder = method.account_holder_name
        if method.account_holder_identification:
            holder = (
                f'{holder} ({method.account_holder_identification})' if holder
                else method.account_holder_identification
            )
        lines = [f'**{method.get_payment_method_type_display()}**', '']
        lines.extend(
            f'- {label}: **{value}**'
            for label, value in (
                ('Entidad', method.bank_name),
                ('Tipo de cuenta', method.account_type),
                ('Número de cuenta', method.account_number),
                ('Titular', holder),
            ) if value
        )
        if method.payment_instructions:
            lines.extend(['', method.payment_instructions])
        parts.append('\n'.join(lines))
    return '\n\n'.join(parts)


def build_collection_account_email(document, *, resend=False):
    """Subject + rendered bodies for the client email. No side effects."""
    extension = document.collection_account
    total = format_cop_email(document.total)
    item = document.items.first()

    markdown_sections = [
        (
            f'Te compartimos la cuenta de cobro {document.public_number} por '
            f'{extension.billing_concept or document.title}.'
        ),
    ]
    if item and item.period_start and item.period_end:
        period = f'{item.period_start:%d/%m/%Y} a {item.period_end:%d/%m/%Y}'
        markdown_sections.append(f'Período facturado: **{period}**.')
    if extension.vat_rate is not None or document.tax_total:
        rate_label = f' ({extension.vat_rate.normalize():f} %)' if extension.vat_rate is not None else ''
        markdown_sections.append(f'Valor antes de IVA: **${format_cop_email(document.total - document.tax_total)} COP**.')
        markdown_sections.append(f'IVA{rate_label}: **${format_cop_email(document.tax_total)} COP**.')
    markdown_sections.append(f'Valor a pagar: **${total} COP**.')
    if document.due_date:
        # Its own line. Sharing the amount's line buried the one date the
        # client has to act on, and the house weekday format reads faster
        # than 19/08/2026 for a deadline.
        markdown_sections.append(
            'Fecha límite de pago: '
            f'**{format_bogota_date(document.due_date)}**.'
        )
    payment_methods = _payment_methods_section(document)
    if payment_methods:
        markdown_sections.append(payment_methods)
    markdown_sections.append(
        'Adjuntamos el PDF con el detalle completo. Cualquier duda, '
        'responde este correo y con gusto te ayudamos.'
    )

    # An empty conversion would silently drop a section, so each one falls
    # back to its plain text — same guard as the composed-email pipeline.
    text_sections = [_plain(section) for section in markdown_sections]
    html_sections = [
        {'html': html} if (html := markdown_to_email_html(section)) else plain
        for section, plain in zip(markdown_sections, text_sections)
    ]

    subject = f'Cuenta de cobro {document.public_number} — ProjectApp'
    greeting = (
        f'Hola {extension.customer_contact_name or extension.customer_name}'
    )
    attachment_name = f'{document.public_number}.pdf'
    context = {
        'subject': subject,
        'greeting': greeting,
        'footer': '',
        'attachment_names': [attachment_name],
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
        'attachment_name': attachment_name,
    }


def send_collection_account_email(
    document, *, hosting=None, resend=False, retry_of=None,
):
    """Build + send the client email with the PDF attached. True on success."""
    extension = document.collection_account
    recipient = extension.customer_email
    if not recipient:
        logger.warning(
            'Collection account %s has no customer email; not sent.',
            document.pk,
        )
        return False

    email_parts = build_collection_account_email(document, resend=resend)
    subject = email_parts['subject']
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co')
    hosting_id = hosting.pk if hosting else document.hosting_record_id
    metadata = {
        'document_id': document.pk,
        'public_number': document.public_number,
        'hosting_id': hosting_id,
        'income_record_id': document.income_record_id,
        'resend': resend,
    }
    targets = [
        ('collection_account', document.pk, document.public_number or ''),
        ('hosting', hosting_id, ''),
        ('income', document.income_record_id, ''),
    ]
    # The one accounting notice addressed to the client rather than to the
    # team. `client_user` is nullable, so a cuenta de cobro for someone with
    # no platform account files as "al cliente" with nobody attached — it did
    # go to a client address, we just cannot name whose profile.
    client = getattr(document.client_user, 'profile', None)

    try:
        # Issued accounts attach the immutable bytes archived at issuance.
        # Legacy rows without a snapshot keep the transitional read fallback.
        pdf_bytes = stored_collection_account_pdf(document)
        email = EmailMultiAlternatives(
            subject=subject,
            body=email_parts['text_body'],
            from_email=from_email,
            to=[recipient],
        )
        email.attach_alternative(email_parts['html_body'], 'text/html')
        email.attach(
            email_parts['attachment_name'], pdf_bytes, 'application/pdf',
        )
        EmailDeliveryGateway.send(
            email,
            template_key=TEMPLATE_KEY,
            attachment_sources=[{
                'document_id': document.pk,
                'business_kind': 'collection_account',
                'business_kind_label': 'Cuenta de cobro',
            }],
        )
    except Exception as exc:
        logger.warning(
            'Failed to send collection account %s to %s: %s',
            document.pk, recipient, exc,
        )
        email_log_service.record_send(
            template_key=TEMPLATE_KEY,
            recipients=[recipient],
            subject=subject,
            status=EmailLog.Status.FAILED,
            error_message=str(exc),
            metadata=metadata,
            targets=targets,
            html_body=email_parts['html_body'],
            text_body=email_parts['text_body'],
            retry_of=retry_of,
            client=client,
            audience=EmailLog.Audience.CLIENT,
        )
        return False

    email_log_service.record_send(
        template_key=TEMPLATE_KEY,
        recipients=[recipient],
        subject=subject,
        status=EmailLog.Status.SENT,
        metadata=metadata,
        targets=targets,
        html_body=email_parts['html_body'],
        text_body=email_parts['text_body'],
        retry_of=retry_of,
        client=client,
        audience=EmailLog.Audience.CLIENT,
    )
    logger.info(
        'Sent collection account %s to %s', document.public_number, recipient,
    )
    return True
