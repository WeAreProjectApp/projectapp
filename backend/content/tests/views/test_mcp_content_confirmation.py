"""Confirmation boundaries for content writes that can publish or schedule."""
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import (
    BlogPost,
    LinkedInPost,
    McpActionIntent,
    McpConnector,
    McpCredential,
    McpObservation,
)


pytestmark = pytest.mark.django_db


def _rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _content(response):
    return json.loads(response.data['result']['content'][0]['text'])


def _call(api_client, token, name, arguments):
    return api_client.post(
        f'/api/mcp/content/{token}/',
        _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _credential(connector, token, tool_name):
    return McpCredential.objects.create(
        connector=connector,
        label=f'{tool_name} confirmation',
        catalog='canonical',
        token_hash=McpCredential.hash_token(token),
        token_prefix=token[:8],
        allowed_tools=[tool_name],
    )


@pytest.fixture
def content_connector():
    connector, _ = McpConnector.objects.update_or_create(
        slug='content',
        defaults={'name': 'Contenido', 'is_active': True, 'retired_at': None, 'aliases_retired_at': None},
    )
    connector.credentials.all().delete()
    return connector


def test_public_blog_create_has_no_domain_write_before_confirmation(
    api_client, content_connector,
):
    """Fails if a public blog post is saved before its sensitive preview is confirmed."""
    token = 'blog-public-confirmation'
    _credential(content_connector, token, 'create_blog_post')
    arguments = {
        'title_es': 'Publicación confirmada',
        'title_en': 'Confirmed publication',
        'excerpt_es': 'Resumen público.',
        'excerpt_en': 'Public summary.',
        'content_json_es': {
            'intro': 'Introducción.',
            'sections': [{'heading': 'Sección', 'content': 'Contenido.'}],
        },
        'is_published': True,
    }

    with patch('content.services.blog_service.schedule_rebuild_after_publish') as rebuild:
        preview = _content(_call(api_client, token, 'create_blog_post', arguments))

        assert preview['confirmation_required'] is True
        assert BlogPost.objects.count() == 0
        rebuild.assert_not_called()

        confirmed = _content(_call(
            api_client, token, 'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        ))

    post = BlogPost.objects.get(pk=confirmed['result']['id'])
    assert post.is_published is True
    rebuild.assert_called_once_with(reason='blog')


@freeze_time('2026-10-19 12:00:00')
def test_scheduled_linkedin_create_has_no_domain_write_before_confirmation(
    api_client, content_connector,
):
    """Fails if a scheduled LinkedIn post writes or enqueues Huey before confirmation."""
    token = 'linkedin-scheduled-confirmation'
    _credential(content_connector, token, 'create_post')
    scheduled_at = (timezone.now() + timedelta(days=1)).isoformat()

    with patch('content.services.linkedin_post_service.schedule_linkedin_post_eta') as enqueue:
        preview = _content(_call(api_client, token, 'create_post', {
            'commentary': 'Post programado que necesita confirmación.',
            'scheduled_at': scheduled_at,
        }))

        assert preview['confirmation_required'] is True
        assert LinkedInPost.objects.count() == 0
        enqueue.assert_not_called()

        confirmed = _content(_call(
            api_client, token, 'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        ))

    post = LinkedInPost.objects.get(pk=confirmed['result']['id'])
    assert post.status == LinkedInPost.STATUS_SCHEDULED
    enqueue.assert_called_once_with(post)


@freeze_time('2026-10-19 12:00:00')
def test_failed_linkedin_publish_is_durable_across_confirmation_replay(
    api_client, content_connector,
):
    """Fails if a replayed confirmation retries a LinkedIn provider failure."""
    token = 'linkedin-publish-durable'
    _credential(content_connector, token, 'publish_post')
    post = LinkedInPost.objects.create(commentary='Publicación que falla')

    preview = _content(_call(api_client, token, 'publish_post', {'post_id': post.pk}))
    with patch(
        'content.services.linkedin_post_service.publish_post_to_linkedin',
        return_value={'success': False, 'post_id': '', 'message': 'provider unavailable'},
    ) as provider:
        failed = _content(_call(
            api_client, token, 'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        ))
        replayed = _content(_call(
            api_client, token, 'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        ))

    post.refresh_from_db()
    assert failed['error']['code'] == 'VALIDATION_ERROR'
    assert post.status == LinkedInPost.STATUS_FAILED
    assert replayed['replayed'] is True
    provider.assert_called_once()


@freeze_time('2026-10-19 12:00:00')
@pytest.mark.parametrize(
    ('body', 'request_kwargs'),
    [
        (_rpc('tools/call', {'name': 'create_post', 'arguments': {'commentary': 'no dispatch'}}), {'format': 'json'}),
        ('{"jsonrpc":', {'content_type': 'application/json'}),
    ],
)
def test_audit_failure_blocks_dispatch_and_restarts_observation(
    api_client, content_connector, body, request_kwargs,
):
    """Fails if unavailable usage evidence dispatches an MCP request or preserves quiet time."""
    token = 'audit-failure-token'
    _credential(content_connector, token, 'create_post')
    earlier = timezone.now() - timedelta(days=3)
    observation = McpObservation.objects.create(
        key='migration', continuous_since=earlier, heartbeat_at=earlier,
    )

    with patch('content.mcp.migration.record_usage', side_effect=RuntimeError('audit unavailable')):
        response = api_client.post(f'/api/mcp/content/{token}/', body, **request_kwargs)

    observation.refresh_from_db()
    assert response.status_code == 503
    assert response.data['error']['code'] == 'MCP_AUDIT_UNAVAILABLE'
    assert observation.continuous_since == timezone.now()
    assert LinkedInPost.objects.count() == 0
    assert McpActionIntent.objects.count() == 0
