"""Tests for the Blog Publisher MCP HTTP endpoint."""
import json
import logging
import pytest

from content.models import BlogPost, McpConnector, McpRequestLog
from content.views.mcp_blog import McpEndpointThrottle


@pytest.fixture
def blog_connector(db):
    connector, _ = McpConnector.objects.get_or_create(
        slug='blog', defaults={'name': 'Blog Publisher'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return connector, token


def _url(token):
    return f'/api/mcp/blog/{token}/'


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _active_connector(slug):
    connector, _ = McpConnector.objects.get_or_create(
        slug=slug, defaults={'name': f'{slug.title()} MCP'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector.generate_token()


VALID_POST = {
    'title_es': 'Post por MCP',
    'title_en': 'Post via MCP',
    'excerpt_es': 'Resumen.',
    'excerpt_en': 'Summary.',
    'content_json_es': {
        'intro': 'Intro.',
        'sections': [{'heading': 'Uno', 'content': 'Texto.'}],
    },
}


@pytest.mark.django_db
class TestMcpEndpointAuth:
    def test_wrong_token_is_404(self, api_client, blog_connector):
        response = api_client.post(_url('bad-token'), _rpc('ping'), format='json')
        assert response.status_code == 404

    def test_inactive_connector_is_404_even_with_valid_token(self, api_client, blog_connector):
        connector, token = blog_connector
        connector.is_active = False
        connector.save(update_fields=['is_active'])
        response = api_client.post(_url(token), _rpc('ping'), format='json')
        assert response.status_code == 404

    def test_get_is_not_allowed(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.get(_url(token))
        assert response.status_code == 405


@pytest.mark.django_db
class TestMcpEndpointThrottle:
    def test_registered_connectors_do_not_consume_each_others_ip_quota(
        self, api_client, monkeypatch,
    ):
        """A busy connector must not make a sibling fail startup with HTTP 429."""
        monkeypatch.setattr(McpEndpointThrottle, 'rate', '2/min', raising=False)
        blog_token = _active_connector('blog')
        documents_token = _active_connector('documents')

        for _ in range(2):
            response = api_client.post(_url(blog_token), _rpc('ping'), format='json')
            assert response.status_code == 200
        assert api_client.post(
            _url(blog_token), _rpc('ping'), format='json',
        ).status_code == 429

        sibling_response = api_client.post(
            f'/api/mcp/documents/{documents_token}/', _rpc('ping'), format='json',
        )
        assert sibling_response.status_code == 200
        assert sibling_response.data['result'] == {}

    def test_unknown_slugs_share_one_quota_bucket(self, api_client, monkeypatch):
        """Inventing endpoint slugs must not bypass the anonymous throttle."""
        monkeypatch.setattr(McpEndpointThrottle, 'rate', '2/min', raising=False)

        for slug in ('made-up-one', 'made-up-two'):
            response = api_client.post(
                f'/api/mcp/{slug}/invalid/', _rpc('ping'), format='json',
            )
            assert response.status_code == 404

        blocked = api_client.post(
            '/api/mcp/made-up-three/invalid/', _rpc('ping'), format='json',
        )
        assert blocked.status_code == 429


@pytest.mark.django_db
class TestMcpEndpointProtocolCompat:
    """Streamable HTTP transport compliance for claude.ai's client probes."""

    def test_get_sse_probe_returns_405_not_406(self, api_client, blog_connector):
        # Spec: GET must get text/event-stream or exactly 405 — DRF's default
        # negotiation used to 406 on an SSE-only Accept header.
        _, token = blog_connector
        response = api_client.get(_url(token), HTTP_ACCEPT='text/event-stream')
        assert response.status_code == 405
        assert 'POST' in response['Allow']

    def test_delete_session_termination_returns_405(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.delete(_url(token))
        assert response.status_code == 405

    def test_head_returns_405(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.head(_url(token))
        assert response.status_code == 405

    def test_post_with_foreign_origin_is_rejected(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(
            _url(token), _rpc('ping'), format='json',
            HTTP_ORIGIN='https://evil.example',
        )
        assert response.status_code == 403

    def test_post_with_same_host_origin_is_accepted(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(
            _url(token), _rpc('ping'), format='json',
            HTTP_ORIGIN='http://testserver',
        )
        assert response.status_code == 200

    def test_post_with_claude_ai_origin_is_accepted(self, api_client, blog_connector):
        # claude.ai's MCP client sends this Origin; rejecting it broke
        # connector creation with "could not connect".
        _, token = blog_connector
        response = api_client.post(
            _url(token), _rpc('ping'), format='json',
            HTTP_ORIGIN='https://claude.ai',
        )
        assert response.status_code == 200

    def test_post_without_trailing_slash_works(self, api_client, blog_connector):
        # Hand-copied connector URLs often lose the trailing slash; without
        # this route the POST fell into the SPA catch-all and got a 403 CSRF.
        _, token = blog_connector
        response = api_client.post(
            f'/api/mcp/blog/{token}',
            _rpc('initialize', {'protocolVersion': '2025-06-18'}),
            format='json',
        )
        assert response.status_code == 200
        assert response.data['result']['serverInfo']['name'] == 'projectapp-blog-mcp'

    @pytest.mark.parametrize('probe_path', [
        '/.well-known/oauth-authorization-server',
        '/.well-known/oauth-protected-resource',
        '/.well-known/openid-configuration',
    ])
    def test_oauth_discovery_probes_return_404(self, api_client, probe_path):
        # The SPA catch-all must not answer these with 200 HTML: claude.ai
        # reads that as "OAuth-protected server" and derails connector setup.
        response = api_client.get(probe_path)
        assert response.status_code == 404


@pytest.mark.django_db
class TestMcpActivityLog:
    def _events(self):
        return list(McpRequestLog.objects.values_list('event', 'ok', 'detail'))

    def test_initialize_records_handshake(self, api_client, blog_connector):
        _, token = blog_connector
        api_client.post(
            _url(token), _rpc('initialize', {'protocolVersion': '2025-06-18'}), format='json',
        )
        assert ('handshake', True, 'initialize OK') in self._events()

    def test_successful_tool_call_records_tool_name(self, api_client, blog_connector):
        _, token = blog_connector
        api_client.post(
            _url(token),
            _rpc('tools/call', {'name': 'get_blog_template', 'arguments': {}}),
            format='json',
        )
        assert ('tool_call', True, 'get_blog_template') in self._events()

    def test_failed_tool_call_records_error_detail(self, api_client, blog_connector):
        _, token = blog_connector
        api_client.post(
            _url(token),
            _rpc('tools/call', {'name': 'create_blog_post', 'arguments': {'title_es': 'x'}}),
            format='json',
        )
        events = self._events()
        failed = [e for e in events if e[0] == 'tool_call' and e[1] is False]
        assert failed and 'create_blog_post' in failed[0][2]

    def test_bad_token_records_auth_error(self, api_client, blog_connector):
        api_client.post(_url('bad-token'), _rpc('ping'), format='json')
        events = self._events()
        assert any(e[0] == 'auth_error' and 'Token inválido' in e[2] for e in events)

    def test_inactive_connector_records_specific_detail(self, api_client, blog_connector):
        connector, token = blog_connector
        connector.is_active = False
        connector.save(update_fields=['is_active'])
        api_client.post(_url(token), _rpc('ping'), format='json')
        assert any(e[0] == 'auth_error' and 'inactivo' in e[2] for e in self._events())

    def test_foreign_origin_records_rejected_origin(self, api_client, blog_connector):
        _, token = blog_connector
        api_client.post(
            _url(token), _rpc('ping'), format='json', HTTP_ORIGIN='https://evil.example',
        )
        assert ('origin_rejected', False, 'origin_rejected') in self._events()

    def test_trail_is_pruned_to_keep_limit(self, blog_connector):
        connector, _ = blog_connector
        for i in range(McpRequestLog.KEEP_PER_CONNECTOR + 7):
            McpRequestLog.record(connector, 'handshake', detail=f'n{i}')
        assert McpRequestLog.objects.filter(connector=connector).count() == McpRequestLog.KEEP_PER_CONNECTOR

    def test_panel_payload_exposes_status_and_events(self, superuser_client, blog_connector):
        connector, token = blog_connector
        McpRequestLog.record(connector, 'handshake', detail='initialize OK')
        response = superuser_client.get('/api/mcp-connectors/')
        blog = next(c for c in response.data if c['slug'] == 'blog')
        assert blog['connection_status'] == 'connected'
        assert blog['recent_events'][0]['event'] == 'handshake'

    def test_panel_payload_error_status_when_last_event_failed(self, superuser_client, blog_connector):
        connector, _ = blog_connector
        McpRequestLog.record(connector, 'handshake', detail='initialize OK')
        McpRequestLog.record(connector, 'origin_rejected', ok=False, detail='https://evil.example')
        response = superuser_client.get('/api/mcp-connectors/')
        blog = next(c for c in response.data if c['slug'] == 'blog')
        assert blog['connection_status'] == 'error'

    def test_panel_payload_none_status_without_events(self, superuser_client, blog_connector):
        response = superuser_client.get('/api/mcp-connectors/')
        blog = next(c for c in response.data if c['slug'] == 'blog')
        assert blog['connection_status'] == 'none'
        assert blog['recent_events'] == []


@pytest.mark.django_db
class TestMcpEndpointFlow:
    def test_initialize_handshake(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(
            _url(token),
            _rpc('initialize', {'protocolVersion': '2025-06-18'}),
            format='json',
        )
        assert response.status_code == 200
        assert response.data['result']['serverInfo']['name'] == 'projectapp-blog-mcp'

    def test_initialized_notification_returns_202(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(
            _url(token),
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            format='json',
        )
        assert response.status_code == 202

    def test_tools_list_exposes_seven_tools(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(_url(token), _rpc('tools/list'), format='json')
        names = [t['name'] for t in response.data['result']['tools']]
        assert names == [
            'get_blog_template', 'create_blog_post', 'update_blog_post',
            'delete_blog_post', 'list_blog_posts', 'get_blog_post',
            'get_blog_calendar',
        ]

    def test_tools_call_creates_post_and_touches_last_used(self, api_client, blog_connector):
        connector, token = blog_connector
        assert connector.last_used_at is None
        response = api_client.post(
            _url(token),
            _rpc('tools/call', {'name': 'create_blog_post', 'arguments': VALID_POST}),
            format='json',
        )
        assert response.status_code == 200
        assert response.data['result']['isError'] is False
        assert BlogPost.objects.filter(title_es='Post por MCP').exists()
        connector.refresh_from_db()
        assert connector.last_used_at is not None

    def test_validation_error_is_readable_tool_error(self, api_client, blog_connector):
        _, token = blog_connector
        response = api_client.post(
            _url(token),
            _rpc('tools/call', {'name': 'create_blog_post', 'arguments': {'title_es': 'x'}}),
            format='json',
        )
        assert response.status_code == 200
        assert response.data['result']['isError'] is True
        assert 'title_en' in response.data['result']['content'][0]['text']

    def test_failed_tool_call_keeps_only_declared_reference_in_audit(
        self, api_client, blog_connector, blog_post, caplog,
    ):
        """Fails if an undeclared tool argument reaches MCP logs or its audit row."""
        _, token = blog_connector
        marker = 'SYNTHETIC_PRIVATE_P5_20261001'
        with caplog.at_level(logging.INFO, logger='content.mcp.protocol'):
            response = api_client.post(
                _url(token),
                _rpc('tools/call', {
                    'name': 'delete_blog_post',
                    'arguments': {'post_id': blog_post.pk, 'private_id': marker},
                }),
                format='json',
            )

        result = response.data['result']
        error = result['structuredContent']['error']
        audit = McpRequestLog.objects.get(event='tool_call')
        serialized_response = json.dumps(response.data, ensure_ascii=False)
        assert response.status_code == 200
        assert error == {
            'code': 'VALIDATION_ERROR',
            'message': 'Este post está publicado. Despublícalo primero con update_blog_post (is_published=false) o elimínalo desde el panel.',
            'details': {},
        }
        assert marker not in f'{serialized_response}{caplog.text}'
        assert {
            'object_refs': audit.object_refs,
            'detail': audit.detail,
            'error_code': audit.error_code,
            'request_id': audit.request_id,
            'has_duration': audit.duration_ms >= 0,
        } == {
            'object_refs': [{'field': 'post_id', 'value': blog_post.pk}],
            'detail': 'delete_blog_post: VALIDATION_ERROR',
            'error_code': 'VALIDATION_ERROR',
            'request_id': result['_meta']['requestId'],
            'has_duration': True,
        }


@pytest.fixture
def superuser_client(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='root_test', password='x', is_staff=True, is_superuser=True,
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestMcpConnectorPanelEndpoints:
    def test_staff_non_superuser_gets_403(self, admin_client):
        assert admin_client.get('/api/mcp-connectors/').status_code == 403
        assert admin_client.post('/api/mcp-connectors/blog/generate-token/').status_code == 403

    def test_list_includes_blog_connector_with_tools(self, superuser_client):
        response = superuser_client.get('/api/mcp-connectors/')
        assert response.status_code == 200
        blog = next(c for c in response.data if c['slug'] == 'blog')
        assert blog['is_active'] is False
        assert blog['has_token'] is False
        tool_names = [t['name'] for t in blog['tools']]
        assert 'create_blog_post' in tool_names

    def test_generate_token_returns_full_url_once(self, superuser_client):
        response = superuser_client.post('/api/mcp-connectors/blog/generate-token/')
        assert response.status_code == 200
        url = response.data['connector_url']
        # Host comes from the request (staging/local instances must hand out
        # URLs pointing at themselves, not at production).
        assert '/api/mcp/blog/' in url
        assert url.startswith('http://testserver/')
        token = url.rstrip('/').rsplit('/', 1)[-1]
        connector = McpConnector.objects.get(slug='blog')
        assert connector.check_token(token) is True
        assert response.data['token_prefix'] == token[:8]

    def test_toggle_is_active(self, superuser_client):
        response = superuser_client.patch(
            '/api/mcp-connectors/blog/', {'is_active': True}, format='json',
        )
        assert response.status_code == 200
        assert McpConnector.objects.get(slug='blog').is_active is True

    def test_toggle_accepts_string_false(self, superuser_client):
        connector = McpConnector.objects.get(slug='blog')
        connector.is_active = True
        connector.save(update_fields=['is_active'])
        response = superuser_client.patch(
            '/api/mcp-connectors/blog/', {'is_active': 'false'}, format='json',
        )
        assert response.status_code == 200
        assert McpConnector.objects.get(slug='blog').is_active is False

    def test_toggle_rejects_invalid_boolean(self, superuser_client):
        response = superuser_client.patch(
            '/api/mcp-connectors/blog/', {'is_active': 'quizás'}, format='json',
        )
        assert response.status_code == 400

    def test_unknown_slug_is_404(self, superuser_client):
        assert superuser_client.patch(
            '/api/mcp-connectors/nope/', {'is_active': True}, format='json',
        ).status_code == 404
