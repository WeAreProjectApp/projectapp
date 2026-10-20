"""Tests for the LinkedIn Personal Content MCP connector HTTP endpoint.

LinkedIn API calls and Huey scheduling are mocked at the service layer —
no real LinkedIn requests are made and no tasks are enqueued.
"""
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from freezegun import freeze_time

from content.models import LinkedInPost, McpConnector
from content.tests.mcp_confirmation_helpers import call_confirmed, confirmed_payload

PUBLISH_SVC = 'content.services.linkedin_post_service.publish_post_to_linkedin'
ETA_SVC = 'content.services.linkedin_post_service.schedule_linkedin_post_eta'
STATUS_SVC = 'content.mcp.linkedin_tools.get_connection_status'


@pytest.fixture
def linkedin_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='linkedin-personal', defaults={'name': 'LinkedIn Personal Content'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


def _url(token):
    return f'/api/mcp/linkedin-personal/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _call(api_client, token, name, arguments):
    return api_client.post(
        _url(token), _rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def _call_confirmed(api_client, token, name, arguments):
    return call_confirmed(api_client, _url(token), _rpc, name, arguments)


def _content(response):
    """First structured content block of a tools/call result."""
    return confirmed_payload(response)


@pytest.mark.django_db
class TestLinkedInMcpTools:
    def test_tool_list_includes_core_tools(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        for expected in (
            'get_connection_status', 'list_posts', 'get_post', 'create_post',
            'update_post', 'delete_post', 'publish_post',
        ):
            assert expected in names

    def test_create_draft_and_list(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        created = _call_confirmed(api_client, token, 'create_post', {'commentary': 'Hola LinkedIn'})
        assert created.data['result']['isError'] is False
        assert _content(created)['status'] == 'draft'

        listed = _call(api_client, token, 'list_posts', {})
        payload = _content(listed)
        assert payload['count'] == 1
        assert payload['posts'][0]['status'] == 'draft'

    @freeze_time('2026-01-15 12:00:00')
    @patch(ETA_SVC)
    def test_create_scheduled_enqueues_eta(self, mock_eta, api_client, linkedin_connector):
        _, token = linkedin_connector
        eta = (timezone.now() + timedelta(hours=2)).isoformat()
        created = _call_confirmed(
            api_client, token, 'create_post',
            {'commentary': 'Programado', 'scheduled_at': eta},
        )
        assert created.data['result']['isError'] is False
        assert _content(created)['status'] == 'scheduled'
        mock_eta.assert_called_once()

    @freeze_time('2026-01-15 12:00:00')
    def test_create_with_past_schedule_is_error(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        eta = (timezone.now() - timedelta(hours=1)).isoformat()
        created = _call_confirmed(
            api_client, token, 'create_post',
            {'commentary': 'Tarde', 'scheduled_at': eta},
        )
        assert created.data['result']['isError'] is True

    def test_update_published_post_is_error(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        post = LinkedInPost.objects.create(
            commentary='ya salió', status=LinkedInPost.STATUS_PUBLISHED,
        )
        updated = _call_confirmed(
            api_client, token, 'update_post',
            {'post_id': post.id, 'commentary': 'edit'},
        )
        assert updated.data['result']['isError'] is True

    @patch(PUBLISH_SVC, return_value={'success': True, 'post_id': 'urn:li:share:9', 'message': 'ok'})
    def test_publish_post_success(self, mock_pub, api_client, linkedin_connector):
        _, token = linkedin_connector
        post = LinkedInPost.objects.create(commentary='Publícame')
        published = _call_confirmed(api_client, token, 'publish_post', {'post_id': post.id})
        assert published.data['result']['isError'] is False
        payload = _content(published)
        assert payload['status'] == 'published'
        assert payload['public_url'].endswith('urn:li:share:9/')

    @patch(PUBLISH_SVC, return_value={'success': False, 'post_id': '', 'message': 'LinkedIn API error (500): boom'})
    def test_publish_post_failure_is_error_and_persists(self, mock_pub, api_client, linkedin_connector):
        _, token = linkedin_connector
        post = LinkedInPost.objects.create(commentary='Falla')
        published = _call_confirmed(api_client, token, 'publish_post', {'post_id': post.id})
        assert published.data['result']['isError'] is True
        post.refresh_from_db()
        assert post.status == LinkedInPost.STATUS_FAILED
        assert 'boom' in post.error_message

    @patch(PUBLISH_SVC, return_value={
        'success': False, 'post_id': '', 'message': 'LinkedIn API error (500): boom',
    })
    def test_publish_failure_replay_keeps_failed_post_without_second_provider_call(
        self, mock_pub, api_client, linkedin_connector,
    ):
        """Fails if replaying a failed confirmed publication contacts LinkedIn again."""
        _, token = linkedin_connector
        post = LinkedInPost.objects.create(commentary='No duplicar')

        preview = _call(api_client, token, 'publish_post', {'post_id': post.id})
        confirmation_id = preview.data['result']['structuredContent']['confirmation_id']
        failed = _call(api_client, token, 'confirm_action', {
            'confirmation_id': confirmation_id,
        })
        replay = _call(api_client, token, 'confirm_action', {
            'confirmation_id': confirmation_id,
        })

        post.refresh_from_db()
        assert failed.data['result']['isError'] is True
        assert replay.data['result']['isError'] is False
        replay_envelope = json.loads(replay.data['result']['content'][0]['text'])
        assert replay_envelope['replayed'] is True
        assert replay_envelope['result']['status'] == 'rejected'
        assert post.status == LinkedInPost.STATUS_FAILED
        assert post.error_message == 'LinkedIn API error (500): boom'
        assert mock_pub.call_count == 1

    def test_delete_post(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        post = LinkedInPost.objects.create(commentary='bye')
        deleted = _call_confirmed(api_client, token, 'delete_post', {'post_id': post.id})
        assert deleted.data['result']['isError'] is False
        assert _content(deleted)['deleted'] is True
        assert not LinkedInPost.objects.filter(pk=post.id).exists()

    @freeze_time('2026-01-15 12:00:00')
    @patch(STATUS_SVC, return_value={
        'connected': True, 'profile_name': 'Gustavo',
        'expires_at': '2026-01-18T12:00:00+00:00',
    })
    def test_connection_status_warns_near_expiry(self, mock_status, api_client, linkedin_connector):
        _, token = linkedin_connector
        response = _call(api_client, token, 'get_connection_status', {})
        payload = _content(response)
        assert payload['connected'] is True
        assert 'expira' in payload['warning']

    def test_wrong_token_is_404(self, api_client, linkedin_connector):
        response = api_client.post(
            _url('not-the-token'), _rpc('tools/list'), format='json',
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestLinkedInMcpHandlerBranches:
    def test_get_post_returns_detail(self, api_client, linkedin_connector):
        post = LinkedInPost.objects.create(commentary='Visible')
        _, token = linkedin_connector
        response = _call(api_client, token, 'get_post', {'post_id': post.id})
        assert _content(response)['commentary'] == 'Visible'

    def test_get_unknown_post_errors(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        response = _call(api_client, token, 'get_post', {'post_id': 999999})
        assert response.data['result']['isError'] is True

    @patch(
        'content.mcp.linkedin_tools.get_connection_status',
        return_value={'connected': False},
    )
    def test_connection_status_warns_when_disconnected(
        self, _mock_status, api_client, linkedin_connector,  # noqa: PT019
    ):
        _, token = linkedin_connector
        response = _call(api_client, token, 'get_connection_status', {})
        payload = _content(response)
        assert payload['connected'] is False
        assert 'no está conectado' in payload['warning']

    def test_list_posts_invalid_status_errors(self, api_client, linkedin_connector):
        _, token = linkedin_connector
        response = _call(api_client, token, 'list_posts', {'status': 'limbo'})
        assert response.data['result']['isError'] is True

    def test_list_posts_filters_by_status(self, api_client, linkedin_connector):
        LinkedInPost.objects.create(commentary='Borrador')
        LinkedInPost.objects.create(
            commentary='Publicado', status=LinkedInPost.STATUS_PUBLISHED,
        )
        _, token = linkedin_connector
        response = _call(api_client, token, 'list_posts', {'status': 'published'})
        assert _content(response)['count'] == 1

    def test_update_without_fields_errors(self, api_client, linkedin_connector):
        post = LinkedInPost.objects.create(commentary='Quieto')
        _, token = linkedin_connector
        response = _call_confirmed(api_client, token, 'update_post', {'post_id': post.id})
        result = response.data['result']
        assert result['isError'] is True
        assert 'Nada que actualizar' in result['content'][0]['text']

    def test_update_draft_commentary(self, api_client, linkedin_connector):
        post = LinkedInPost.objects.create(commentary='Antes')
        _, token = linkedin_connector
        response = _call_confirmed(api_client, token, 'update_post', {
            'post_id': post.id, 'commentary': 'Después',
        })
        assert response.data['result']['isError'] is False
        post.refresh_from_db()
        assert post.commentary == 'Después'

    def test_delete_post_removes_local_record(self, api_client, linkedin_connector):
        post = LinkedInPost.objects.create(commentary='Borrable')
        _, token = linkedin_connector
        response = _call_confirmed(api_client, token, 'delete_post', {'post_id': post.id})
        payload = _content(response)
        assert payload['deleted'] is True
        assert 'nada cambió en LinkedIn' in payload['note']
        assert not LinkedInPost.objects.filter(pk=post.pk).exists()
