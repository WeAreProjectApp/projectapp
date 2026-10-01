"""Closure-email MCP calls retain previews and use durable explicit confirmation."""
import hashlib
from unittest.mock import patch

import pytest
from django.core import mail
from django.db import connection
from rest_framework.test import APIClient

from accounts.models import DeliveryEvidenceEmail, DeliveryEvidenceEmailAttempt
from accounts.services import delivery_workflow as delivery
from accounts.services.tokens import get_tokens_for_user
from content.models import McpActionIntent, McpCredential, McpUpload
from content.tests.views.test_mcp_delivery import (
    call_projects as call_projects, current_version, draft as draft, published as published,
)


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def memory_mail(settings):
    settings.MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
    mail.outbox = []


@pytest.fixture
def approved_project(published, superuser):
    published.client.email = 'closure-client@example.test'
    published.client.save(update_fields=['email'])
    delivery.review_stage(published.project.pk, published.client, published.stage.pk, {
        'expected_version': delivery.overview(published.project.pk, superuser)['version'],
        'request_id': 'closure-client-approval',
        'decisions': [{'requirement_id': published.requirement.pk,
                       'version': published.requirement.version, 'decision': 'approved'}],
    })
    return published


def prepare(call, context, *, request_id='mcp-closure-prepare', **options):
    return call('prepare_delivery_stage_closure_email', {
        'project_id': context.project.pk, 'stage_id': context.stage.pk,
        'expected_version': current_version(call, context.project), 'request_id': request_id,
        **options,
    })


def preparation_arguments(context, preparation):
    return {'project_id': context.project.pk, 'preparation_id': preparation['id']}


def send_arguments(context, preparation, *, request_id='mcp-closure-send', **options):
    return {**preparation_arguments(context, preparation), 'expected_version': preparation['version'],
            'request_id': request_id, 'preview_sha256': preparation['manifest_sha256'],
            'human_reviewed': True, **options}


def send_preview(call, context, preparation, **options):
    return call('send_delivery_stage_closure_email', send_arguments(context, preparation, **options))


def confirm_preview(call, preview):
    return call('confirm_action', {'confirmation_id': preview['confirmation_id']})


def foreign_credential():
    original = McpCredential.objects.get(connector__slug='projects', label='Default')
    other = McpCredential.objects.create(connector=original.connector, actor=original.actor, label='Other closure reader')
    return other.generate_token()


def foreign_call(api_client, token, tool, arguments):
    response = api_client.post(f'/api/mcp/projects/{token}/', {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool, 'arguments': arguments},
    }, format='json')
    assert response.status_code == 200, response.data
    return response.data['result']['structuredContent']


def test_prepare_retains_a_personal_preview(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project, message='Gracias por la validación.')

    retained = DeliveryEvidenceEmail.objects.get()

    assert preparation['to'] == [approved_project.client.email]
    assert preparation['status'] == 'prepared'
    assert retained.mcp_credential.connector.slug == 'projects'
    assert retained.prepared_by_id == retained.mcp_credential.actor_id
    assert mail.outbox == []


def test_read_returns_the_exact_prepared_body(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)

    result = call_projects('get_delivery_stage_closure_email', preparation_arguments(approved_project, preparation))

    assert result['html_body'] == preparation['html_body']
    assert result['manifest_sha256'] == preparation['manifest_sha256']
    assert result['to'] == preparation['to']
    assert mail.outbox == []


def test_history_lists_the_owned_preparation(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)

    history = call_projects('list_delivery_stage_closure_emails', {
        'project_id': approved_project.project.pk, 'stage_id': approved_project.stage.pk,
    })

    assert [item['id'] for item in history['emails']] == [preparation['id']]
    assert history['version'] == preparation['version']
    assert mail.outbox == []


def test_download_returns_the_exact_private_artifact(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project, include_record_pdf=True)
    attachment = preparation['attachments'][0]

    result = call_projects('download_delivery_stage_closure_email_attachment', {
        **preparation_arguments(approved_project, preparation), 'file_id': attachment['id'],
    })
    artifact = McpUpload.objects.get(pk=result['asset_id'])

    assert result['sha256'] == attachment['sha256']
    assert result['content_type'] == 'application/pdf'
    assert hashlib.sha256(artifact.file.read()).hexdigest() == attachment['sha256']
    assert artifact.credential_id == DeliveryEvidenceEmail.objects.get().mcp_credential_id


def test_send_preview_shows_the_frozen_manifest(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project, include_record_pdf=True)

    preview = send_preview(call_projects, approved_project, preparation)

    assert preview['confirmation_required'] is True
    assert preview['impact']['to'] == preparation['to']
    assert preview['impact']['html_body'] == preparation['html_body']
    assert preview['impact']['attachments'] == preparation['attachments']
    assert DeliveryEvidenceEmailAttempt.objects.count() == 0
    assert mail.outbox == []


def test_confirm_commits_the_receipt_before_transport(call_projects, approved_project):
    """The SMTP boundary sees an executed intent and domain claim without an outer atomic."""
    preparation = prepare(call_projects, approved_project)
    preview = send_preview(call_projects, approved_project, preparation)
    observed = {}

    def transport_boundary(*args, **kwargs):
        observed['inside_transaction'] = connection.in_atomic_block
        observed['intent_status'] = McpActionIntent.objects.get().status
        observed['attempt_status'] = DeliveryEvidenceEmailAttempt.objects.get().status
        return 1

    with patch('content.services.email_delivery_service.EmailMessage.send', side_effect=transport_boundary):
        result = confirm_preview(call_projects, preview)

    assert result['confirmed'] is True
    assert result['result']['status'] == 'sent'
    assert observed == {'inside_transaction': False, 'intent_status': 'executed', 'attempt_status': 'sending'}


