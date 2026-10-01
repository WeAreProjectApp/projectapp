"""JWT closure-email routes preserve personal previews and explicit sending."""
import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.db import connection, transaction
from rest_framework.test import APIClient

from accounts.models import DeliveryEvidenceEmail, DeliveryEvidenceEmailAttempt, Project, UserProfile
from accounts.services import delivery_workflow as delivery
from accounts.services.tokens import get_tokens_for_user
from accounts.tests.delivery_helpers import build_delivery_context, decisions, publish, version
from content.models import EmailDeliverySnapshot


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def memory_mail(settings):
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    mail.outbox = []


@pytest.fixture
def context():
    # Keep explicit profiles together with users before on_commit provisioning.
    with transaction.atomic():
        return build_delivery_context()


@pytest.fixture
def approved(context):
    publish(context)
    delivery.review_stage(context.project.pk, context.client, context.stage.pk,
                          decisions(context, (context.first, 'approved'), (context.second, 'approved')))
    return context


def api_for(actor):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(actor)["access"]}')
    return api


def route(context, suffix):
    return f'/api/accounts/projects/{context.project.pk}/delivery/{suffix}'


def prepare(context, *, request_id='api-email-prepare', **options):
    response = api_for(context.admin).post(route(context, f'stages/{context.stage.pk}/closure-email/prepare/'), {
        'expected_version': version(context), 'request_id': request_id, **options,
    }, format='json')
    assert response.status_code == 201, response.data
    return response.data


def send_payload(context, preparation, *, request_id='api-email-send', **options):
    return {'expected_version': version(context), 'request_id': request_id,
            'preview_sha256': preparation['manifest_sha256'], 'human_reviewed': True, **options}


def send(context, preparation, *, request_id='api-email-send', **options):
    return api_for(context.admin).post(route(context, f'closure-emails/{preparation["id"]}/send/'),
                                      send_payload(context, preparation, request_id=request_id, **options), format='json')


def test_prepare_route_retains_the_reviewable_email(approved):
    previous_version = version(approved)

    preparation = prepare(approved, message='Gracias por validar esta etapa.')

    assert preparation['to'] == [approved.client.email]
    assert 'Gracias por validar esta etapa.' in preparation['text_body']
    assert preparation['status'] == 'prepared'
    assert version(approved) == previous_version
    assert mail.outbox == []


def test_prepare_route_rejects_client_tokens(approved):
    api = api_for(approved.client)

    response = api.post(route(approved, f'stages/{approved.stage.pk}/closure-email/prepare/'), {
        'expected_version': version(approved), 'request_id': 'client-prepare',
    }, format='json')

    assert response.status_code == 403
    assert DeliveryEvidenceEmail.objects.count() == 0


def test_prepare_route_rejects_an_unapproved_stage(context):
    response = api_for(context.admin).post(route(context, f'stages/{context.stage.pk}/closure-email/prepare/'), {
        'expected_version': version(context), 'request_id': 'unapproved-prepare',
    }, format='json')

    assert response.status_code == 400
    assert response.data['code'] == 'stage_not_approved'
    assert DeliveryEvidenceEmail.objects.count() == 0


def test_prepare_route_rejects_stale_versions(approved):
    response = api_for(approved.admin).post(route(approved, f'stages/{approved.stage.pk}/closure-email/prepare/'), {
        'expected_version': version(approved) + 1, 'request_id': 'stale-prepare',
    }, format='json')

    assert response.status_code == 409
    assert DeliveryEvidenceEmail.objects.count() == 0


def test_detail_route_returns_the_retained_preview(approved):
    preparation = prepare(approved)

    response = api_for(approved.admin).get(route(approved, f'closure-emails/{preparation["id"]}/'))

    assert response.status_code == 200
    assert response.data['manifest_sha256'] == preparation['manifest_sha256']
    assert response.data['html_body'] == preparation['html_body']
    assert response['Cache-Control'] == 'private, no-store'


