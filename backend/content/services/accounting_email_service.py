"""Email notifications for accounting module changes.

Every create/update/delete on an accounting record produces one email to
the recipients configured in AccountingSettings (Gustavo's and Carlos's
inboxes). Best-effort: never raises; every attempt is recorded in EmailLog.
"""

import logging

from django.conf import settings
from django.template.loader import render_to_string

from content.services import email_log_service
from content.services.accounting_display import display_accounting_changes
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from content.services.notification_recipient_service import (
    active_recipient_emails,
)

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'accounting_change'

NOTIFICATION_TONE_INCOME = 'income'
NOTIFICATION_TONE_OUTFLOW = 'outflow'
NOTIFICATION_TONE_NEUTRAL = 'neutral'

NOTIFICATION_TONE_COLORS = {
    NOTIFICATION_TONE_INCOME: '#15803d',
    NOTIFICATION_TONE_OUTFLOW: '#b45309',
    NOTIFICATION_TONE_NEUTRAL: '#1d4ed8',
}

ACTION_COLORS = {
    'created': '#15803d',
    'updated': '#1d4ed8',
    'deleted': '#b91c1c',
}

_INCOME_ENTITY_TYPES = frozenset({'income'})
_OUTFLOW_ENTITY_TYPES = frozenset({
    'expense',
    'recurring',
    'ads',
    'card_snapshot',
    'statement',
    'statement_tx',
})

# Panel subview per entity, used for the email CTA link.
_PANEL_PATHS = {
    'income': '/panel/accounting/incomes',
    'expense': '/panel/accounting/expenses',
    'hosting': '/panel/accounting/hostings',
    'pocket': '/panel/accounting/pocket',
    'recurring': '/panel/accounting/recurring',
    'ads': '/panel/accounting/ads',
    'card_snapshot': '/panel/accounting/cards',
    'settings': '/panel/accounting/settings',
}


def resolve_accounting_notification_tone(change_log):
    """Classify one accounting audit event by financial meaning."""
    if change_log.entity_type in _INCOME_ENTITY_TYPES:
        return NOTIFICATION_TONE_INCOME
    if change_log.entity_type in _OUTFLOW_ENTITY_TYPES:
        return NOTIFICATION_TONE_OUTFLOW
    if change_log.entity_type == 'pocket':
        if change_log.movement_direction == 'in':
            return NOTIFICATION_TONE_INCOME
        if change_log.movement_direction == 'out':
            return NOTIFICATION_TONE_OUTFLOW
    return NOTIFICATION_TONE_NEUTRAL


def build_accounting_change_context(change_log):
    """Build the template context for an accounting-change email."""
    base_url = getattr(settings, 'FRONTEND_BASE_URL', '').rstrip('/')
    path = _PANEL_PATHS.get(change_log.entity_type, '/panel/accounting')
    notification_tone = resolve_accounting_notification_tone(change_log)
    return {
        'action': change_log.action,
        'action_label': change_log.get_action_display(),
        'entity_label': change_log.get_entity_type_display(),
        'object_repr': change_log.object_repr,
        'actor_name': change_log.actor_username or 'Sistema',
        'changes': display_accounting_changes(change_log.changes),
        'is_created': change_log.action == 'created',
        'is_updated': change_log.action == 'updated',
        'is_deleted': change_log.action == 'deleted',
        'occurred_at': change_log.created_at,
        'panel_url': f'{base_url}{path}',
        'history_url': f'{base_url}/panel/accounting/history',
        'notification_tone': notification_tone,
        'accent_color': ACTION_COLORS.get(change_log.action, '#374151'),
    }


def send_accounting_change_email(change_log_id, *, recipients=None, retry_of=None):
    """
    Render and send the change notification to the configured recipients.
    Returns True if the email was sent, False otherwise. Never raises.

    `recipients` overrides the configured list — a manual retry re-sends to
    the one address that failed, not to everybody who already got it.
    """
    from content.models import AccountingChangeLog, AccountingSettings, EmailLog

    try:
        change_log = AccountingChangeLog.objects.get(id=change_log_id)
    except AccountingChangeLog.DoesNotExist:
        logger.warning(
            'AccountingChangeLog %s not found for notification email',
            change_log_id,
        )
        return False

    config = AccountingSettings.load()
    if not config.notifications_enabled:
        logger.info(
            'Accounting notifications disabled; skipping change_log %s',
            change_log_id,
        )
        return False

    recipients = recipients or active_recipient_emails()
    if not recipients:
        logger.warning(
            'No accounting notification recipients configured; '
            'skipping change_log %s',
            change_log_id,
        )
        return False

    context = build_accounting_change_context(change_log)
    subject = (
        f'[Contabilidad] {context["entity_label"]} '
        f'{context["action_label"].lower()}: {context["object_repr"]}'
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co')
    metadata = {
        'change_log_id': change_log.id,
        'entity_type': change_log.entity_type,
        'action': change_log.action,
    }

    targets = [(
        change_log.entity_type, change_log.object_id, change_log.object_repr,
    )]
    # Internal by default: this notice goes to the team, not to the client.
    # It is still filed under them, because the change it reports is theirs.
    client = email_log_service.client_for_entity(
        change_log.entity_type, change_log.object_id,
    )
    text_body = html_body = ''

    try:
        text_body = render_to_string('emails/accounting_change.txt', context)
        html_body = render_to_string('emails/accounting_change.html', context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=recipients,
        )
        email.attach_alternative(html_body, 'text/html')
        EmailDeliveryGateway.send(
            email,
            template_key=TEMPLATE_KEY,
            classification=DeliveryClassification.INTERNAL,
        )
    except Exception as exc:
        logger.warning(
            'Failed to send accounting change email for change_log %s: %s',
            change_log_id, exc,
        )
        email_log_service.record_send(
            template_key=TEMPLATE_KEY,
            recipients=recipients,
            subject=subject,
            status=EmailLog.Status.FAILED,
            error_message=str(exc),
            metadata=metadata,
            targets=targets,
            origin_action=change_log.action,
            html_body=html_body,
            text_body=text_body,
            retry_of=retry_of,
            client=client,
        )
        return False

    email_log_service.record_send(
        template_key=TEMPLATE_KEY,
        recipients=recipients,
        subject=subject,
        status=EmailLog.Status.SENT,
        metadata=metadata,
        targets=targets,
        origin_action=change_log.action,
        html_body=html_body,
        text_body=text_body,
        retry_of=retry_of,
        client=client,
    )
    logger.info(
        'Sent accounting change email (change_log %s) to %s',
        change_log_id, ', '.join(recipients),
    )
    return True
