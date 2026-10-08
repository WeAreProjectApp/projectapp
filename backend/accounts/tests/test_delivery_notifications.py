"""Activity email claims preserve recipients, public snapshots and uncertainty."""
from unittest.mock import patch

import pytest
from content.models import EmailDeliverySnapshot
from content.services.email_delivery_service import EmailDeliveryGateway
from django.core import mail
from django.db import transaction
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from accounts.models import (
    DeliveryMessage,
    DeliveryPublication,
    Notification,
    RequirementReview,
)
from accounts.models_delivery_notifications import (
    DeliveryNotificationAttempt,
    DeliveryNotificationEvent,
)
from accounts.services import delivery_notifications as notices
from accounts.services import delivery_workflow as delivery
from accounts.services.delivery_access import DeliveryConflict
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish
from accounts.tests.delivery_notification_helpers import (
    failed_notice,
    public_message,
    published_notice,
    retry_payload,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory_mail(settings):
    """Keep every transport and team address inside the isolated test boundary."""
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    settings.NOTIFICATION_EMAIL = 'team@example.test'
    settings.NOTIFICATION_EMAILS = []
    settings.FRONTEND_URL = 'https://delivery.example.test'
    mail.outbox = []


@pytest.fixture
def context():
    """Build profiles before their after-commit provisioning hooks can run."""
    with transaction.atomic():
        return build_delivery_context()


def test_publication_waits_for_commit_before_transport(context, django_capture_on_commit_callbacks):
    """Fails if publishing sends mail before the delivery transaction commits."""
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        event = published_notice(context)

    assert event.status == 'pending'
    assert event.attempts.get().status == 'pending'
    assert mail.outbox == []
    assert len(callbacks) == 1


def test_publication_sends_one_client_snapshot(context, django_capture_on_commit_callbacks):
    """Fails if a committed publication misses its owner or loses its retained body."""
    with django_capture_on_commit_callbacks(execute=True):
        event = published_notice(context)
    event.refresh_from_db()
    snapshot = event.attempts.get().gateway_snapshot

    assert (event.status, event.audience) == ('sent', 'client')
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [context.client.email]
    assert snapshot.body.text == event.text_body
    assert snapshot.body.html == event.html_body
    assert snapshot.subject == event.subject
    assert f'https://delivery.example.test/es-co/platform/projects/{context.project.pk}/delivery?stage={context.stage.pk}' in mail.outbox[0].body


def test_publication_replay_preserves_one_notice(context, django_capture_on_commit_callbacks):
    """Fails if replaying the operation creates a second SMTP attempt or publication."""
    data = {'expected_version': 0, 'request_id': 'publish-once'}
    with django_capture_on_commit_callbacks(execute=True):
        delivery.publish_stage(context.project.pk, context.admin, context.stage.pk, data)
        delivery.publish_stage(context.project.pk, context.admin, context.stage.pk, data)

    assert DeliveryNotificationEvent.objects.count() == 1
    assert DeliveryNotificationAttempt.objects.count() == 1
    assert DeliveryPublication.objects.count() == 1
    assert len(mail.outbox) == 1


@pytest.mark.parametrize('decision', ['objected', 'rejected'])
def test_review_attention_notifies_the_team(context, django_capture_on_commit_callbacks, decision):
    """Fails if an objection or rejection omits its motive from the team notice."""
    publish(context)
    with django_capture_on_commit_callbacks(execute=True):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                              decisions(context, (context.second, decision)))
    event = DeliveryNotificationEvent.objects.get(audience='team')

    assert event.status == 'sent'
    assert mail.outbox[0].to == ['team@example.test']
    assert 'El registro no se guarda' in mail.outbox[0].body
    assert RequirementReview.objects.get().decision == decision


def test_plain_approval_keeps_an_in_app_receipt(context, django_capture_on_commit_callbacks):
    """Fails if ordinary approval sends an automatic legal constance by email."""
    publish(context)
    with django_capture_on_commit_callbacks(execute=True):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                              decisions(context, (context.first, 'approved')))

    assert mail.outbox == []
    assert DeliveryNotificationEvent.objects.filter(audience='team').count() == 0
    assert Notification.objects.filter(user=context.admin, title='Revisión recibida: Etapa').count() == 1


@pytest.mark.parametrize(('actor_role', 'audience', 'recipient'), [
    ('admin', 'client', 'client@example.test'), ('client', 'team', 'team@example.test'),
])
def test_public_message_notifies_its_recipient(context, django_capture_on_commit_callbacks, actor_role, audience, recipient):
    """Fails if a public response emails its author instead of the opposite audience."""
    publish(context)
    with django_capture_on_commit_callbacks(execute=True):
        public_message(context, getattr(context, actor_role))
    event = DeliveryNotificationEvent.objects.get(event_type=f'delivery_message_{audience}')

    assert event.status == 'sent'
    assert mail.outbox[0].to == [recipient]
    assert 'nueva comprobación' in event.text_body


def test_internal_message_creates_no_activity_email(context, django_capture_on_commit_callbacks):
    """Fails if a private team note becomes a public notice or email."""
    with django_capture_on_commit_callbacks(execute=True):
        public_message(context, context.admin, internal=True)

    assert DeliveryMessage.objects.get().is_internal is True
    assert DeliveryNotificationEvent.objects.count() == 0
    assert mail.outbox == []