def test_repeated_confirmation_does_not_send_again(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)
    preview = send_preview(call_projects, approved_project, preparation)
    confirm_preview(call_projects, preview)

    replay = confirm_preview(call_projects, preview)

    assert replay['replayed'] is True
    assert replay['result']['status'] == 'sent'
    assert DeliveryEvidenceEmailAttempt.objects.count() == 1
    assert len(mail.outbox) == 1


def test_second_send_request_returns_the_existing_attempt(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)
    confirm_preview(call_projects, send_preview(call_projects, approved_project, preparation))

    repeated = confirm_preview(call_projects, send_preview(
        call_projects, approved_project, preparation, request_id='second-click',
    ))

    assert repeated['result']['status'] == 'sent'
    assert len(repeated['result']['attempts']) == 1
    assert len(mail.outbox) == 1


def test_resend_only_prepares_new_evidence(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project, include_record_pdf=True)

    resend = call_projects('prepare_delivery_stage_closure_email_resend', {
        **preparation_arguments(approved_project, preparation),
        'expected_version': preparation['version'], 'request_id': 'explicit-resend',
    })

    assert resend['id'] != preparation['id']
    assert resend['manifest_sha256'] == preparation['manifest_sha256']
    assert resend['text_body'] == preparation['text_body']
    assert resend['status'] == 'prepared'
    assert mail.outbox == []


def test_send_rejects_missing_human_review(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)

    error = call_projects('send_delivery_stage_closure_email',
                          send_arguments(approved_project, preparation, human_reviewed=False), expect_error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert McpActionIntent.objects.count() == 0
    assert mail.outbox == []


def test_send_rejects_a_different_preview_hash(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)

    error = call_projects('send_delivery_stage_closure_email',
                          send_arguments(approved_project, preparation, preview_sha256='0' * 64), expect_error=True)

    assert error['code'] == 'CONFLICT'
    assert DeliveryEvidenceEmailAttempt.objects.count() == 0
    assert mail.outbox == []


def test_read_rejects_a_malformed_preparation_id(call_projects, approved_project):
    error = call_projects('get_delivery_stage_closure_email', {
        'project_id': approved_project.project.pk, 'preparation_id': 'invalid-uuid',
    }, expect_error=True)

    assert error['code'] == 'VALIDATION_ERROR'
    assert mail.outbox == []


def test_prepare_rejects_a_stage_still_in_review(call_projects, published):
    published.client.email = 'closure-client@example.test'
    published.client.save(update_fields=['email'])

    error = call_projects('prepare_delivery_stage_closure_email', {
        'project_id': published.project.pk, 'stage_id': published.stage.pk,
        'expected_version': current_version(call_projects, published.project), 'request_id': 'pending-email',
    }, expect_error=True)

    assert error['code'] == 'STAGE_NOT_APPROVED'
    assert DeliveryEvidenceEmail.objects.count() == 0


def test_other_credential_cannot_read_the_preparation(call_projects, approved_project, api_client):
    preparation = prepare(call_projects, approved_project)
    token = foreign_credential()

    result = foreign_call(api_client, token, 'get_delivery_stage_closure_email',
                          preparation_arguments(approved_project, preparation))

    assert result['error']['code'] == 'NOT_FOUND'
    assert mail.outbox == []


def test_other_credential_cannot_download_the_attachment(call_projects, approved_project, api_client):
    preparation = prepare(call_projects, approved_project, include_record_pdf=True)
    token = foreign_credential()

    result = foreign_call(api_client, token, 'download_delivery_stage_closure_email_attachment', {
        **preparation_arguments(approved_project, preparation), 'file_id': preparation['attachments'][0]['id'],
    })

    assert result['error']['code'] == 'NOT_FOUND'
    assert McpUpload.objects.count() == 0


def test_confirmation_rejects_a_new_workspace_version(call_projects, approved_project):
    """A later private discussion invalidates the send intent without sending SMTP."""
    preparation = prepare(call_projects, approved_project)
    preview = send_preview(call_projects, approved_project, preparation)
    call_projects('add_delivery_message', {
        'project_id': approved_project.project.pk, 'level': 'stage', 'target_id': approved_project.stage.pk,
        'expected_version': preparation['version'], 'request_id': 'changed-discussion',
        'message': 'Nota interna posterior a la vista previa.', 'is_internal': True,
    })

    error = call_projects('confirm_action', {'confirmation_id': preview['confirmation_id']}, expect_error=True)

    assert error['code'] == 'STALE_VERSION'
    assert DeliveryEvidenceEmailAttempt.objects.count() == 0
    assert mail.outbox == []


def test_rest_cannot_read_a_credential_owned_preparation(call_projects, approved_project):
    preparation = prepare(call_projects, approved_project)
    principal = DeliveryEvidenceEmail.objects.get().prepared_by
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {get_tokens_for_user(principal)["access"]}')

    response = api.get(f'/api/accounts/projects/{approved_project.project.pk}/delivery/closure-emails/{preparation["id"]}/')

    assert response.status_code == 404
    assert DeliveryEvidenceEmail.objects.count() == 1
