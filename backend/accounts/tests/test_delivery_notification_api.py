"""JWT notice history and reviewed retry preserve authorization boundaries."""
import pytest
from django.core import mail
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from accounts.models import Project
from accounts.models_delivery_notifications import DeliveryNotificationAttempt
from accounts.services import delivery_notifications as notices
from accounts.services.tokens import get_tokens_for_user
from accounts.tests.delivery_helpers import RECORDED_AT, build_delivery_context
from accounts.tests.delivery_notification_helpers import (
    create_credential,
    failed_notice,
    retry_payload,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory_mail(settings):
    """Configure only in-memory email for the focused HTTP checks."""
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    settings.NOTIFICATION_EMAIL = 'team@example.test'
    settings.NOTIFICATION_EMAILS = []
    mail.outbox = []


@pytest.fixture
def context():
    """Create the real domain without executing provisioning callbacks."""
    with transaction.atomic():
        return build_delivery_context()


def api_for(actor):
    """Authenticate through the project's genuine JWT boundary."""
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(actor)["access"]}')
    return api


def route(context, suffix=''):
    """Locate a notice action inside its explicit project."""
    return f'/api/accounts/projects/{context.project.pk}/delivery/notices/{suffix}'


def test_anonymous_notice_history_requires_authentication(context):
    """Fails if anonymous callers can read administrative delivery history."""
    response = APIClient().get(route(context))

    assert response.status_code == 401


def test_client_token_cannot_read_administrative_notices(context):
    """Fails if the client receives team email recipients or retry actions."""
    response = api_for(context.client).get(route(context))

    assert response.status_code == 403


def test_admin_history_returns_the_exact_retained_body(context):
    """Fails if reading history substitutes the current project for its captured notice."""
    event = failed_notice(context)
    context.project.name = 'Nombre cambiado después del aviso'
    context.project.save(update_fields=['name'])

    response = api_for(context.admin).get(route(context))

    assert response.status_code == 200
    assert response.data['count'] == 1
    assert response.data['results'][0]['text_body'] == event.text_body
    assert response.data['results'][0]['recipients'] == [context.client.email]


def test_notice_detail_rejects_a_different_project(context):
    """Fails if a notice UUID can be read through another project's URL."""
    event = failed_notice(context)
    other = Project.objects.create(name='Otro proyecto', client=context.client)

    response = api_for(context.admin).get(
        f'/api/accounts/projects/{other.pk}/delivery/notices/{event.pk}/',
    )

    assert response.status_code == 404


@pytest.mark.parametrize('query', [{'page': -1}, {'page': 'invalid'}, {'status': 'invented'}])
def test_history_rejects_invalid_filters(context, query):
    """Fails if malformed history filters become a server error or expose another page."""
    response = api_for(context.admin).get(route(context), query)

    assert response.status_code == 400


@pytest.mark.parametrize(('field', 'value'), [('expected_version', 99), ('preview_sha256', '0' * 64)])
def test_retry_rejects_an_outdated_reviewed_copy(context, field, value, django_capture_on_commit_callbacks):
    """Fails if a stale version or changed reviewed hash can send a retry."""
    event = failed_notice(context)
    payload = retry_payload(context, event, **{field: value})

    with django_capture_on_commit_callbacks(execute=True):
        response = api_for(context.admin).post(route(context, f'{event.pk}/retry/'), payload, format='json')

    assert response.status_code == 409
    assert DeliveryNotificationAttempt.objects.filter(event=event).count() == 1
    assert mail.outbox == []


def test_retry_preview_is_read_only(context):
    """Fails if opening a retry preview starts the transport without confirmation."""
    event = failed_notice(context)

    response = api_for(context.admin).get(
        route(context, f'{event.pk}/retry-preview/'), {'expected_version': event.version},
    )

    assert response.status_code == 200
    assert response.data['text_body'] == event.text_body
    assert len(response.data['preview_sha256']) == 64
    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_client_token_cannot_retry_a_notice(context, django_capture_on_commit_callbacks):
    """Fails if the project owner can trigger an administrator's email retry."""
    event = failed_notice(context)
    payload = retry_payload(context, event)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_for(context.client).post(route(context, f'{event.pk}/retry/'), payload, format='json')

    assert response.status_code == 403
    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_retry_token_cannot_cross_projects(context, django_capture_on_commit_callbacks):
    """Fails if a reviewed retry is accepted under another project's URL."""
    event = failed_notice(context)
    other = Project.objects.create(name='Otro destino', client=context.client)
    payload = retry_payload(context, event)

    with django_capture_on_commit_callbacks(execute=True):
        response = api_for(context.admin).post(
            f'/api/accounts/projects/{other.pk}/delivery/notices/{event.pk}/retry/', payload, format='json',
        )

    assert response.status_code == 404
    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_unknown_notice_cannot_prepare_a_retry(context):
    """Fails if an uncertain SMTP result can be resent through the preview route."""
    event = failed_notice(context)
    event.status = 'unknown'
    event.save(update_fields=['status'])

    response = api_for(context.admin).get(
        route(context, f'{event.pk}/retry-preview/'), {'expected_version': event.version},
    )

    assert response.status_code == 400
    assert response.data['code'] == 'notice_not_retryable'
    assert event.attempts.count() == 1


def test_retry_refuses_a_changed_client_address(context, django_capture_on_commit_callbacks):
    """Fails if retry silently substitutes a recipient changed after the original notice."""
    event = failed_notice(context)
    payload = retry_payload(context, event)
    context.client.email = 'changed@example.test'
    context.client.save(update_fields=['email'])

    with django_capture_on_commit_callbacks(execute=True):
        response = api_for(context.admin).post(route(context, f'{event.pk}/retry/'), payload, format='json')

    assert response.status_code == 409
    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_retry_refuses_a_revoked_mcp_credential(context):
    """Fails if a revoked credential may enqueue a reviewed administrative retry."""
    event = failed_notice(context)
    credential = create_credential(context.admin)
    credential.revoked_at = RECORDED_AT
    credential.save(update_fields=['revoked_at'])
    payload = retry_payload(context, event)

    with pytest.raises(PermissionDenied):
        notices.retry_event(context.project.pk, context.admin, event.pk, credential=credential, **payload)

    assert event.attempts.count() == 1
    assert mail.outbox == []


def test_retry_claim_cancels_a_later_revoked_credential(context):
    """Fails if worker send ignores a credential revoked after retry confirmation."""
    event = failed_notice(context)
    credential = create_credential(context.admin)
    payload = retry_payload(context, event)
    notices.retry_event(context.project.pk, context.admin, event.pk, credential=credential, **payload)
    credential.revoked_at = RECORDED_AT
    credential.save(update_fields=['revoked_at'])
    attempt = event.attempts.get(request_id='manual-notice-retry')

    result = notices.send_attempt(attempt.pk)
    attempt.refresh_from_db()

    assert result is False
    assert attempt.status == 'cancelled'
    assert attempt.error_code == 'recipient_or_credential_changed'
    assert mail.outbox == []
