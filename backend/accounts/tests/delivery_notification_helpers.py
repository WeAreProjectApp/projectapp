"""Real delivery-notice setup shared by the focused service and JWT tests."""
from unittest.mock import patch

from content.models import McpConnector, McpCredential

from accounts.models_delivery_notifications import DeliveryNotificationEvent
from accounts.services import delivery_notifications as notices
from accounts.services import delivery_workflow as delivery
from accounts.tests.delivery_helpers import publish, version


def published_notice(context):
    """Publish a genuine stage without running its after-commit send yet."""
    publish(context)
    return DeliveryNotificationEvent.objects.get(project=context.project)


def failed_notice(context):
    """Run the real snapshot gateway with a rejected SMTP boundary."""
    event = published_notice(context)
    with patch('accounts.services.delivery_notifications.EmailMultiAlternatives.send', return_value=0):
        notices.send_attempt(event.attempts.get().pk)
    event.refresh_from_db()
    return event


def retry_payload(context, event, **overrides):
    """Prepare an exact retry manifest through the production service."""
    preview = notices.retry_impact(context.project.pk, context.admin, event.pk, event.version)
    data = {'expected_version': event.version, 'request_id': 'manual-notice-retry',
            'preview_sha256': preview['preview_sha256']}
    data.update(overrides)
    return data


def public_message(context, actor, *, request_id='public-message', internal=False):
    """Write a response through the same service used by JWT and MCP."""
    return delivery.add_message(context.project.pk, actor, {
        'expected_version': version(context), 'request_id': request_id,
        'level': 'stage', 'target_id': context.stage.pk,
        'message': 'El registro preparado está listo para la nueva comprobación.',
        'is_internal': internal,
    })


def create_credential(actor, *, label='notice-qa'):
    """Create a scoped credential without exposing or generating a live token."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='projects', defaults={'name': 'Projects', 'is_active': True},
    )
    return McpCredential.objects.create(
        connector=connector, label=label, actor=actor, token_hash='a' * 64,
    )
