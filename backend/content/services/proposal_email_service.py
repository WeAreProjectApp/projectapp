import logging
import uuid

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import UserProfile
from content.services.client_email_inventory import CLIENT_EMAIL_CHANNELS
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.utils import format_bogota_date, format_cop_email, safe_slug

logger = logging.getLogger(__name__)


# Flows whose recipient is, by construction, the client's own address — the
# default `audience` for their log rows. The composed ones (branded_email,
# proposal_email, diagnostic_custom_email) are deliberately absent: they go
# to whatever address the panel typed, so they state their audience at the
# call site. `team_copy` is absent for the opposite reason: it never does.
CLIENT_FACING_TEMPLATE_KEYS = frozenset(CLIENT_EMAIL_CHANNELS)


# Fallback de marca cuando una propuesta no tiene email_method_phases diligenciado.
# Renderiza el card oscuro "Método en 3 fases" del diseño nuevo.
DEFAULT_METHOD_PHASES = [
    {'number': '01', 'title': 'Diagnóstico', 'duration': '',
     'description': 'Mapeo de procesos y alcance final.'},
    {'number': '02', 'title': 'Construcción', 'duration': '',
     'description': 'Sprints con demo cada viernes.'},
    {'number': '03', 'title': 'Lanzamiento', 'duration': '',
     'description': 'Deploy, capacitación y soporte.'},
]


def _resolve_signature(signer_key):
    """Return ``{'name', 'role'}`` for ``signer_key`` (falls back to default)."""
    signatures = getattr(settings, 'EMAIL_SIGNATURES', {}) or {}
    default_key = getattr(settings, 'EMAIL_DEFAULT_SIGNER', 'gustavo')
    return signatures.get(signer_key) or signatures.get(default_key) or {
        'name': 'Equipo ProjectApp', 'role': 'ProjectApp.',
    }


def _configured_standalone_signer():
    """Signer key for standalone branded emails.

    Reads the ``signer`` override stored by the panel defaults form on the
    ``branded_email`` template config, falling back to
    ``settings.EMAIL_DEFAULT_SIGNER``.
    """
    from content.models import EmailTemplateConfig

    config = EmailTemplateConfig.objects.filter(template_key='branded_email').first()
    overrides = (config.content_overrides if config else {}) or {}
    return overrides.get('signer') or getattr(settings, 'EMAIL_DEFAULT_SIGNER', 'gustavo')


def _build_design_context(proposal=None):
    """Common context keys for the redesigned client-facing emails.

    Provides:
    - ``signature_name`` / ``signature_role`` — resolved from settings (always)
    - ``email_features`` — bullets for "Qué incluye" (empty if proposal=None)
    - ``email_method_phases`` — 3-phase card; falls back to brand default
    - ``proposal_reference`` — display id like "PA-2026-0042" (if proposal)
    """
    if proposal is None:
        sig = _resolve_signature(getattr(settings, 'EMAIL_DEFAULT_SIGNER', 'gustavo'))
        return {
            'signature_name': sig['name'],
            'signature_role': sig['role'],
            'email_features': [],
            'email_method_phases': DEFAULT_METHOD_PHASES,
            'proposal_reference': '',
        }

    sig = _resolve_signature(getattr(proposal, 'email_signed_by', None))
    method_phases = list(getattr(proposal, 'email_method_phases', []) or [])
    if not method_phases:
        method_phases = DEFAULT_METHOD_PHASES

    year = proposal.created_at.year if getattr(proposal, 'created_at', None) else timezone.now().year
    reference = f'PA-{year}-{proposal.pk:04d}' if proposal.pk else ''

    return {
        'signature_name': sig['name'],
        'signature_role': sig['role'],
        'email_features': list(getattr(proposal, 'email_features', []) or []),
        'email_method_phases': method_phases,
        'proposal_reference': reference,
    }


def _is_unsendable_client_email(email):
    """Return True when ``email`` is empty or a generated placeholder."""
    if not email:
        return True
    return email.endswith(UserProfile.PLACEHOLDER_EMAIL_DOMAIN)


def _delivery(ok, reason, detail=''):
    return {'ok': ok, 'reason': reason, 'detail': detail}


# User-facing detail for unexpected send failures. The raw exception text is
# kept in the logs / EmailLog, never surfaced to the panel user.
GENERIC_SEND_FAILURE_DETAIL = (
    'No se pudo enviar el correo al cliente. Verifica el correo del cliente o '
    'la configuración de envío e inténtalo de nuevo.'
)


