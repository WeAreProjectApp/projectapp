"""Team notice for secure links created by clients from the public page.

The email never contains the link token or the content: it only says who
sent something and where to open it in the panel.
"""

import logging

from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
    EmailMultiAlternatives,
)
from django.conf import settings
from django.template.loader import render_to_string
from huey.contrib.djhuey import task

logger = logging.getLogger(__name__)

TEMPLATE_KEY = 'secure_link_received_team'


def send_received_notice(link_id):
    """Email the team inbox about a client-created link. Never raises."""
    from content.services.proposal_email_service import ProposalEmailService

    from .catalog import type_label
    from .models import SecureLink
    from .services import panel_url

    link = SecureLink.objects.filter(pk=link_id).first()
    if link is None:
        return False
    recipients = ProposalEmailService._get_notification_recipients()
    if not recipients:
        logger.warning('No team recipients configured; skipping secure-link notice')
        return False
    context = {
        'creator_name': link.creator_name or 'Cliente',
        'creator_email': link.creator_email,
        'type_label': type_label(link.secret_type),
        'title': link.title,
        'created_at': link.created_at,
        'expires_at': link.expires_at,
        'panel_url': panel_url(link),
    }
    try:
        email = EmailMultiAlternatives(
            subject=f'Enlace seguro recibido · {context["creator_name"]} · ProjectApp',
            body=render_to_string('emails/secure_link_received_team.txt', context),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'team@projectapp.co'),
            to=recipients,
        )
        email.attach_alternative(render_to_string('emails/secure_link_received_team.html', context), 'text/html')
        EmailDeliveryGateway.send(email, template_key=TEMPLATE_KEY, classification=DeliveryClassification.INTERNAL)
        return True
    except Exception as exc:  # best effort: the link already exists in the panel
        logger.warning('Failed to send secure-link notice for %s: %s', link_id, exc)
        return False


@task()
def notify_team_secure_link_received(link_id):
    return send_received_notice(link_id)
