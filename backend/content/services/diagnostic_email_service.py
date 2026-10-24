"""Email service for the WebAppDiagnostic feature.

Sends two emails:
- ``diagnostic_initial_sent`` — initial scope/severity/categories doc (no pricing).
- ``diagnostic_final_sent`` — full package with pricing + sizing annex.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.template.loader import render_to_string

from accounts.services.proposal_client_service import build_client_display_name
from content.models import EmailLog, WebAppDiagnostic
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.services.proposal_email_service import (
    ProposalEmailService,
    _is_unsendable_client_email,
)

logger = logging.getLogger(__name__)


class DiagnosticEmailService:

    TEMPLATE_INITIAL = 'diagnostic_initial_sent'
    TEMPLATE_FINAL = 'diagnostic_final_sent'
    TEMPLATE_CUSTOM = 'diagnostic_custom_email'
    TEMPLATE_DOCUMENTS = 'diagnostic_documents_sent'

    @classmethod
    def _send(cls, diagnostic: WebAppDiagnostic, template_key: str,
              subject: str) -> bool:
        recipient = (diagnostic.client.user.email or '').strip()
        if _is_unsendable_client_email(recipient):
            logger.warning(
                'Cannot send %s: no usable client email for diagnostic %s',
                template_key, diagnostic.uuid,
            )
            return False

        from content.services.proposal_email_service import _build_design_context

        context = {
            'client_name': build_client_display_name(diagnostic.client),
            'diagnostic_url': diagnostic.public_url,
            'title': diagnostic.title,
            'investment_amount': diagnostic.investment_amount,
            'currency': diagnostic.currency,
            'duration_label': diagnostic.duration_label,
        }
        # Diagnostics no tienen Proposal asociada — usa firmante por defecto.
        context.update(_build_design_context())
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co')

        # Bound before the try: the failure path logs from the except, and a
        # render error must not turn into a NameError there.
        html_body = text_body = ''
        try:
            html_body = render_to_string(f'emails/{template_key}.html', context)
            text_body = render_to_string(f'emails/{template_key}.txt', context)
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[recipient],
            )
            email.attach_alternative(html_body, 'text/html')
            EmailDeliveryGateway.send(email, template_key=template_key)
            ProposalEmailService._log_email(
                template_key, recipient, subject=subject, status='sent',
                metadata={'diagnostic_uuid': str(diagnostic.uuid)},
                client=diagnostic.client_id,
                html_body=html_body, text_body=text_body,
            )
            logger.info('Sent %s to %s for diagnostic %s',
                        template_key, recipient, diagnostic.uuid)
            return True
        except Exception as exc:
            ProposalEmailService._log_email(
                template_key, recipient, subject=subject, status='failed',
                error_message=str(exc)[:1000],
                metadata={'diagnostic_uuid': str(diagnostic.uuid)},
                client=diagnostic.client_id,
                html_body=html_body, text_body=text_body,
            )
            logger.exception('Failed sending %s for diagnostic %s',
                             template_key, diagnostic.uuid)
            return False

    @classmethod
    def send_initial_to_client(cls, diagnostic: WebAppDiagnostic) -> bool:
        name = build_client_display_name(diagnostic.client)
        subject = f'📋 {name}, propuesta de diagnóstico técnico — Project App'
        return cls._send(diagnostic, cls.TEMPLATE_INITIAL, subject)

    @classmethod
    def send_final_to_client(cls, diagnostic: WebAppDiagnostic) -> bool:
        name = build_client_display_name(diagnostic.client)
        subject = f'📊 {name}, tu diagnóstico está listo — Project App'
        return cls._send(diagnostic, cls.TEMPLATE_FINAL, subject)

    # ── Custom composer (branded-style email) ────────────────────────

    @classmethod
    def get_defaults(cls, diagnostic: WebAppDiagnostic) -> dict:
        """Return suggested field values for the admin email composer."""
        name = build_client_display_name(diagnostic.client)
        return {
            'recipient_email': (diagnostic.client.user.email or '').strip(),
            'subject': f'{name}, seguimiento de tu diagnóstico — Project App',
            'greeting': f'Hola {name}',
            'sections': [''],
            'footer': 'Quedamos atentos a tus comentarios.',
        }

    @classmethod
    def send_custom_email(
        cls,
        diagnostic: WebAppDiagnostic,
        recipient_emails=None,
        subject: str = '',
        greeting: str = '',
        sections: list = (),
        footer: str = '',
        text_formats=None,
        attachments: list | None = None,
        cc_emails=None,
        recipient_email=None,
    ) -> bool:
        """Send a composer-driven follow-up email for a diagnostic.

        Reuses the shared branded-email template and records the send in
        ``EmailLog`` with ``metadata.diagnostic_uuid`` (no ``proposal`` FK).
        """
        from content.services.email_markdown import normalize_sections
        from content.services.email_recipient_service import recipient_log_contexts

        if recipient_emails is None:
            recipient_emails = recipient_email
        if isinstance(recipient_emails, str):
            recipient_emails = [recipient_emails]
        if isinstance(cc_emails, str):
            cc_emails = [cc_emails]
        to_recipients = [
            value.strip().lower() for value in (recipient_emails or ()) if value
        ]
        cc_recipients = [
            value.strip().lower() for value in (cc_emails or ()) if value
        ]
        all_recipients = to_recipients + cc_recipients

        attachment_names = [a[0] for a in attachments] if attachments else []
        normalized_sections = normalize_sections(sections)
        log_metadata = {
            'diagnostic_uuid': str(diagnostic.uuid),
            'greeting': greeting,
            'sections': normalized_sections,
            'footer': footer,
            **({'text_formats': text_formats} if text_formats else {}),
            'attachment_names': attachment_names,
            'to_recipients': to_recipients,
            'cc_recipients': cc_recipients,
        }
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL',
                             'team@projectapp.co')
        # A composed email goes wherever the panel addressed it, so the
        # audience is a fact of this send and not of its template: it counts
        # as contact only when it actually reached the client's own address.
        recipient_contexts = recipient_log_contexts(
            to_recipients,
            cc_recipients,
            contextual_client=diagnostic.client,
        )

        html_body = text_body = ''
        try:
            html_body, text_body = ProposalEmailService.render_composed_email(
                'branded_email', None, subject, greeting,
                normalized_sections, footer, attachment_names, text_formats=text_formats,
            )
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=to_recipients,
                cc=cc_recipients,
            )
            email.attach_alternative(html_body, 'text/html')
            for filename, data, mime_type in (attachments or []):
                email.attach(filename, data, mime_type)
            classification = (
                DeliveryClassification.CLIENT
                if any(
                    item['audience'] == EmailLog.Audience.CLIENT
                    for item in recipient_contexts
                )
                else DeliveryClassification.INTERNAL
            )
            EmailDeliveryGateway.send(
                email,
                template_key=cls.TEMPLATE_CUSTOM,
                classification=classification,
            )

            ProposalEmailService._log_email(
                cls.TEMPLATE_CUSTOM,
                recipients=all_recipients,
                recipient_contexts=recipient_contexts,
                subject=subject, status='sent',
                metadata=log_metadata,
                client=None, audience=EmailLog.Audience.INTERNAL,
                html_body=html_body, text_body=text_body,
            )
            logger.info(
                'Sent %s to %s for diagnostic %s',
                cls.TEMPLATE_CUSTOM, all_recipients, diagnostic.uuid,
            )
            return True
        except Exception as exc:
            ProposalEmailService._log_email(
                cls.TEMPLATE_CUSTOM,
                recipients=all_recipients,
                recipient_contexts=recipient_contexts,
                subject=subject, status='failed',
                error_message=str(exc)[:1000],
                metadata=log_metadata,
                client=None, audience=EmailLog.Audience.INTERNAL,
                html_body=html_body, text_body=text_body,
            )
            logger.exception(
                'Failed sending %s for diagnostic %s',
                cls.TEMPLATE_CUSTOM, diagnostic.uuid,
            )
            return False

    @classmethod
    def list_emails(cls, diagnostic: WebAppDiagnostic, page: int = 1,
                    page_size: int = 20) -> dict:
        """Return paginated email history filtered by diagnostic uuid."""
        from content.models import EmailLog

        logs = EmailLog.objects.filter(
            proposal__isnull=True,
            metadata__diagnostic_uuid=str(diagnostic.uuid),
            delivery_role=EmailLog.DeliveryRole.PRIMARY,
        ).order_by('-sent_at')

        page = max(1, int(page or 1))
        from content.services.email_log_service import (
            attach_delivery_copies,
            attach_delivery_recipients,
            delivery_copy_payloads,
            delivery_recipient_payloads,
            representative_delivery_queryset,
        )

        logs = representative_delivery_queryset(logs)
        total = logs.count()
        offset = (page - 1) * page_size
        page_logs = attach_delivery_recipients(
            attach_delivery_copies(logs[offset:offset + page_size]),
        )
        results = [
            {
                'id': log.pk,
                'delivery_id': str(log.delivery_id) if log.delivery_id else None,
                'recipient': log.recipient,
                'subject': log.subject,
                'status': log.status,
                'template_key': log.template_key,
                'sent_at': log.sent_at.isoformat(),
                'metadata': log.metadata,
                'copies': delivery_copy_payloads(log),
                **delivery_recipient_payloads(log),
            }
            for log in page_logs
        ]
        return {
            'results': results,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_next': offset + page_size < total,
        }
