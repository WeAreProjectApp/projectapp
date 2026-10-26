"""Retry chains retain evidence without multiplying actionable incidents."""
from uuid import uuid4

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import EmailBody, EmailDeliverySnapshot, EmailLog
from content.services.dashboard_attention_service import failed_email_incidents
from content.services.email_snapshot_service import resend_email_log

pytestmark = pytest.mark.django_db


def delivery(*, parent=None, status='failed', recipient='client@example.test', **extra):
    snapshot = EmailDeliverySnapshot.objects.create(
        delivery_id=uuid4(), body=EmailBody.objects.create(text='Retained evidence'),
        template_key='document_signed_client', classification='client', family='platform',
        resend_of=parent,
    )
    return EmailLog.objects.create(
        snapshot=snapshot, delivery_id=snapshot.delivery_id, template_key=snapshot.template_key,
        recipient=recipient, subject='Evidence', status=status, **extra,
    )


@freeze_time('2026-10-26 15:00:00')
def test_skipped_retry_cannot_resolve_a_failure():
    original = delivery()
    delivery(parent=original.snapshot, status='skipped')

    incidents = failed_email_incidents(timezone.now())

    assert [row['id'] for row in incidents] == [original.pk]


@freeze_time('2026-10-26 15:00:00')
def test_cc_bounce_surfaces_a_sent_representative():
    original = delivery(status='sent')
    bounce = EmailLog.objects.create(
        snapshot=original.snapshot, delivery_id=original.delivery_id,
        template_key=original.template_key, recipient='cc@example.test',
        recipient_kind='cc', status='bounced',
    )

    incidents = failed_email_incidents(timezone.now())

    assert [row['id'] for row in incidents] == [bounce.pk]


@freeze_time('2026-10-26 15:00:00')
def test_success_resolves_a_chain_started_before_the_window():
    original = delivery()
    EmailLog.objects.filter(pk=original.pk).update(sent_at=timezone.now() - timezone.timedelta(days=10))
    recent = delivery(parent=original.snapshot)
    delivery(parent=recent.snapshot, status='sent')

    incidents = failed_email_incidents(timezone.now())

    assert incidents == []


def test_resend_records_its_origin():
    original = delivery()

    resent = resend_email_log(original, ['client@example.test'])

    assert resent.retry_of_id == original.pk
    assert resent.snapshot.resend_of_id == original.snapshot_id