def test_history_route_lists_personal_preparations(approved):
    preparation = prepare(approved)

    response = api_for(approved.admin).get(route(approved, f'stages/{approved.stage.pk}/closure-email/history/'))

    assert response.status_code == 200
    assert [item['id'] for item in response.data['emails']] == [preparation['id']]
    assert response.data['version'] == version(approved)
    assert mail.outbox == []


def test_detail_route_rejects_another_project(approved):
    preparation = prepare(approved)
    other = Project.objects.create(name='Otro proyecto', client=approved.client)

    response = api_for(approved.admin).get(
        f'/api/accounts/projects/{other.pk}/delivery/closure-emails/{preparation["id"]}/',
    )

    assert response.status_code == 404
    assert DeliveryEvidenceEmail.objects.count() == 1


def test_detail_route_rejects_another_administrator(approved):
    preparation = prepare(approved)
    other = User.objects.create_user('other-email-admin', 'other@example.test', 'test-password')
    UserProfile.objects.create(user=other, role='admin', is_onboarded=True, email_verified=True)

    response = api_for(other).get(route(approved, f'closure-emails/{preparation["id"]}/'))

    assert response.status_code == 403
    assert mail.outbox == []


def test_attachment_route_downloads_the_exact_record(approved):
    preparation = prepare(approved, include_record_pdf=True)
    attachment = preparation['attachments'][0]

    response = api_for(approved.admin).get(route(
        approved, f'closure-emails/{preparation["id"]}/attachments/{attachment["id"]}/download/',
    ))

    assert response.status_code == 200
    assert hashlib.sha256(response.content).hexdigest() == attachment['sha256']
    assert response['Content-Type'] == 'application/pdf'
    assert response['Cache-Control'] == 'private, no-store'


@pytest.mark.django_db(transaction=True)
def test_send_route_commits_the_claim_before_transport(approved):
    """The SMTP boundary observes a durable receipt outside HTTP history atomic."""
    preparation = prepare(approved)
    observed = {}

    def transport_boundary(*args, **kwargs):
        observed['inside_transaction'] = connection.in_atomic_block
        observed['claim_status'] = DeliveryEvidenceEmailAttempt.objects.get().status
        observed['snapshot_saved'] = EmailDeliverySnapshot.objects.exists()
        return 1

    with patch('content.services.email_delivery_service.EmailMessage.send', side_effect=transport_boundary):
        response = send(approved, preparation)

    assert response.status_code == 200
    assert response.data['status'] == 'sent'
    assert observed == {'inside_transaction': False, 'claim_status': 'sending', 'snapshot_saved': True}


def test_repeated_send_returns_the_existing_attempt(approved):
    preparation = prepare(approved)
    original = send(approved, preparation)

    repeated = send(approved, preparation, request_id='another-button-click')

    assert original.status_code == repeated.status_code == 200
    assert repeated.data['status'] == 'sent'
    assert len(repeated.data['attempts']) == 1
    assert len(mail.outbox) == 1


def test_send_route_requires_human_review(approved):
    preparation = prepare(approved)

    response = send(approved, preparation, human_reviewed=False)

    assert response.status_code == 400
    assert DeliveryEvidenceEmailAttempt.objects.count() == 0
    assert mail.outbox == []


def test_send_route_rejects_body_overwrites(approved):
    preparation = prepare(approved)

    response = send(approved, preparation, text_body='Un cuerpo diferente.')

    assert response.status_code == 400
    assert DeliveryEvidenceEmailAttempt.objects.count() == 0
    assert mail.outbox == []


def test_resend_route_only_prepares_a_new_review(approved):
    preparation = prepare(approved, include_record_pdf=True)

    response = api_for(approved.admin).post(route(approved, f'closure-emails/{preparation["id"]}/resend/prepare/'), {
        'expected_version': version(approved), 'request_id': 'explicit-resend-preview',
    }, format='json')

    assert response.status_code == 201
    assert response.data['id'] != preparation['id']
    assert response.data['manifest_sha256'] == preparation['manifest_sha256']
    assert response.data['status'] == 'prepared'
    assert mail.outbox == []
