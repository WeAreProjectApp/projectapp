"""Regression tests: text fields must reach the DB as real UTF-8.

Some MCP clients double-escape non-ASCII characters, so the argument
string contains the literal characters ``\\u00e9`` instead of ``é``.
The serializers must decode those literal escape sequences defensively.
"""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from content.models import BlogPost, McpConnector


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


def _call(name, arguments):
    return {
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': name, 'arguments': arguments},
    }


def _confirm(api_client, token, preview):
    confirmation_id = preview.json()['result']['structuredContent']['confirmation_id']
    return api_client.post(
        _url(token),
        _call('confirm_action', {'confirmation_id': confirmation_id}),
        format='json',
    )


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
class TestMcpBlogUtf8:
    def test_create_stores_real_utf8(self, api_client, blog_connector):
        _, token = blog_connector
        args = {
            **VALID_POST,
            'linkedin_summary_en': 'Café → Result',
            'linkedin_summary_es': 'Así se ve construir software — ¿sí?',
        }
        response = api_client.post(_url(token), _call('create_blog_post', args), format='json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        assert not response.json()['result'].get('isError'), response.json()
        post = BlogPost.objects.latest('id')
        assert post.linkedin_summary_en == 'Café → Result'
        assert post.linkedin_summary_es == 'Así se ve construir software — ¿sí?'

    def test_create_with_escaped_json_body(self, api_client, blog_connector):
        """A strict JSON encoder (ensure_ascii) is still valid JSON."""
        _, token = blog_connector
        args = {**VALID_POST, 'linkedin_summary_en': 'Café → Result'}
        raw = json.dumps(_call('create_blog_post', args), ensure_ascii=True)
        assert '\\u00e9' in raw
        response = api_client.post(_url(token), data=raw, content_type='application/json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        post = BlogPost.objects.latest('id')
        assert post.linkedin_summary_en == 'Café → Result'

    def test_create_decodes_literal_escape_sequences(self, api_client, blog_connector):
        """Double-escaped input: the argument VALUE itself contains the
        literal characters ``\\u00e9`` — what a buggy MCP client sends."""
        _, token = blog_connector
        args = {
            **VALID_POST,
            'linkedin_summary_en': 'Caf\\u00e9 \\u2192 Result',
            'linkedin_summary_es': 'As\\u00ed se ve \\u2014 \\u00bfs\\u00ed?',
        }
        response = api_client.post(_url(token), _call('create_blog_post', args), format='json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        assert not response.json()['result'].get('isError'), response.json()
        post = BlogPost.objects.latest('id')
        assert post.linkedin_summary_en == 'Café → Result'
        assert post.linkedin_summary_es == 'Así se ve — ¿sí?'

    def test_update_decodes_literal_escape_sequences(self, api_client, blog_connector):
        _, token = blog_connector
        post = BlogPost.objects.create(
            title_es='T', title_en='T', slug='utf8-update',
            excerpt_es='E', excerpt_en='E',
        )
        args = {'post_id': post.id, 'linkedin_summary_en': 'Caf\\u00e9 \\u2192 Result'}
        response = api_client.post(_url(token), _call('update_blog_post', args), format='json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        assert not response.json()['result'].get('isError'), response.json()
        post.refresh_from_db()
        assert post.linkedin_summary_en == 'Café → Result'

    def test_decodes_escapes_inside_content_json(self, api_client, blog_connector):
        _, token = blog_connector
        args = {
            **VALID_POST,
            'content_json_es': {
                'intro': 'Introducci\\u00f3n con emoji \\ud83d\\ude00.',
                'sections': [{'heading': 'Secci\\u00f3n', 'content': 'Texto.'}],
            },
        }
        response = api_client.post(_url(token), _call('create_blog_post', args), format='json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        assert not response.json()['result'].get('isError'), response.json()
        post = BlogPost.objects.latest('id')
        assert post.content_json_es['intro'] == 'Introducción con emoji 😀.'
        assert post.content_json_es['sections'][0]['heading'] == 'Sección'

    def test_lone_surrogate_escape_is_left_untouched(self, api_client, blog_connector):
        """An unpaired surrogate cannot become a valid character — leave the
        literal text as-is instead of corrupting the string."""
        _, token = blog_connector
        args = {**VALID_POST, 'linkedin_summary_en': 'broken \\ud83d escape'}
        response = api_client.post(_url(token), _call('create_blog_post', args), format='json')
        response = _confirm(api_client, token, response)
        assert response.status_code == 200
        post = BlogPost.objects.latest('id')
        assert post.linkedin_summary_en == 'broken \\ud83d escape'


@pytest.mark.django_db
class TestFixBlogUnicodeEscapesCommand:
    def _corrupted_post(self):
        return BlogPost.objects.create(
            title_es='T\\u00edtulo', title_en='Title', slug='corrupted-post',
            excerpt_es='E', excerpt_en='E',
            linkedin_summary_en='Caf\\u00e9 \\u2192 Result',
            content_json_es={'intro': 'Introducci\\u00f3n', 'sections': []},
        )

    def test_dry_run_reports_without_saving(self):
        post = self._corrupted_post()
        out = StringIO()
        call_command('fix_blog_unicode_escapes', stdout=out)
        post.refresh_from_db()
        assert post.linkedin_summary_en == 'Caf\\u00e9 \\u2192 Result'
        assert 'WOULD FIX' in out.getvalue()

    def test_apply_decodes_all_fields(self):
        post = self._corrupted_post()
        call_command('fix_blog_unicode_escapes', '--apply', stdout=StringIO())
        post.refresh_from_db()
        assert post.title_es == 'Título'
        assert post.linkedin_summary_en == 'Café → Result'
        assert post.content_json_es['intro'] == 'Introducción'