def test_invalid_review_rolls_back_its_notice(context, django_capture_on_commit_callbacks):
    """Fails if a partially invalid review leaves an email or accepted decision behind."""
    publish(context)
    payload = decisions(context, (context.first, 'approved'), (context.second, 'objected'))
    payload['decisions'][1]['message'] = ''
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(ValidationError):
        delivery.review_stage(context.project.pk, context.client, context.stage.pk, payload)

    assert RequirementReview.objects.count() == 0
    assert DeliveryNotificationEvent.objects.filter(audience='team').count() == 0
    assert mail.outbox == []


def test_stale_publication_creates_no_notice(context, django_capture_on_commit_callbacks):
    """Fails if a rejected workspace version still produces an activity event."""
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(DeliveryConflict):
        delivery.publish_stage(context.project.pk, context.admin, context.stage.pk,
                               {'expected_version': 99, 'request_id': 'stale-publication'})

    assert DeliveryNotificationEvent.objects.count() == 0
    assert DeliveryPublication.objects.count() == 0
    assert mail.outbox == []


def test_new_round_creates_another_client_notice(context, django_capture_on_commit_callbacks):
    """Fails if a corrected round reuses the previous publication notice."""
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'objected')))
    with django_capture_on_commit_callbacks(execute=True):
        publish(context, 'round-two')

    assert DeliveryNotificationEvent.objects.filter(audience='client').count() == 2
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [context.client.email]
    assert context.first.reviews.get().decision == 'approved'


def test_pending_queue_failure_is_recovered(context, django_capture_on_commit_callbacks):
    """Fails if a queue outage loses the durable event or repeats its recovery send."""
    with patch('accounts.tasks.send_delivery_notification_task', side_effect=ConnectionError('Queue offline')):
        with django_capture_on_commit_callbacks(execute=True):
            event = published_notice(context)

    notices.dispatch_pending()
    notices.dispatch_pending()
    event.refresh_from_db()

    assert event.status == 'sent'
    assert event.attempts.count() == 1
    assert len(mail.outbox) == 1


def test_uncertain_smtp_result_is_never_retried_automatically(context):
    """Fails if an uncertain SMTP outcome permits another automatic delivery."""
    event = published_notice(context)
    with patch('accounts.services.delivery_notifications.EmailMultiAlternatives.send', side_effect=RuntimeError('SMTP result lost')):
        notices.send_attempt(event.attempts.get().pk)

    notices.dispatch_pending()
    event.refresh_from_db()

    assert event.status == 'unknown'
    assert event.error_code == 'transport_result_unknown'
    assert event.attempts.count() == 1
    assert EmailDeliverySnapshot.objects.filter(template_key=event.event_type).count() == 1
    assert mail.outbox == []


def test_failed_retry_preserves_the_original_email(context, django_capture_on_commit_callbacks):
    """Fails if retry uses edited live data instead of the reviewed notice body."""
    event = failed_notice(context)
    payload = retry_payload(context, event)
    context.project.name = 'Nombre posterior que no fue revisado'
    context.project.save(update_fields=['name'])
    with django_capture_on_commit_callbacks(execute=True):
        notices.retry_event(context.project.pk, context.admin, event.pk, **payload)
    event.refresh_from_db()

    assert event.status == 'sent'
    assert mail.outbox[0].subject == 'Etapa disponible: Etapa'
    assert mail.outbox[0].body == event.text_body
    assert 'Nombre posterior' not in mail.outbox[0].body
    assert event.attempts.count() == 2


def test_failed_retry_replay_sends_only_once(context, django_capture_on_commit_callbacks):
    """Fails if retrying a lost HTTP response creates another transport attempt."""
    event = failed_notice(context)
    payload = retry_payload(context, event)
    with django_capture_on_commit_callbacks(execute=True):
        notices.retry_event(context.project.pk, context.admin, event.pk, **payload)
        notices.retry_event(context.project.pk, context.admin, event.pk, **payload)

    assert DeliveryNotificationAttempt.objects.filter(event=event).count() == 2
    assert len(mail.outbox) == 1


def test_retry_rejects_changed_payload_for_an_existing_request(context):
    """Fails if an existing retry identity silently accepts a different reviewed hash."""
    event = failed_notice(context)
    payload = retry_payload(context, event)
    notices.retry_event(context.project.pk, context.admin, event.pk, **payload)
    payload['preview_sha256'] = '0' * 64

    with pytest.raises(DeliveryConflict):
        notices.retry_event(context.project.pk, context.admin, event.pk, **payload)

    assert event.attempts.count() == 2
    assert mail.outbox == []


def test_dispatch_recovers_a_notice_without_its_commit_callback(context):
    """Fails if a worker missed after commit leaves its durable notice pending forever."""
    event = published_notice(context)

    notices.dispatch_pending()
    event.refresh_from_db()

    assert event.status == 'sent'
    assert event.attempts.count() == 1
    assert len(mail.outbox) == 1


@pytest.mark.parametrize(('configured_timeout', 'expected_timeout'), [(None, 20), (5, 5)])
def test_activity_smtp_connection_uses_the_bounded_timeout(configured_timeout, expected_timeout):
    """The SMTP boundary receives a finite timeout without raising a stricter limit."""
    smtp_mailers = {'default': {
        'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
        'OPTIONS': {'host': 'example.invalid', 'port': 25, 'timeout': configured_timeout},
    }}
    with override_settings(MAILERS=smtp_mailers), patch('django.core.mail.backends.smtp.smtplib.SMTP') as transport:
        connection = EmailDeliveryGateway.bounded_connection(timeout_seconds=20)

        opened = connection.open()
        connection.close()

    assert opened is True
    assert transport.call_count == 1
    assert transport.call_args.args == ('example.invalid', 25)
    assert transport.call_args.kwargs['timeout'] == expected_timeout