class ProposalEmailService:
    """
    Service for sending proposal-related emails to clients.
    Uses Django's EmailMultiAlternatives for HTML + text fallback.
    """

    FROM_EMAIL = None  # Resolved at runtime from settings

    @classmethod
    def _get_from_email(cls):
        """Return the configured sender email address."""
        return cls.FROM_EMAIL or getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co'
        )

    @classmethod
    def _get_notification_recipients(cls):
        """
        Return internal notification recipients.

        Supports:
        - NOTIFICATION_EMAIL (single email or comma-separated emails)
        - NOTIFICATION_EMAILS (list/tuple/set or comma-separated string)
        """
        recipients = []

        def _append(value):
            if not value:
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    _append(item)
                return
            for part in str(value).split(','):
                email = part.strip()
                if email and email not in recipients:
                    recipients.append(email)

        _append(getattr(settings, 'NOTIFICATION_EMAILS', None))
        _append(getattr(settings, 'NOTIFICATION_EMAIL', None))

        if not recipients:
            recipients.append('team@projectapp.co')

        return recipients

    @classmethod
    def _log_email(cls, template_key, recipient=None, subject='', proposal=None,
                   status='sent', error_message='', metadata=None,
                   client=None, audience=None, html_body='', text_body='',
                   targets=(), recipients=None, recipient_contexts=None):
        """Log an email send attempt, through the single writer.

        Delegates to ``email_log_service.record_send`` so proposal traffic
        lands in the same shape as the accounting notices: a stored body the
        panel can show back, and a client the clients list can count. The
        signature only grew keyword arguments, so the call sites that want
        none of it stay as they were.
        """
        try:
            from content.models import EmailLog
            from content.services import email_log_service

            if client is None and proposal is not None and not recipient_contexts:
                # No extra query: the FK id is already on the instance.
                client = proposal.client_id
            return email_log_service.record_send(
                template_key=template_key,
                recipients=list(recipients or [recipient]),
                recipient_contexts=recipient_contexts,
                subject=subject[:500] if subject else '',
                status=status,
                error_message=error_message,
                metadata=metadata,
                proposal=proposal,
                client=client,
                audience=audience or (
                    EmailLog.Audience.CLIENT
                    if template_key in CLIENT_FACING_TEMPLATE_KEYS
                    else EmailLog.Audience.INTERNAL
                ),
                html_body=html_body,
                text_body=text_body,
                targets=targets,
            )
        except Exception:
            logger.exception('Failed to create EmailLog entry')
            return []

    @classmethod
    def _is_template_active(cls, template_key):
        """Check if a template is active (not disabled by admin)."""
        from content.models import EmailTemplateConfig
        config = EmailTemplateConfig.objects.filter(
            template_key=template_key,
        ).first()
        if config is None:
            return True
        return config.is_active

    @classmethod
    def _check_cooldown(cls, proposal, cooldown_hours=24):
        """
        Check if enough time has passed since the last automated email.
        If cooldown has passed, update last_automated_email_at and return True.
        Otherwise return False (email should be skipped).
        """
        from datetime import timedelta
        now = timezone.now()
        if (
            proposal.last_automated_email_at
            and (now - proposal.last_automated_email_at) < timedelta(hours=cooldown_hours)
        ):
            logger.info(
                'Skipping automated email for %s: cooldown active (last sent %s)',
                proposal.uuid, proposal.last_automated_email_at,
            )
            return False
        proposal.last_automated_email_at = now
        proposal.save(update_fields=['last_automated_email_at'])
        return True

    @classmethod
    def _resolve_content(cls, template_key, context):
        """
        Resolve editable field values for a template, merging DB overrides
        with registry defaults, then substituting {variable} placeholders
        with actual context values.

        Returns a dict of {field_key: resolved_value}.
        """
        from content.models import EmailTemplateConfig
        from content.services.email_template_registry import (
            resolve_field_values,
            substitute_variables,
        )

        config = EmailTemplateConfig.objects.filter(
            template_key=template_key,
        ).first()
        overrides = config.content_overrides if config else {}
        field_values = resolve_field_values(template_key, overrides)

        resolved = {}
        for key, value in field_values.items():
            resolved[key] = substitute_variables(value, context)
        return resolved

    @classmethod
    def _build_platform_context(cls, proposal):
        """
        Build the shared platform-related context (login URL + linked
        deliverable identifiers) used by client-facing emails that point
        to the platform workspace.
        """
        base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:3000').rstrip('/')
        dlv = getattr(proposal, 'deliverable', None)
        project_name = ''
        deliverable_title = ''
        if dlv is not None:
            project_name = dlv.project.name if dlv.project_id else ''
            deliverable_title = dlv.title or ''
        return {
            'platform_login_url': f'{base}/platform/login',
            'project_name': project_name,
            'deliverable_title': deliverable_title,
        }

    @classmethod
    def _build_initial_email_context(cls, proposal):
        """Read payment_options + total_duration from existing sections.

        These are already populated when the proposal is created (see
        ``proposal_service.py``) and are the same values rendered on the
        public web view, so the email always matches the proposal.
        """
        from content.models.proposal_section import ProposalSection

        sections = list(proposal.sections.all())
        investment_section = next(
            (s for s in sections if s.section_type == ProposalSection.SectionType.INVESTMENT),
            None,
        )
        timeline_section = next(
            (s for s in sections if s.section_type == ProposalSection.SectionType.TIMELINE),
            None,
        )

        payment_options = []
        if investment_section:
            raw = investment_section.content_json.get('paymentOptions') or []
            payment_options = [
                {
                    'label': item.get('label', ''),
                    'description': item.get('description', ''),
                }
                for item in raw
                if isinstance(item, dict)
            ]

        total_duration = ''
        if timeline_section:
            total_duration = timeline_section.content_json.get('totalDuration', '') or ''

        payment_summary = '/'.join(
            opt['label'].split('%', 1)[0].strip()
            for opt in payment_options
            if '%' in opt.get('label', '')
        )

        return {
            'email_intro': (proposal.email_intro or '').strip(),
            'payment_options': payment_options,
            'total_duration': total_duration,
            'payment_summary': payment_summary,
        }

    @classmethod
    def _attach_commercial_pdf(cls, email, proposal, snapshot=None):
        """Attach the commercial proposal PDF to ``email``.

        Send flows pass a persisted snapshot so the bytes attached to the
        email are exactly the bytes retained by the document manager.  The
        generation fallback remains for non-send callers during rollout.
        """
        if snapshot is not None:
            email.attach(
                snapshot.attachment_name,
                snapshot.pdf_bytes,
                'application/pdf',
            )
            logger.info(
                'Attached stored commercial PDF version %s for proposal %s',
                snapshot.document.source_version,
                proposal.uuid,
            )
            return True

        from content.services.proposal_pdf_service import ProposalPdfService

        try:
            pdf_bytes = ProposalPdfService.generate(proposal)
        except Exception:
            logger.warning(
                'Commercial PDF generation failed for proposal %s; sending email without it',
                proposal.uuid,
                exc_info=True,
            )
            return False

        if not pdf_bytes:
            return False

        safe_client = safe_slug(proposal.client_name, 'Cliente')
        email.attach(
            f'Propuesta_Comercial_{safe_client}.pdf',
            pdf_bytes,
            'application/pdf',
        )
        logger.info(
            'Attached commercial PDF (%d bytes) for proposal %s',
            len(pdf_bytes), proposal.uuid,
        )
        return True

    @classmethod
    def send_proposal_to_client(cls, proposal, snapshot=None):
        """
        Send the initial proposal email to the client with a link to view it.

        Normal send flows provide a persisted ``snapshot`` and attach those
        exact bytes. The compatibility fallback generates the PDF here and is
        best-effort for callers that do not yet provide a snapshot.

        Args:
            proposal: BusinessProposal instance with client_email set.
            snapshot: Prepared immutable PDF version, when the caller archives
                generated documents.

        Returns:
            dict: {'ok': bool, 'reason': str, 'detail': str}
                  reason is one of: 'sent', 'placeholder_email',
                  'template_disabled', 'send_failed'.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.warning(
                'Cannot send proposal email for %s: missing or placeholder client_email',
                proposal.uuid,
            )
            return _delivery(
                False, 'placeholder_email',
                'El correo del cliente está vacío o es un placeholder.',
            )

        if not cls._is_template_active('proposal_sent_client'):
            logger.info('Skipping proposal_sent_client: template disabled')
            return _delivery(
                False, 'template_disabled',
                'La plantilla proposal_sent_client está desactivada.',
            )

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'days_remaining': proposal.days_remaining,
            'expires_at': proposal.expires_at,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'title': proposal.title,
        }
        context.update(cls._build_initial_email_context(proposal))

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_sent_client', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_sent_client.html', context
            )
            text_content = render_to_string(
                'emails/proposal_sent_client.txt', context
            )

            subject = resolved.get('subject', (
                f'📋 {proposal.client_name}, tu propuesta está lista — '
                f'Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')

            pdf_attached = cls._attach_commercial_pdf(email, proposal, snapshot)

            EmailDeliveryGateway.send(
                email, template_key='proposal_sent_client',
            )

            cls._log_email(
                'proposal_sent_client', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                metadata={'pdf_attached': pdf_attached},
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent proposal email for %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return _delivery(True, 'sent')

        except Exception as exc:
            cls._log_email(
                'proposal_sent_client', proposal.client_email,
                subject='', proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send proposal email for %s',
                proposal.uuid,
            )
            return _delivery(False, 'send_failed', GENERIC_SEND_FAILURE_DETAIL)

    @classmethod
    def send_multi_proposal_to_client(cls, proposals, snapshots=None):
        """Send a single email referencing multiple proposals from the same
        client. One PDF attachment per proposal, one EmailLog per proposal
        (linked by ``group_uuid`` in metadata).

        ``proposals`` must all share the same ``client_email``; the caller is
        responsible for that validation. Returns the same delivery dict shape
        as ``send_proposal_to_client``.
        """
        if not proposals:
            return _delivery(False, 'no_proposals', 'No se proporcionaron propuestas.')

        primary = proposals[0]
        if _is_unsendable_client_email(primary.client_email):
            return _delivery(
                False, 'placeholder_email',
                'El correo del cliente está vacío o es un placeholder.',
            )

        if not cls._is_template_active('proposal_multi_sent_client'):
            logger.info('Skipping proposal_multi_sent_client: template disabled')
            return _delivery(
                False, 'template_disabled',
                'La plantilla proposal_multi_sent_client está desactivada.',
            )

        phases = []
        for proposal in proposals:
            phase_ctx = cls._build_initial_email_context(proposal)
            phases.append({
                'title': proposal.title,
                'proposal_url': proposal.public_url,
                'total_investment': format_cop_email(proposal.total_investment),
                'currency': proposal.currency,
                **phase_ctx,
            })

        context = {
            'client_name': primary.client_name,
            'phases': phases,
            'phases_count': len(phases),
        }

        context.update(_build_design_context(primary))
        resolved = cls._resolve_content('proposal_multi_sent_client', context)
        context.update(resolved)

        group_uuid = str(uuid.uuid4())

        # Bound before the try: the failure path logs from the except, and a
        # render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_multi_sent_client.html', context,
            )
            text_content = render_to_string(
                'emails/proposal_multi_sent_client.txt', context,
            )

            subject = resolved.get('subject', (
                f'📋 {primary.client_name}, tus propuestas comerciales — Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[primary.client_email],
            )
            email.attach_alternative(html_content, 'text/html')

            snapshots_by_proposal = {
                snapshot.proposal_id: snapshot for snapshot in (snapshots or [])
            }
            attached_count = sum(
                1 for proposal in proposals
                if cls._attach_commercial_pdf(
                    email,
                    proposal,
                    snapshots_by_proposal.get(proposal.pk),
                )
            )

            EmailDeliveryGateway.send(
                email,
                template_key='proposal_multi_sent_client',
                primary_log_writes=len(proposals),
            )

            # One email, one stored body: the rows share `group_uuid`, so
            # only the first carries it and the others point the reader at
            # the group instead of duplicating the same HTML N times.
            for index, proposal in enumerate(proposals):
                cls._log_email(
                    'proposal_multi_sent_client', proposal.client_email,
                    subject=subject, proposal=proposal, status='sent',
                    metadata={
                        'group_uuid': group_uuid,
                        'group_size': len(proposals),
                        'pdfs_attached': attached_count,
                    },
                    html_body=html_content if index == 0 else '',
                    text_body=text_content if index == 0 else '',
                )
            logger.info(
                'Sent multi-proposal email (%d proposals, %d PDFs) to %s — group %s',
                len(proposals), attached_count, primary.client_email, group_uuid,
            )
            return _delivery(True, 'sent', f'group={group_uuid}')

        except Exception as exc:
            for index, proposal in enumerate(proposals):
                cls._log_email(
                    'proposal_multi_sent_client', proposal.client_email,
                    subject='', proposal=proposal, status='failed',
                    error_message=str(exc)[:1000],
                    metadata={'group_uuid': group_uuid},
                    html_body=html_content if index == 0 else '',
                    text_body=text_content if index == 0 else '',
                )
            logger.exception(
                'Failed to send multi-proposal email — group %s', group_uuid,
            )
            return _delivery(False, 'send_failed', GENERIC_SEND_FAILURE_DETAIL)

    @classmethod
    def send_reminder(cls, proposal):
        """
        Send a reminder email about a pending proposal.

        Renders HTML and plain-text templates with proposal context,
        sends via EmailMultiAlternatives, and records reminder_sent_at.

        Args:
            proposal: BusinessProposal instance with client_email set.

        Returns:
            bool: True if the email was sent successfully.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.warning(
                'Cannot send reminder for proposal %s: missing or placeholder client_email',
                proposal.uuid,
            )
            return False

        if not cls._is_template_active('proposal_reminder'):
            logger.info('Skipping proposal_reminder: template disabled')
            return False

        if not cls._check_cooldown(proposal):
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'days_remaining': proposal.days_remaining,
            'expires_at': proposal.expires_at,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'title': proposal.title,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_reminder', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_reminder.html', context
            )
            text_content = render_to_string(
                'emails/proposal_reminder.txt', context
            )

            subject = resolved.get('subject', (
                f'📋 {proposal.client_name}, tu propuesta te espera — '
                f'Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_reminder',
            )

            proposal.reminder_sent_at = timezone.now()
            proposal.save(update_fields=['reminder_sent_at'])

            cls._log_email(
                'proposal_reminder', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent reminder email for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_reminder', proposal.client_email,
                subject='', proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send reminder email for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_urgency_email(cls, proposal, *, force=False):
        """
        Send an urgency/reminder email at day 15.

        If proposal.discount_percent > 0, sends the discount-focused template.
        Otherwise, sends a simpler reminder without discount info.

        Args:
            proposal: BusinessProposal instance with client_email set.
            force: When True (manual admin send), bypass the 24h cooldown so the
                seller can offer the discount on demand.

        Returns:
            bool: True if the email was sent successfully.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        has_discount = (
            proposal.discount_percent and proposal.discount_percent > 0
        )

        template_key = (
            'proposal_urgency' if has_discount
            else 'proposal_urgency_no_discount'
        )

        if not cls._is_template_active(template_key):
            logger.info('Skipping %s: template disabled', template_key)
            return False

        if not force and not cls._check_cooldown(proposal):
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'days_remaining': proposal.days_remaining,
            'expires_at': proposal.expires_at,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'title': proposal.title,
        }

        if has_discount:
            from content.services.proposal_totals_service import discounted_total_for_proposal, discount_original_for_proposal
            discounted = discounted_total_for_proposal(proposal)
            context.update({
                'total_investment': format_cop_email(discount_original_for_proposal(proposal)),
                'discounted_investment': format_cop_email(discounted),
                'discount_percent': proposal.discount_percent,
            })
            html_template = 'emails/proposal_urgency.html'
            txt_template = 'emails/proposal_urgency.txt'
        else:
            html_template = 'emails/proposal_urgency_no_discount.html'
            txt_template = 'emails/proposal_urgency_no_discount.txt'

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content(template_key, context)
        context.update(resolved)
        subject = resolved.get('subject', f'{proposal.client_name}, tu propuesta expira pronto')

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(html_template, context)
            text_content = render_to_string(txt_template, context)

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(email, template_key=template_key)

            proposal.urgency_email_sent_at = timezone.now()
            proposal.save(update_fields=['urgency_email_sent_at'])

            cls._log_email(
                template_key, proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent urgency email for proposal %s to %s (discount=%s)',
                proposal.uuid, proposal.client_email, has_discount,
            )
            return True

        except Exception as exc:
            cls._log_email(
                template_key, proposal.client_email,
                subject=subject, proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send urgency email for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_response_notification(cls, proposal, action):
        """
        Send notification email to team@projectapp.co when a client
        accepts or rejects a proposal.
        """
        if not cls._is_template_active('proposal_response_notification'):
            logger.info('Skipping proposal_response_notification: template disabled')
            return False

        action_tag = (
            'ACCEPTED' if action == 'accepted'
            else 'NEGOTIATING' if action == 'negotiating'
            else 'REJECTED'
        )
        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'action': action,
            'action_label': (
                'ACEPTADA' if action == 'accepted'
                else 'NEGOCIANDO' if action == 'negotiating'
                else 'RECHAZADA'
            ),
            'action_tag': action_tag,
            'proposal_uuid': str(proposal.uuid),
            'rejection_reason': getattr(proposal, 'rejection_reason', ''),
            'rejection_comment': getattr(proposal, 'rejection_comment', ''),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_response_notification', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_response_notification.html', context
            )
            text_content = render_to_string(
                'emails/proposal_response_notification.txt', context
            )

            subject = resolved.get('subject', (
                f'[{action_tag}] Propuesta: {proposal.title} — '
                f'{proposal.client_name}'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_response_notification',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent %s notification for proposal %s',
                action, proposal.uuid,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send %s notification for proposal %s',
                action, proposal.uuid,
            )
            return False

    @classmethod
    def send_acceptance_confirmation(cls, proposal):
        """
        Send acceptance confirmation email to the client with a link
        to view/download their proposal. Attaches a PDF of the proposal
        when generation succeeds.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_accepted_client'):
            logger.info('Skipping proposal_accepted_client: template disabled')
            return False

        platform_ctx = cls._build_platform_context(proposal)
        platform_login_url = platform_ctx['platform_login_url']
        project_name = platform_ctx['project_name']
        deliverable_title = platform_ctx['deliverable_title']

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            **platform_ctx,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_accepted_client', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_accepted_client.html', context
            )
            text_content = render_to_string(
                'emails/proposal_accepted_client.txt', context
            )

            subject = resolved.get('subject', (
                f'✅ {proposal.client_name}, tu propuesta ha sido aceptada — '
                f'Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')

            cls._attach_commercial_pdf(email, proposal)
            safe_client = safe_slug(proposal.client_name, 'Cliente')

            # Technical document PDF
            try:
                from content.services.technical_document_pdf import (
                    generate_technical_document_pdf,
                )

                tech_pdf = generate_technical_document_pdf(proposal)
                if tech_pdf:
                    email.attach(
                        f'Documento_tecnico_{safe_client}.pdf',
                        tech_pdf,
                        'application/pdf',
                    )
            except Exception:
                logger.warning(
                    'Technical PDF attachment failed for proposal %s',
                    proposal.uuid,
                    exc_info=True,
                )

            # Platform onboarding guide PDF
            try:
                from content.services.platform_onboarding_pdf import (
                    generate_platform_onboarding_pdf,
                )

                guide_pdf = generate_platform_onboarding_pdf(
                    client_name=proposal.client_name or '',
                    client_email=proposal.client_email or '',
                    project_name=project_name,
                    deliverable_title=deliverable_title,
                    platform_login_url=platform_login_url,
                )
                if guide_pdf:
                    email.attach(
                        f'Guia_plataforma_{safe_client}.pdf',
                        guide_pdf,
                        'application/pdf',
                    )
            except Exception:
                logger.warning(
                    'Platform guide PDF failed for proposal %s',
                    proposal.uuid,
                    exc_info=True,
                )

            EmailDeliveryGateway.send(
                email, template_key='proposal_accepted_client',
            )

            cls._log_email(
                'proposal_accepted_client', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent acceptance confirmation for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_accepted_client', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send acceptance confirmation for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_finished_confirmation(cls, proposal):
        """
        Notify the client that their accepted project has been marked as
        finished. No PDF attachments — this is a status closure email.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_finished_client'):
            logger.info('Skipping proposal_finished_client: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'title': proposal.title,
            **cls._build_platform_context(proposal),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_finished_client', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_finished_client.html', context
            )
            text_content = render_to_string(
                'emails/proposal_finished_client.txt', context
            )

            subject = resolved.get('subject', (
                f'🎯 {proposal.client_name}, tu proyecto ha sido finalizado — '
                f'Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_finished_client',
            )

            cls._log_email(
                'proposal_finished_client', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent finished confirmation for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_finished_client', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send finished confirmation for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_rejection_thank_you(cls, proposal):
        """
        Send a thank-you email to the client when they reject a proposal.
        Includes an inspirational message inviting future collaboration.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_rejected_client'):
            logger.info('Skipping proposal_rejected_client: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'title': proposal.title,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_rejected_client', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_rejected_client.html', context
            )
            text_content = render_to_string(
                'emails/proposal_rejected_client.txt', context
            )

            subject = resolved.get('subject', (
                f'Gracias por tu tiempo, {proposal.client_name} — '
                f'Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_rejected_client',
            )

            cls._log_email(
                'proposal_rejected_client', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent rejection thank-you for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_rejected_client', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send rejection thank-you for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_first_view_notification(cls, proposal, *, raise_on_error=False):
        """
        Send notification email to team@projectapp.co when a client
        opens a proposal for the first time. This is the ideal moment
        for the sales team to do follow-up.
        """
        from content.services.proposal_service import ProposalService
        if ProposalService.open_notifications_suppressed(proposal):
            logger.info(
                'Skipping proposal_first_view_notification: proposal %s is %s',
                proposal.uuid, proposal.status,
            )
            return False
        if not cls._is_template_active('proposal_first_view_notification'):
            logger.info('Skipping proposal_first_view_notification: template disabled')
            return False

        recipients = cls._get_notification_recipients()
        subject = ''
        html_content = ''
        text_content = ''
        try:
            # Mirror the effective total used by PDF, admin and client views.
            from decimal import Decimal
            from content.services.proposal_totals_service import (
                effective_total_for_proposal,
            )
            effective_amount = effective_total_for_proposal(proposal)
            base_amount = Decimal(proposal.total_investment or 0).quantize(Decimal('1'))
            has_additional_modules = effective_amount.quantize(Decimal('1')) != base_amount

            context = {
                'client_name': proposal.client_name,
                'proposal_title': proposal.title,
                'title': proposal.title,
                'total_investment': format_cop_email(proposal.total_investment),
                'effective_total_investment': format_cop_email(effective_amount),
                'has_additional_modules': has_additional_modules,
                'currency': proposal.currency,
                'proposal_uuid': str(proposal.uuid),
                'viewed_at': proposal.first_viewed_at or timezone.now(),
                'client_email': proposal.client_email or '',
            }
            context.update(_build_design_context(proposal))
            resolved = cls._resolve_content(
                'proposal_first_view_notification', context,
            )
            context.update(resolved)

            html_content = render_to_string(
                'emails/proposal_first_view_notification.html', context
            )
            text_content = render_to_string(
                'emails/proposal_first_view_notification.txt', context
            )

            subject = resolved.get('subject', (
                f'\U0001f441 [OPENED] Propuesta: {proposal.title} — '
                f'{proposal.client_name}'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=recipients,
            )
            email.attach_alternative(html_content, 'text/html')
            sent_count = EmailDeliveryGateway.send(
                email,
                template_key='proposal_first_view_notification',
                classification=DeliveryClassification.INTERNAL,
            )
            if not sent_count:
                raise RuntimeError('Email backend did not accept the delivery.')

            from content.models import EmailLog
            from content.services import email_log_service

            try:
                email_log_service.record_send(
                    template_key='proposal_first_view_notification',
                    recipients=recipients,
                    subject=subject,
                    status=EmailLog.Status.SENT,
                    proposal=proposal,
                    client=proposal.client_id,
                    audience=EmailLog.Audience.INTERNAL,
                    html_body=html_content,
                    text_body=text_content,
                )
            except Exception:
                # SMTP has already accepted the message. Enrichment is useful
                # for the panel, but it must never turn a successful delivery
                # into a retry that sends the same alert twice.
                logger.exception(
                    'Sent first-view notification for proposal %s but could '
                    'not enrich its EmailLog entry',
                    proposal.uuid,
                )

            logger.info(
                'Sent first-view notification for proposal %s',
                proposal.uuid,
            )
            return True

        except Exception as exc:
            from content.models import EmailLog
            from content.services import email_log_service

            try:
                email_log_service.record_send(
                    template_key='proposal_first_view_notification',
                    recipients=recipients,
                    subject=subject,
                    status=EmailLog.Status.FAILED,
                    proposal=proposal,
                    client=proposal.client_id,
                    audience=EmailLog.Audience.INTERNAL,
                    error_message=str(exc)[:1000],
                    html_body=html_content,
                    text_body=text_content,
                )
            except Exception:
                logger.exception(
                    'Could not record failed first-view notification for '
                    'proposal %s',
                    proposal.uuid,
                )
            logger.exception(
                'Failed to send first-view notification for proposal %s',
                proposal.uuid,
            )
            if raise_on_error:
                raise
            return False

    @classmethod
    def send_comment_notification(cls, proposal, comment):
        """
        Send notification email to team@projectapp.co when a client
        submits a negotiation comment ("Tengo comentarios antes de decidir").
        This is a high-intent signal — client is not rejecting, just negotiating.
        """
        if not cls._is_template_active('proposal_comment_notification'):
            logger.info('Skipping proposal_comment_notification: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'comment': comment,
            'proposal_uuid': str(proposal.uuid),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_comment_notification', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_comment_notification.html', context
            )
            text_content = render_to_string(
                'emails/proposal_comment_notification.txt', context
            )

            subject = resolved.get('subject', (
                f'[COMENTARIO] Propuesta: {proposal.title} — '
                f'{proposal.client_name}'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_comment_notification',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent comment notification for proposal %s',
                proposal.uuid,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send comment notification for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_rejection_reengagement(cls, proposal):
        """
        Send a personalized re-engagement email to the client 48h after
        rejecting due to budget concerns. Invites them to explore a
        reduced scope or payment flexibility.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_reengagement'):
            logger.info('Skipping proposal_reengagement: template disabled')
            return False

        has_discount = bool(proposal.discount_percent and proposal.discount_percent > 0)
        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
        }
        if has_discount:
            from content.services.proposal_totals_service import discounted_total_for_proposal, discount_original_for_proposal
            context['total_investment'] = format_cop_email(discount_original_for_proposal(proposal))
            context['discounted_investment'] = format_cop_email(discounted_total_for_proposal(proposal))
            context['discount_percent'] = proposal.discount_percent

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_reengagement', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except, and a
        # render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_reengagement.html', context
            )
            text_content = render_to_string(
                'emails/proposal_reengagement.txt', context
            )

            subject = resolved.get('subject', (
                f'{proposal.client_name}, ¿podemos encontrar una solución '
                f'que se ajuste a tu presupuesto?'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_reengagement',
            )

            cls._log_email(
                'proposal_reengagement', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent rejection re-engagement email for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_reengagement', proposal.client_email,
                subject='', proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send re-engagement email for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_revisit_alert(cls, proposal, visit_count, top_section='', top_section_time=0):
        """
        Send a smart follow-up alert to team@projectapp.co when a client
        shows strong engagement signals (multiple revisits or high time on
        key sections like Investment).
        """
        if not cls._is_template_active('proposal_revisit_alert'):
            logger.info('Skipping proposal_revisit_alert: template disabled')
            return False

        top_section_display = top_section or 'N/A'
        top_time_display = f'{int(top_section_time // 60)}m {int(top_section_time % 60)}s'

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'visit_count': visit_count,
            'top_section': top_section_display,
            'top_section_time': top_time_display,
            'proposal_uuid': str(proposal.uuid),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_revisit_alert', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_revisit_alert.html', context
            )
            text_content = render_to_string(
                'emails/proposal_revisit_alert.txt', context
            )

            subject = resolved.get('subject', (
                f'\U0001f525 [HOT LEAD] {proposal.client_name} revisó la propuesta '
                f'{visit_count} veces'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_revisit_alert',
                classification=DeliveryClassification.INTERNAL,
            )

            proposal.revisit_alert_sent_at = timezone.now()
            proposal.save(update_fields=['revisit_alert_sent_at'])

            logger.info(
                'Sent revisit alert for proposal %s (visits=%d)',
                proposal.uuid, visit_count,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send revisit alert for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_abandonment_followup(cls, proposal):
        """
        Send a follow-up email when the client viewed the proposal but
        never reached the investment section, suggesting a call to discuss.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_abandonment_followup'):
            logger.info('Skipping proposal_abandonment_followup: template disabled')
            return False

        if not cls._check_cooldown(proposal):
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'title': proposal.title,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_abandonment_followup', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_abandonment_followup.html', context
            )
            text_content = render_to_string(
                'emails/proposal_abandonment_followup.txt', context
            )

            subject = resolved.get('subject', (
                f'📋 {proposal.client_name}, ¿te quedaron dudas sobre '
                f'la propuesta? — Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_abandonment_followup',
            )

            proposal.abandonment_email_sent_at = timezone.now()
            proposal.save(update_fields=['abandonment_email_sent_at'])

            cls._log_email(
                'proposal_abandonment_followup', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent abandonment followup for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_abandonment_followup', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send abandonment followup for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_investment_interest_followup(cls, proposal, time_on_investment=0):
        """
        Send a follow-up email when the client spent significant time
        on the investment section, offering to discuss payment options.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_investment_interest_followup'):
            logger.info('Skipping proposal_investment_interest_followup: template disabled')
            return False

        if not cls._check_cooldown(proposal):
            return False

        time_display = f'{int(time_on_investment // 60)}m {int(time_on_investment % 60)}s'

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'time_on_investment': time_display,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_investment_interest_followup', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_investment_interest_followup.html', context
            )
            text_content = render_to_string(
                'emails/proposal_investment_interest_followup.txt', context
            )

            subject = resolved.get('subject', (
                f'💰 {proposal.client_name}, hablemos sobre opciones '
                f'de inversión — Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_investment_interest_followup',
            )

            proposal.investment_interest_email_sent_at = timezone.now()
            proposal.save(update_fields=['investment_interest_email_sent_at'])

            cls._log_email(
                'proposal_investment_interest_followup', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent investment interest followup for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_investment_interest_followup', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send investment interest followup for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_share_notification(cls, proposal, share_link):
        """
        Notify the sales team when a client shares the proposal
        with another person (multi-stakeholder signal).
        """
        if not cls._is_template_active('proposal_share_notification'):
            logger.info('Skipping proposal_share_notification: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'shared_by_name': share_link.shared_by_name,
            'shared_by_email': share_link.shared_by_email,
            'proposal_uuid': str(proposal.uuid),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_share_notification', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_share_notification.html', context
            )
            text_content = render_to_string(
                'emails/proposal_share_notification.txt', context
            )

            subject = resolved.get('subject', (
                f'🔗 [SHARED] {proposal.client_name} compartió la propuesta '
                f'"{proposal.title}"'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_share_notification',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent share notification for proposal %s (shared by %s)',
                proposal.uuid, share_link.shared_by_name,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send share notification for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_scheduled_followup(cls, proposal):
        """
        Send a scheduled follow-up email to a client who previously
        rejected the proposal with "Not the right time".
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_scheduled_followup'):
            logger.info('Skipping proposal_scheduled_followup: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'title': proposal.title,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_scheduled_followup', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except, and a
        # render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_scheduled_followup.html', context
            )
            text_content = render_to_string(
                'emails/proposal_scheduled_followup.txt', context
            )

            subject = resolved.get('subject', (
                f'👋 {proposal.client_name}, ¿es buen momento para '
                f'retomar tu proyecto? — Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_scheduled_followup',
            )

            cls._log_email(
                'proposal_scheduled_followup', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent scheduled followup for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_scheduled_followup', proposal.client_email,
                subject='', proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send scheduled followup for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_stakeholder_detected_notification(cls, proposal, known_ips_count):
        """
        Notify the sales team when the proposal is accessed from a new
        IP address, suggesting a secondary decision-maker is reviewing it.
        """
        from content.services.proposal_service import ProposalService
        if ProposalService.open_notifications_suppressed(proposal):
            logger.info(
                'Skipping proposal_stakeholder_detected: proposal %s is %s',
                proposal.uuid, proposal.status,
            )
            return False
        if not cls._is_template_active('proposal_stakeholder_detected'):
            logger.info('Skipping proposal_stakeholder_detected: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'proposal_uuid': str(proposal.uuid),
            'known_ips_count': known_ips_count,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_stakeholder_detected', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_stakeholder_detected.html', context
            )
            text_content = render_to_string(
                'emails/proposal_stakeholder_detected.txt', context
            )

            subject = resolved.get('subject', (
                f'\U0001f465 [NUEVO LECTOR] Propuesta: {proposal.title} — '
                f'{proposal.client_name}'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_stakeholder_detected',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent stakeholder detection notification for proposal %s',
                proposal.uuid,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send stakeholder notification for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_seller_inactivity_escalation(cls, proposal, days_inactive):
        """
        Send an escalation email to the sales team when a proposal has had
        no seller follow-up for >=5 days after the client viewed it.

        Args:
            proposal: BusinessProposal instance.
            days_inactive: Number of days without seller activity.

        Returns:
            bool: True if the email was sent successfully.
        """
        if not cls._is_template_active('seller_inactivity_escalation'):
            logger.info('Skipping seller_inactivity_escalation: template disabled')
            return False

        frontend_base = getattr(
            settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'
        )
        edit_url = f'{frontend_base}/panel/proposals/{proposal.id}/edit'

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'days_inactive': days_inactive,
            'edit_url': edit_url,
            'proposal_uuid': str(proposal.uuid),
            'status': proposal.status,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('seller_inactivity_escalation', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/seller_inactivity_escalation.html', context
            )
            text_content = render_to_string(
                'emails/seller_inactivity_escalation.txt', context
            )

            subject = resolved.get('subject', (
                f'\u26a0\ufe0f Propuesta sin seguimiento: '
                f'{proposal.client_name} — {proposal.title}'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='seller_inactivity_escalation',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent seller inactivity escalation for proposal %s (%d days)',
                proposal.uuid, days_inactive,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send seller inactivity escalation for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_negotiation_notification(cls, proposal, comment=''):
        """
        Send notification to the sales team when a client wants to
        accept with changes (negotiating status).
        """
        if not cls._is_template_active('proposal_negotiation_notification'):
            logger.info('Skipping proposal_negotiation_notification: template disabled')
            return False

        frontend_base = getattr(
            settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'
        )
        edit_url = f'{frontend_base}/panel/proposals/{proposal.id}/edit'

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'comment': comment,
            'edit_url': edit_url,
            'proposal_uuid': str(proposal.uuid),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_negotiation_notification', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_negotiation_notification.html', context
            )
            text_content = render_to_string(
                'emails/proposal_negotiation_notification.txt', context
            )

            subject = resolved.get('subject', (
                f'🤝 [NEGOCIANDO] {proposal.client_name} quiere '
                f'ajustar la propuesta "{proposal.title}"'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_negotiation_notification',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent negotiation notification for proposal %s',
                proposal.uuid,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send negotiation notification for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_negotiation_confirmation(cls, proposal):
        """
        Send confirmation email to the client when they choose
        'accept with changes' (negotiating).
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.info(
                'Skipping client email for proposal %s — placeholder or empty client_email',
                proposal.pk,
            )
            return False

        if not cls._is_template_active('proposal_negotiation_confirmation'):
            logger.info('Skipping proposal_negotiation_confirmation: template disabled')
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_url': proposal.public_url,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_negotiation_confirmation', context)
        context.update(resolved)

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_negotiation_confirmation.html', context
            )
            text_content = render_to_string(
                'emails/proposal_negotiation_confirmation.txt', context
            )

            subject = resolved.get('subject', (
                f'🤝 {proposal.client_name}, recibimos tu solicitud '
                f'de ajustes — Project App'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email, template_key='proposal_negotiation_confirmation',
            )

            cls._log_email(
                'proposal_negotiation_confirmation', proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent negotiation confirmation for proposal %s to %s',
                proposal.uuid, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                'proposal_negotiation_confirmation', proposal.client_email,
                subject=locals().get('subject', ''), proposal=proposal,
                status='failed', error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send negotiation confirmation for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_post_rejection_revisit_alert(cls, proposal):
        """
        Send immediate alert to the sales team when a rejected client
        revisits the proposal after 7+ days — high-intent reconsideration signal.
        """
        if not cls._is_template_active('post_rejection_revisit_alert'):
            logger.info('Skipping post_rejection_revisit_alert: template disabled')
            return False

        frontend_base = getattr(
            settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'
        )
        edit_url = f'{frontend_base}/panel/proposals/{proposal.id}/edit'

        days_since = 0
        if proposal.responded_at:
            days_since = (timezone.now() - proposal.responded_at).days

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'edit_url': edit_url,
            'proposal_uuid': str(proposal.uuid),
            'days_since_rejection': days_since,
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('post_rejection_revisit_alert', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/post_rejection_revisit_alert.html', context
            )
            text_content = render_to_string(
                'emails/post_rejection_revisit_alert.txt', context
            )

            subject = resolved.get('subject', (
                f'🔄 [RECONSIDERACIÓN] {proposal.client_name} revisitó la '
                f'propuesta rechazada "{proposal.title}" ({days_since}d después)'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='post_rejection_revisit_alert',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent post-rejection revisit alert for proposal %s (%d days)',
                proposal.uuid, days_since,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send post-rejection revisit alert for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_daily_pipeline_digest(cls, digest_data):
        """
        Send a daily pipeline digest email summarising proposal activity.

        Args:
            digest_data: dict with keys:
                - viewed_yesterday: list of proposal dicts
                - inactive: list of proposal dicts
                - expiring_soon: list of proposal dicts
                - total_active: int
                - date: str
        """
        if not cls._is_template_active('daily_pipeline_digest'):
            logger.info('Skipping daily_pipeline_digest: template disabled')
            return False

        context = digest_data

        context.update(_build_design_context())
        resolved = cls._resolve_content('daily_pipeline_digest', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/daily_pipeline_digest.html', context
            )
            text_content = render_to_string(
                'emails/daily_pipeline_digest.txt', context
            )

            subject = resolved.get('subject', (
                f'📊 Pipeline Diario — {digest_data["date"]} — '
                f'{digest_data["total_active"]} propuestas activas'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='daily_pipeline_digest',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info('Sent daily pipeline digest for %s', digest_data['date'])
            return True

        except Exception:
            logger.exception('Failed to send daily pipeline digest')
            return False

    @classmethod
    def send_post_expiration_visit_alert(cls, proposal):
        """
        Send immediate alert to the sales team when a client opens
        an expired proposal — high-intent signal.
        """
        if not cls._is_template_active('proposal_post_expiration_visit'):
            logger.info('Skipping proposal_post_expiration_visit: template disabled')
            return False

        frontend_base = getattr(
            settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'
        )
        edit_url = f'{frontend_base}/panel/proposals/{proposal.id}/edit'

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'total_investment': format_cop_email(proposal.total_investment),
            'currency': proposal.currency,
            'edit_url': edit_url,
            'proposal_uuid': str(proposal.uuid),
        }

        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content('proposal_post_expiration_visit', context)
        context.update(resolved)

        try:
            html_content = render_to_string(
                'emails/proposal_post_expiration_visit.html', context
            )
            text_content = render_to_string(
                'emails/proposal_post_expiration_visit.txt', context
            )

            subject = resolved.get('subject', (
                f'🔥 {proposal.client_name} abrió la propuesta expirada '
                f'"{proposal.title}" — ¡Alto interés!'
            ))

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key='proposal_post_expiration_visit',
                classification=DeliveryClassification.INTERNAL,
            )

            logger.info(
                'Sent post-expiration visit alert for proposal %s',
                proposal.uuid,
            )
            return True

        except Exception:
            logger.exception(
                'Failed to send post-expiration visit alert for proposal %s',
                proposal.uuid,
            )
            return False

    @classmethod
    def send_magic_link_email(cls, email, proposals):
        """
        Send a magic link email containing links to the client's proposals.

        Args:
            email: Client email address.
            proposals: List of BusinessProposal instances.
        """
        if not proposals:
            return False

        proposal_links = []
        for p in proposals:
            proposal_links.append({
                'title': p.title,
                'url': p.public_url,
                'status': p.get_status_display(),
                'created_at': format_bogota_date(p.created_at) if p.created_at else '',
            })

        client_name = proposals[0].client_name or ''
        subject = f'Tus propuestas en Project App — {client_name}'

        # Build simple HTML email
        links_html = ''
        for link in proposal_links:
            links_html += (
                f'<tr><td style="padding:12px 16px;border-bottom:1px solid #f0f0f0;">'
                f'<a href="{link["url"]}" style="color:#059669;text-decoration:none;'
                f'font-weight:600;">{link["title"]}</a>'
                f'<br><span style="color:#9ca3af;font-size:12px;">'
                f'{link["status"]} — {link["created_at"]}</span>'
                f'</td></tr>'
            )

        html_content = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                     max-width:560px;margin:0 auto;padding:32px 24px;">
            <h2 style="color:#111827;font-weight:400;margin-bottom:8px;">
                Hola{(' ' + client_name) if client_name else ''},
            </h2>
            <p style="color:#6b7280;line-height:1.6;">
                Solicitaste acceso a tus propuestas. Aquí están los enlaces:
            </p>
            <table style="width:100%;border-collapse:collapse;margin:24px 0;
                          background:#fafafa;border-radius:8px;overflow:hidden;">
                {links_html}
            </table>
            <p style="color:#9ca3af;font-size:13px;margin-top:24px;">
                Si no solicitaste este email, puedes ignorarlo.
            </p>
            <p style="color:#d1d5db;font-size:12px;margin-top:32px;">
                Project App — projectapp.co
            </p>
        </div>
        """

        text_content = (
            f'Hola {client_name},\n\n'
            f'Solicitaste acceso a tus propuestas:\n\n'
            + '\n'.join(
                f'- {l["title"]}: {l["url"]}' for l in proposal_links
            )
            + '\n\nProject App — projectapp.co'
        )

        try:
            email_msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[email],
            )
            email_msg.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email_msg, template_key='magic_link',
            )

            cls._log_email(
                'magic_link', email, subject=subject,
                proposal=proposals[0],
                html_body=html_content, text_body=text_content,
            )

            logger.info('Sent magic link email to %s with %d proposals', email, len(proposals))
            return True

        except Exception:
            cls._log_email(
                'magic_link', email, subject=subject,
                proposal=proposals[0], status='failed',
                error_message='Send failed',
                html_body=html_content, text_body=text_content,
            )
            logger.exception('Failed to send magic link email to %s', email)
            return False

    @classmethod
    def send_documents_to_client(cls, proposal, attachments,
                                  subject=None, greeting=None, body=None,
                                  footer=None, document_descriptions=None):
        """
        Send selected documents to the client as email attachments.

        The admin composes the email content in a modal before sending.
        If content fields are not provided, defaults from the registry are used.

        Args:
            proposal: BusinessProposal instance.
            attachments: list of (filename, pdf_bytes, mime_type) tuples.
            subject: Email subject (pre-resolved by frontend).
            greeting: Greeting text.
            body: Introductory body text.
            footer: Closing text.
            document_descriptions: list of dicts [{'name': str, 'description': str}].

        Returns:
            bool: True if the email was sent successfully.
        """
        if _is_unsendable_client_email(proposal.client_email):
            logger.warning(
                'Cannot send documents for proposal %s: missing or placeholder client_email',
                proposal.pk,
            )
            return False

        template_key = 'proposal_documents_sent'
        if not cls._is_template_active(template_key):
            logger.info('Skipping %s: template disabled', template_key)
            return False

        # Fall back to registry defaults for any missing fields
        if not subject or not greeting or not body or not footer:
            fallback_context = {
                'client_name': proposal.client_name,
                'title': proposal.title,
            }
            resolved = cls._resolve_content(template_key, fallback_context)
            if not subject:
                subject = resolved.get('subject', (
                    f'\U0001f4ce {proposal.client_name}, te compartimos documentos '
                    f'de tu proyecto \u2014 Project App'
                ))
            if not greeting:
                greeting = resolved.get('greeting', f'Hola {proposal.client_name}')
            if not body:
                body = resolved.get('body', '')
            if not footer:
                footer = resolved.get('footer', '')

        context = {
            'client_name': proposal.client_name,
            'title': proposal.title,
            'greeting': greeting,
            'body': body,
            'footer': footer or '',
            'document_descriptions': document_descriptions or [],
        }
        context.update(_build_design_context(proposal))

        # Bound before the try: the failure path logs from the except,
        # and a render error must not turn into a NameError there.
        html_content = text_content = ''
        try:
            html_content = render_to_string(
                'emails/proposal_documents_sent.html', context
            )
            text_content = render_to_string(
                'emails/proposal_documents_sent.txt', context
            )

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=[proposal.client_email],
            )
            email.attach_alternative(html_content, 'text/html')

            for filename, data, mime_type in attachments:
                email.attach(filename, data, mime_type)

            EmailDeliveryGateway.send(email, template_key=template_key)

            cls._log_email(
                template_key, proposal.client_email,
                subject=subject, proposal=proposal, status='sent',
                html_body=html_content, text_body=text_content,
            )
            logger.info(
                'Sent %d documents for proposal %s to %s',
                len(attachments), proposal.pk, proposal.client_email,
            )
            return True

        except Exception as exc:
            cls._log_email(
                template_key, proposal.client_email,
                subject='', proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                html_body=html_content, text_body=text_content,
            )
            logger.exception(
                'Failed to send documents for proposal %s', proposal.pk,
            )
            return False

    # ── User-composed emails (branded & proposal) ───────────────────

    @classmethod
    def render_composed_email(
        cls, template_key, proposal, subject, greeting,
        sections, footer='', attachment_names=None,
    ):
        """Render a user-composed email exactly as the send path does.

        Returns ``(html_content, text_content)``. ``sections`` accepts both
        plain strings and ``{'text', 'markdown'}`` dicts; markdown sections
        are converted to inline-styled HTML for the html alternative while
        the text alternative keeps the raw text. Shared by the send funnel
        and the composed-email preview endpoint so they can never drift.
        """
        from content.services.email_markdown import (
            markdown_to_email_html, normalize_sections,
        )
        from content.services.email_template_registry import get_template_entry

        normalized = normalize_sections(sections)
        html_sections = []
        for item in normalized:
            if item['markdown']:
                html = markdown_to_email_html(item['text'])
                # Empty conversion (e.g. only [TOC]) falls back to plain text.
                html_sections.append({'html': html} if html else item['text'])
            else:
                html_sections.append(item['text'])
        text_sections = [item['text'] for item in normalized]

        base_context = {
            'subject': subject,
            'greeting': greeting,
            'footer': footer,
            'attachment_names': attachment_names or [],
        }
        base_context.update(_build_design_context(proposal))

        # Standalone emails (no proposal) honor the signer configured in the
        # panel defaults form; proposal emails keep their per-proposal signer.
        if proposal is None:
            sig = _resolve_signature(_configured_standalone_signer())
            base_context['signature_name'] = sig['name']
            base_context['signature_role'] = sig['role']

        entry = get_template_entry(template_key)
        html_content = render_to_string(
            entry['html_template'], {**base_context, 'sections': html_sections},
        )
        text_content = render_to_string(
            entry['txt_template'], {**base_context, 'sections': text_sections},
        )
        return html_content, text_content

    @classmethod
    def _send_composed_email(
        cls, template_key, proposal, recipient_emails=None, subject='',
        greeting='', sections=(), footer='', attachments=None, targets=(),
        return_logs=False, attachment_sources=None, cc_emails=None,
        recipient_email=None,
    ):
        """
        Send a user-composed email with the standard Project App branding.

        Shared implementation for branded emails and proposal emails.
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
            'greeting': greeting,
            'sections': normalized_sections,
            'footer': footer,
            'attachment_names': attachment_names,
            'to_recipients': to_recipients,
            'cc_recipients': cc_recipients,
        }

        # A composed email goes wherever the panel addressed it — a
        # stakeholder, an internal inbox, or the client — so the audience is a
        # fact of this send and not of its template. It counts as contact only
        # when it actually reached the client's own address.
        from content.models import EmailLog

        contextual_client = getattr(proposal, 'client', None) if proposal else None
        recipient_contexts = recipient_log_contexts(
            to_recipients,
            cc_recipients,
            contextual_client=contextual_client,
        )

        html_content = text_content = ''
        try:
            html_content, text_content = cls.render_composed_email(
                template_key, proposal, subject, greeting,
                normalized_sections, footer, attachment_names,
            )

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=to_recipients,
                cc=cc_recipients,
            )
            email.attach_alternative(html_content, 'text/html')

            if attachments:
                for filename, data, mime_type in attachments:
                    email.attach(filename, data, mime_type)

            classification = (
                DeliveryClassification.CLIENT
                if proposal is None or any(
                    item['audience'] == EmailLog.Audience.CLIENT
                    for item in recipient_contexts
                )
                else DeliveryClassification.INTERNAL
            )
            EmailDeliveryGateway.send(
                email,
                template_key=template_key,
                classification=classification,
                attachment_sources=attachment_sources,
            )

            logs = cls._log_email(
                template_key,
                recipients=all_recipients,
                recipient_contexts=recipient_contexts,
                subject=subject, proposal=proposal, status='sent',
                metadata=log_metadata, audience=EmailLog.Audience.INTERNAL,
                html_body=html_content, text_body=text_content,
                targets=targets,
            )
            logger.info(
                'Sent %s for proposal %s to %s',
                template_key, proposal.pk if proposal else 'standalone', all_recipients,
            )
            return (True, logs) if return_logs else True

        except Exception as exc:
            logs = cls._log_email(
                template_key,
                recipients=all_recipients,
                recipient_contexts=recipient_contexts,
                subject=subject, proposal=proposal, status='failed',
                error_message=str(exc)[:1000],
                metadata=log_metadata, audience=EmailLog.Audience.INTERNAL,
                html_body=html_content, text_body=text_content,
                targets=targets,
            )
            logger.exception(
                'Failed to send %s for proposal %s', template_key, proposal.pk if proposal else 'standalone',
            )
            return (False, logs) if return_logs else False

    @classmethod
    def send_branded_email(
        cls, proposal, recipient_emails=None, subject='', greeting='',
        sections=(), footer='', attachments=None, cc_emails=None,
        recipient_email=None,
    ):
        """Send a user-composed branded email (generic, no activity logging)."""
        return cls._send_composed_email(
            'branded_email', proposal, recipient_emails, subject,
            greeting, sections, footer, attachments,
            cc_emails=cc_emails, recipient_email=recipient_email,
        )

    @classmethod
    def send_standalone_branded_email(
        cls, recipient_emails=None, subject='', greeting='',
        sections=(), footer='', attachments=None, targets=(), return_logs=False,
        attachment_sources=None, cc_emails=None, recipient_email=None,
    ):
        """Send a standalone branded email not tied to any proposal."""
        return cls._send_composed_email(
            'branded_email', None, recipient_emails, subject,
            greeting, sections, footer, attachments, targets, return_logs,
            attachment_sources, cc_emails, recipient_email,
        )

    @classmethod
    def send_proposal_email(
        cls, proposal, recipient_emails=None, subject='', greeting='',
        sections=(), footer='', attachments=None, cc_emails=None,
        recipient_email=None,
    ):
        """Send a proposal-specific email and register it as a proposal activity."""
        to_values = (
            [recipient_emails]
            if isinstance(recipient_emails, str)
            else list(
                recipient_emails
                or ([recipient_email] if recipient_email else [])
            )
        )
        to_count = len(to_values)
        cc_count = 1 if isinstance(cc_emails, str) else len(cc_emails or [])
        sent = cls._send_composed_email(
            'proposal_email', proposal, recipient_emails, subject,
            greeting, sections, footer, attachments,
            cc_emails=cc_emails, recipient_email=recipient_email,
        )
        if sent:
            from content.models import ProposalChangeLog
            ProposalChangeLog.objects.create(
                proposal=proposal,
                change_type=ProposalChangeLog.ChangeType.EMAIL_SENT,
                actor_type=ProposalChangeLog.ActorType.SELLER,
                description=(
                    f'Correo enviado a {", ".join(to_values)} '
                    f'({to_count} destinatario(s), {cc_count} CC): {subject}'
                ),
            )
            proposal.last_activity_at = timezone.now()
            proposal.save(update_fields=['last_activity_at'])
        return sent

    # ------------------------------------------------------------------
    # Project-stage tracking notifications (internal team)
    #
    # Called by the daily Huey task `notify_proposal_stage_deadlines` via
    # ProposalStageTracker. Match the convention used by every other
    # internal-team notification in this file: no _check_cooldown() (per-
    # stage dedup is handled by warning_sent_at / last_overdue_reminder_at
    # at the task level), no _log_email() (those are for client-facing
    # sends), and recipients via _get_notification_recipients() which
    # reads NOTIFICATION_EMAIL / NOTIFICATION_EMAILS (CSV supported).
    # ------------------------------------------------------------------

    @classmethod
    def _build_panel_schedule_url(cls, proposal):
        """Build a deep link to the proposal's Cronograma tab in the panel."""
        frontend_base = getattr(
            settings, 'FRONTEND_BASE_URL', 'http://localhost:3000'
        ).rstrip('/')
        return f'{frontend_base}/panel/proposals/{proposal.id}/edit?tab=schedule'

    @classmethod
    def _send_stage_notification(
        cls, *, template_key, proposal, stage, context_extras, fallback_subject,
    ):
        """
        Shared scaffolding for stage warning + overdue emails.

        Returns True iff the email was dispatched. Skips silently when the
        admin has disabled the template via EmailTemplateConfig.
        """
        if not cls._is_template_active(template_key):
            logger.info('Skipping %s: template disabled', template_key)
            return False

        context = {
            'client_name': proposal.client_name,
            'proposal_title': proposal.title,
            'title': proposal.title,
            'stage_label': stage.get_stage_key_display(),
            'stage_key': stage.stage_key,
            'start_date_human': format_bogota_date(stage.start_date) if stage.start_date else '',
            'end_date_human': format_bogota_date(stage.end_date) if stage.end_date else '',
            'edit_url': cls._build_panel_schedule_url(proposal),
            'proposal_uuid': str(proposal.uuid),
            **context_extras,
        }
        context.update(_build_design_context(proposal))
        resolved = cls._resolve_content(template_key, context)
        context.update(resolved)
        subject = resolved.get('subject') or fallback_subject

        try:
            html_content = render_to_string(f'emails/{template_key}.html', context)
            text_content = render_to_string(f'emails/{template_key}.txt', context)
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from_email(),
                to=cls._get_notification_recipients(),
            )
            email.attach_alternative(html_content, 'text/html')
            EmailDeliveryGateway.send(
                email,
                template_key=template_key,
                classification=DeliveryClassification.INTERNAL,
            )
            logger.info(
                'Sent %s for proposal %s stage %s',
                template_key, proposal.uuid, stage.stage_key,
            )
            return True
        except Exception:
            logger.exception(
                'Failed to send %s for proposal %s stage %s',
                template_key, proposal.uuid, stage.stage_key,
            )
            return False

    @classmethod
    def send_stage_warning(cls, proposal, stage, days_remaining):
        """Send the 70%-elapsed pre-deadline warning to the team."""
        from content.services.proposal_stage_tracker import ProposalStageTracker
        stage_label = stage.get_stage_key_display()
        return cls._send_stage_notification(
            template_key='proposal_stage_warning_notification',
            proposal=proposal,
            stage=stage,
            context_extras={
                'days_remaining': days_remaining,
                'time_remaining_human': ProposalStageTracker.format_remaining_time(days_remaining),
            },
            fallback_subject=(
                f'\u26a0\ufe0f Etapa {stage_label} cerca de vencer — '
                f'{proposal.client_name} ({proposal.title})'
            ),
        )

    @classmethod
    def send_stage_overdue(cls, proposal, stage, days_overdue):
        """Send the overdue alert to the team (first day past end_date + every 3 days)."""
        from content.services.proposal_stage_tracker import ProposalStageTracker
        stage_label = stage.get_stage_key_display()
        return cls._send_stage_notification(
            template_key='proposal_stage_overdue_notification',
            proposal=proposal,
            stage=stage,
            context_extras={
                'days_overdue': days_overdue,
                'time_overdue_human': ProposalStageTracker.format_remaining_time(days_overdue),
            },
            fallback_subject=(
                f'\U0001f534 Etapa {stage_label} VENCIDA — '
                f'{proposal.client_name} ({proposal.title})'
            ),
        )
