"""MCP notice retry uses the real retained event and credential-owned confirmation."""
import pytest
from accounts.models import Project
from accounts.models_delivery_notifications import DeliveryNotificationEvent
from accounts.tests.delivery_helpers import build_delivery_context
from accounts.tests.delivery_notification_helpers import failed_notice
from django.core import mail

from content.models import McpActionIntent, McpConnector
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects,  # noqa: PLC0414
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def notice_context(settings):
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    settings.NOTIFICATION_EMAIL = 'team@example.test'
    settings.NOTIFICATION_EMAILS = []
    mail.outbox = []
    return build_delivery_context()


@pytest.fixture
def event(notice_context):
    return failed_notice(notice_context)


def retry_arguments(call_projects, notice_context, event):
    preview = call_projects('preview_delivery_notification_retry', {
        'project_id': notice_context.project.pk, 'event_id': str(event.pk), 'expected_version': event.version})
    return {'project_id': notice_context.project.pk, 'event_id': str(event.pk),
            'expected_version': event.version, 'request_id': 'mcp-notice-retry',
            'preview_sha256': preview['preview_sha256']}


def test_notice_preview_preserves_the_existing_attempt(call_projects, notice_context, event):
    preview = call_projects('retry_delivery_notification_event', retry_arguments(call_projects, notice_context, event))
    assert preview['confirmation_required'] is True
    assert preview['impact']['text_body'] == event.text_body
    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_notice_confirmation_records_the_credential_owner(call_projects, notice_context, event):
    preview = call_projects('retry_delivery_notification_event', retry_arguments(call_projects, notice_context, event))
    call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']})
    attempt = event.attempts.get(request_id='mcp-notice-retry')
    credential = McpConnector.objects.get(slug='projects').credentials.get(label='Default')
    assert attempt.credential_id == credential.pk
    assert attempt.requested_by_id == credential.actor_id


def test_notice_confirmation_replay_preserves_one_retry(call_projects, notice_context, event):
    preview = call_projects('retry_delivery_notification_event', retry_arguments(call_projects, notice_context, event))
    payload = {'confirmation_id': preview['confirmation_id']}
    call_projects('confirm_action', payload)
    second = call_projects('confirm_action', payload)
    assert second['replayed'] is True
    assert event.attempts.filter(request_id='mcp-notice-retry').count() == 1


def test_notice_confirmation_rejects_a_changed_copy(call_projects, notice_context, event):
    preview = call_projects('retry_delivery_notification_event', retry_arguments(call_projects, notice_context, event))
    event.text_body = 'Changed after preview'
    event.save(update_fields=['text_body'])
    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)
    assert error['code'] == 'STALE_VERSION'
    assert event.attempts.count() == 1


def test_notice_preview_rejects_an_unknown_delivery(call_projects, notice_context, event):
    event.status = DeliveryNotificationEvent.Status.UNKNOWN
    event.save(update_fields=['status'])
    error = call_projects('preview_delivery_notification_retry', {
        'project_id': notice_context.project.pk, 'event_id': str(event.pk),
        'expected_version': event.version}, expect_error=True)
    assert error['code'] == 'NOTICE_NOT_RETRYABLE'
    assert not McpActionIntent.objects.filter(tool_name='retry_delivery_notification_event').exists()


def test_notice_detail_rejects_a_foreign_project(call_projects, notice_context, event):
    other = Project.objects.create(name='Otro', client=notice_context.client)
    error = call_projects('get_delivery_notification_event', {
        'project_id': other.pk, 'event_id': str(event.pk)}, expect_error=True)
    assert error['code'] == 'NOT_FOUND'


def test_notice_detail_rejects_an_invalid_identifier(call_projects, notice_context):
    error = call_projects('get_delivery_notification_event', {
        'project_id': notice_context.project.pk, 'event_id': 'invalid'}, expect_error=True)
    assert error['code'] == 'VALIDATION_ERROR'
