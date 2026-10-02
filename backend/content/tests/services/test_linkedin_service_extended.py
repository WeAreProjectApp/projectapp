"""Additional tests for uncovered branches in linkedin_service.py.

Targets: _api_headers, _save_token, _refresh_access_token,
get_authorization_url, exchange_code_for_token, get_access_token (expired),
_fetch_profile_from_api, _cache_profile_info, get_member_urn,
_upload_image_to_linkedin, publish_blog_to_linkedin (all branches),
get_connection_status (all branches).
"""
from datetime import datetime, timedelta
from datetime import timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from freezegun import freeze_time

from content.models import LinkedInToken
from content.services import linkedin_service

pytestmark = pytest.mark.django_db

FROZEN_NOW = datetime(2026, 4, 4, 12, 0, 0, tzinfo=dt_tz.utc)

LINKEDIN_SETTINGS = {
    'LINKEDIN_CLIENT_ID': 'test-client-id',
    'LINKEDIN_CLIENT_SECRET': 'test-client-secret',
    'LINKEDIN_REDIRECT_URI': 'https://example.com/callback',
    'LINKEDIN_ENCRYPTION_KEY': '',
}


@pytest.fixture
def fernet_key():
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


@pytest.fixture
def token_with_access(fernet_key):
    with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
        token = LinkedInToken.load()
        token.set_access_token('test-access-token-123')
        token.expires_at = FROZEN_NOW + timedelta(days=30)
        token.obtained_at = FROZEN_NOW
        token.member_sub = 'abc123'
        token.profile_name = 'Test User'
        token.profile_email = 'test@example.com'
        token.save()
        return token


# ===========================================================================
# _api_headers
# ===========================================================================

class TestApiHeaders:
    def test_returns_bearer_authorization_header(self):
        headers = linkedin_service._api_headers('my-token')

        assert headers['Authorization'] == 'Bearer my-token'

    def test_returns_default_json_content_type(self):
        headers = linkedin_service._api_headers('tok')

        assert headers['Content-Type'] == 'application/json'

    def test_accepts_custom_content_type(self):
        headers = linkedin_service._api_headers('tok', content_type='image/jpeg')

        assert headers['Content-Type'] == 'image/jpeg'

    def test_includes_restli_protocol_version(self):
        headers = linkedin_service._api_headers('tok')

        assert headers['X-Restli-Protocol-Version'] == '2.0.0'

    def test_includes_linkedin_api_version(self):
        headers = linkedin_service._api_headers('tok')

        assert headers['LinkedIn-Version'] == linkedin_service.LINKEDIN_API_VERSION


# ===========================================================================
# _cache_profile_info
# ===========================================================================

class TestCacheProfileInfo:
    def test_does_nothing_when_no_access_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            linkedin_service._cache_profile_info()

            token = LinkedInToken.load()
            assert token.profile_name == ''

    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    def test_does_nothing_when_profile_fetch_fails(self, mock_fetch, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('valid-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.save()

            linkedin_service._cache_profile_info()

            token.refresh_from_db()
            assert token.profile_name == ''

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api')
    def test_saves_profile_data_when_fetch_succeeds(self, mock_fetch, fernet_key):
        mock_fetch.return_value = {
            'sub': 'user123',
            'name': 'Jane Doe',
            'picture': 'https://example.com/pic.jpg',
            'email': 'jane@example.com',
        }

        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('valid-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.save()

            linkedin_service._cache_profile_info()

            token.refresh_from_db()
            assert token.member_sub == 'user123'
            assert token.profile_name == 'Jane Doe'
            assert token.profile_email == 'jane@example.com'


# ===========================================================================
# get_member_urn
# ===========================================================================

class TestGetMemberUrn:
    @freeze_time(FROZEN_NOW)
    def test_returns_cached_urn_when_member_sub_exists(self, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_member_urn()

            assert result == 'urn:li:person:abc123'

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api')
    def test_fetches_from_api_when_no_cached_sub(self, mock_fetch, fernet_key):
        mock_fetch.return_value = {'sub': 'fetched456', 'name': 'Bob'}

        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('valid-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.member_sub = ''
            token.save()

            result = linkedin_service.get_member_urn()

            assert result == 'urn:li:person:fetched456'
            token.refresh_from_db()
            assert token.member_sub == 'fetched456'

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    def test_returns_none_when_profile_unavailable(self, mock_fetch, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('valid-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.member_sub = ''
            token.save()

            result = linkedin_service.get_member_urn()

            assert result is None

    def test_returns_none_when_not_connected(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_member_urn()

            assert result is None


# ===========================================================================
# _upload_image_to_linkedin
# ===========================================================================

class TestUploadImageToLinkedin:
    @patch('content.services.linkedin_service.get_access_token', return_value=None)
    def test_returns_none_when_not_connected(self, mock_token):
        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None

    @patch('content.services.linkedin_service.get_member_urn', return_value=None)
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_none_when_no_member_urn(self, mock_token, mock_urn):
        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None

    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_none_when_image_download_fails(self, mock_token, mock_urn, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException('network error')

        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_none_when_init_upload_fails(
        self, mock_token, mock_urn, mock_get, mock_post,
    ):
        mock_img = MagicMock()
        mock_img.raise_for_status.return_value = None
        mock_img.content = b'image bytes'
        mock_img.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = mock_img

        mock_init = MagicMock()
        mock_init.status_code = 500
        mock_init.text = 'Internal Error'
        mock_post.return_value = mock_init

        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_get.assert_called_once_with('https://example.com/img.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_none_when_init_missing_upload_url(
        self, mock_token, mock_urn, mock_get, mock_post,
    ):
        mock_img = MagicMock()
        mock_img.raise_for_status.return_value = None
        mock_img.content = b'image bytes'
        mock_img.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = mock_img

        mock_init = MagicMock()
        mock_init.status_code = 200
        mock_init.json.return_value = {'value': {}}  # No uploadUrl or image
        mock_post.return_value = mock_init

        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_get.assert_called_once_with('https://example.com/img.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.put')
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_image_urn_on_success(
        self, mock_token, mock_urn, mock_get, mock_post, mock_put,
    ):
        mock_img = MagicMock()
        mock_img.raise_for_status.return_value = None
        mock_img.content = b'image bytes'
        mock_img.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = mock_img

        mock_init = MagicMock()
        mock_init.status_code = 200
        mock_init.json.return_value = {
            'value': {
                'uploadUrl': 'https://upload.linkedin.com/img/upload',
                'image': 'urn:li:image:ABC123',
            },
        }
        mock_post.return_value = mock_init

        mock_upload = MagicMock()
        mock_upload.status_code = 201
        mock_put.return_value = mock_upload

        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result == 'urn:li:image:ABC123'
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_get.assert_called_once_with('https://example.com/img.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()
        mock_put.assert_called_once()

    @patch('content.services.linkedin_service.requests.put')
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_none_when_binary_upload_fails(
        self, mock_token, mock_urn, mock_get, mock_post, mock_put,
    ):
        mock_img = MagicMock()
        mock_img.raise_for_status.return_value = None
        mock_img.content = b'image bytes'
        mock_img.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = mock_img

        mock_init = MagicMock()
        mock_init.status_code = 200
        mock_init.json.return_value = {
            'value': {
                'uploadUrl': 'https://upload.linkedin.com/img/upload',
                'image': 'urn:li:image:ABC123',
            },
        }
        mock_post.return_value = mock_init

        mock_upload = MagicMock()
        mock_upload.status_code = 500
        mock_put.return_value = mock_upload

        result = linkedin_service._upload_image_to_linkedin('https://example.com/img.jpg')

        assert result is None
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_get.assert_called_once_with('https://example.com/img.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()
        mock_put.assert_called_once()


# ===========================================================================
# _refresh_access_token — missing no-refresh-token branch
# ===========================================================================

class TestRefreshAccessTokenNoToken:
    @freeze_time(FROZEN_NOW)
    def test_returns_none_and_clears_when_no_refresh_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('expired-access')
            token.expires_at = FROZEN_NOW - timedelta(hours=1)
            token.save()

            result = linkedin_service._refresh_access_token()

            assert result is None
            token.refresh_from_db()
            assert token.get_access_token() is None


# ===========================================================================
# publish_blog_to_linkedin — missing branches
# ===========================================================================

class TestPublishBlogMissingBranches:
    @patch('content.services.linkedin_service.get_member_urn', return_value=None)
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_raises_when_member_urn_unavailable(self, mock_token, mock_urn):
        # quality: disable no_assertions (pytest.raises is the assertion)
        with pytest.raises(ValueError, match='member URN'):
            linkedin_service.publish_blog_to_linkedin(
                summary='Test', blog_url='https://x.co', title='T',
            )

    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_raises_when_summary_is_empty(self, mock_token, mock_urn):
        # quality: disable no_assertions (pytest.raises is the assertion)
        with pytest.raises(ValueError, match='Summary text is required'):
            linkedin_service.publish_blog_to_linkedin(
                summary='', blog_url='https://x.co', title='T',
            )

    @patch('content.services.linkedin_service._upload_image_to_linkedin', return_value=None)
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_publishes_without_thumbnail_when_upload_fails(
        self, mock_token, mock_urn, mock_post, mock_upload,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:999'}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Post text',
            blog_url='https://x.co',
            title='T',
            cover_image_url='https://img.example.com/cover.jpg',
        )

        assert result['success'] is True
        payload = mock_post.call_args[1]['json']
        assert 'thumbnail' not in payload['content']['article']
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_upload.assert_called_once_with('https://img.example.com/cover.jpg')
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_publishes_without_cover_image_url(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:111'}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='No image post',
            blog_url='https://x.co',
            title='T',
        )

        assert result['success'] is True
        payload = mock_post.call_args[1]['json']
        assert 'thumbnail' not in payload['content']['article']
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_replaces_escaped_newlines_in_summary(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:222'}
        mock_post.return_value = mock_resp

        linkedin_service.publish_blog_to_linkedin(
            summary='Line one\\nLine two',
            blog_url='https://x.co',
            title='T',
        )

        payload = mock_post.call_args[1]['json']
        assert payload['commentary'] == 'Line one\nLine two'
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_status_200_response_is_treated_as_success(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {'x-restli-id': 'urn:li:share:333'}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Post', blog_url='https://x.co', title='T',
        )

        assert result['success'] is True
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_description_included_in_article_when_provided(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:444'}
        mock_post.return_value = mock_resp

        linkedin_service.publish_blog_to_linkedin(
            summary='Post',
            blog_url='https://x.co',
            title='T',
            description='Short blurb',
        )

        payload = mock_post.call_args[1]['json']
        assert payload['content']['article']['description'] == 'Short blurb'
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_post.assert_called_once()


# ===========================================================================
# get_connection_status — API fallback success path
# ===========================================================================

class TestConnectionStatusApiFallback:
    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api')
    def test_caches_and_returns_profile_when_fetched_from_api(
        self, mock_fetch, fernet_key,
    ):
        mock_fetch.return_value = {
            'sub': 'api_user_sub',
            'name': 'API User',
            'picture': 'https://pic.example.com',
            'email': 'apiuser@example.com',
        }

        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('valid-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.profile_name = ''
            token.save()

            result = linkedin_service.get_connection_status()

            assert result['connected'] is True
            assert result['profile_name'] == 'API User'
            assert result['email'] == 'apiuser@example.com'

            token.refresh_from_db()
            assert token.profile_name == 'API User'
            assert token.member_sub == 'api_user_sub'


# ===========================================================================
# _save_token
# ===========================================================================

class TestSaveToken:
    @freeze_time(FROZEN_NOW)
    def test_saves_access_token_and_expiry(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            linkedin_service._save_token({
                'access_token': 'new-access-token',
                'expires_in': 3600,
            })

            token = LinkedInToken.load()
            assert token.get_access_token() == 'new-access-token'

    @freeze_time(FROZEN_NOW)
    def test_saves_refresh_token_when_provided(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            linkedin_service._save_token({
                'access_token': 'access',
                'expires_in': 3600,
                'refresh_token': 'my-refresh-token',
            })

            token = LinkedInToken.load()
            assert token.get_refresh_token() == 'my-refresh-token'

    @freeze_time(FROZEN_NOW)
    def test_skips_refresh_token_when_absent(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            linkedin_service._save_token({
                'access_token': 'access-only',
                'expires_in': 3600,
            })

            token = LinkedInToken.load()
            assert token.get_refresh_token() is None


# ===========================================================================
# _refresh_access_token — HTTP call path
# ===========================================================================

class TestRefreshAccessTokenHttpPath:
    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service.requests.post')
    def test_refreshes_successfully_and_returns_new_token(self, mock_post, fernet_key):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'access_token': 'refreshed-tok', 'expires_in': 7200}
        mock_post.return_value = mock_resp

        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            token = LinkedInToken.load()
            token.set_access_token('expired-access')
            token.set_refresh_token('valid-refresh')
            token.expires_at = FROZEN_NOW - timedelta(hours=1)
            token.refresh_token_expires_at = FROZEN_NOW + timedelta(days=60)
            token.save()

            result = linkedin_service._refresh_access_token()

            assert result == 'refreshed-tok'
            mock_post.assert_called_once()

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service.requests.post')
    def test_clears_token_and_returns_none_when_refresh_fails(self, mock_post, fernet_key):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = 'invalid_grant'
        mock_resp.json.side_effect = ValueError
        mock_post.return_value = mock_resp

        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            token = LinkedInToken.load()
            token.set_access_token('expired-access')
            token.set_refresh_token('bad-refresh')
            token.expires_at = FROZEN_NOW - timedelta(hours=1)
            token.refresh_token_expires_at = FROZEN_NOW + timedelta(days=60)
            token.save()

            result = linkedin_service._refresh_access_token()

            assert result is None
            token.refresh_from_db()
            assert token.get_access_token() is None
            mock_post.assert_called_once()


# ===========================================================================
# get_authorization_url
# ===========================================================================

class TestGetAuthorizationUrl:
    def test_returns_url_with_required_params(self):
        with override_settings(**LINKEDIN_SETTINGS):
            url = linkedin_service.get_authorization_url()

            assert 'client_id=test-client-id' in url
            assert 'response_type=code' in url

    def test_includes_state_param_when_provided(self):
        with override_settings(**LINKEDIN_SETTINGS):
            url = linkedin_service.get_authorization_url(state='csrf-token-123')

            assert 'state=csrf-token-123' in url

    def test_omits_state_param_when_empty(self):
        with override_settings(**LINKEDIN_SETTINGS):
            url = linkedin_service.get_authorization_url(state='')

            assert 'state=' not in url


# ===========================================================================
# exchange_code_for_token
# ===========================================================================

class TestExchangeCodeForToken:
    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._cache_profile_info')
    @patch('content.services.linkedin_service.requests.post')
    def test_saves_token_and_returns_data_on_success(
        self, mock_post, mock_cache, fernet_key,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'access_token': 'new-tok', 'expires_in': 5184000}
        mock_post.return_value = mock_resp

        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            result = linkedin_service.exchange_code_for_token('auth-code-abc')

            assert result['access_token'] == 'new-tok'
            mock_cache.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    def test_raises_value_error_when_exchange_fails(self, mock_post):
        # quality: disable no_assertions (pytest.raises is the assertion)
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = 'invalid_code'
        mock_post.return_value = mock_resp

        with override_settings(**LINKEDIN_SETTINGS):
            with pytest.raises(ValueError, match='token exchange failed'):
                linkedin_service.exchange_code_for_token('bad-code')
        # quality: allow-call-contract (request boundary: verifies the POST to the OAuth endpoint was attempted; observable effect is the pytest.raises above)
        mock_post.assert_called_once()


# ===========================================================================
# get_access_token — expired → refresh path
# ===========================================================================

class TestGetAccessTokenExpiredPath:
    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._refresh_access_token', return_value='refreshed')
    def test_calls_refresh_when_token_is_expired(self, mock_refresh, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('expired-tok')
            token.expires_at = FROZEN_NOW - timedelta(seconds=1)
            token.obtained_at = FROZEN_NOW - timedelta(hours=2)
            token.save()

            result = linkedin_service.get_access_token()

            assert result == 'refreshed'
            mock_refresh.assert_called_once()


# ===========================================================================
# _fetch_profile_from_api
# ===========================================================================

class TestFetchProfileFromApi:
    @patch('content.services.linkedin_service.requests.get')
    def test_returns_profile_dict_on_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'sub': 'xyz', 'name': 'Alice'}
        mock_get.return_value = mock_resp

        result = linkedin_service._fetch_profile_from_api('test-token')

        assert result['sub'] == 'xyz'
        assert result['name'] == 'Alice'
        mock_get.assert_called_once()

    @patch('content.services.linkedin_service.requests.get')
    def test_returns_none_on_api_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = 'Unauthorized'
        mock_get.return_value = mock_resp

        result = linkedin_service._fetch_profile_from_api('bad-token')

        assert result is None
        mock_get.assert_called_once()


# ===========================================================================
# publish_blog_to_linkedin — remaining branches
# ===========================================================================

class TestPublishBlogRemainingBranches:
    @patch('content.services.linkedin_service.get_access_token', return_value=None)
    def test_raises_when_not_connected(self, mock_token):
        # quality: disable no_assertions (pytest.raises is the assertion)
        with pytest.raises(ValueError, match='not connected'):
            linkedin_service.publish_blog_to_linkedin(
                summary='Test', blog_url='https://x.co', title='T',
            )

    @patch('content.services.linkedin_service._upload_image_to_linkedin', return_value='urn:li:image:IMG1')
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_sets_thumbnail_when_image_upload_succeeds(
        self, mock_token, mock_urn, mock_post, mock_upload,
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:999'}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Post', blog_url='https://x.co', title='T',
            cover_image_url='https://img.example.com/cover.jpg',
        )

        assert result['success'] is True
        payload = mock_post.call_args[1]['json']
        assert payload['content']['article']['thumbnail'] == 'urn:li:image:IMG1'
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_upload.assert_called_once_with('https://img.example.com/cover.jpg')
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='tok')
    def test_returns_failure_dict_on_api_error(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.text = 'Unprocessable'
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Post', blog_url='https://x.co', title='T',
        )

        assert result['success'] is False
        assert '422' in result['message']
        mock_token.assert_called_once()
        mock_urn.assert_called_once()
        mock_post.assert_called_once()


# ===========================================================================
# get_connection_status — no access token + cached profile
# ===========================================================================

class TestGetConnectionStatusRemainingBranches:
    def test_returns_not_connected_when_no_access_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_connection_status()

            assert result == {'connected': False}

    @freeze_time(FROZEN_NOW)
    def test_returns_connected_with_cached_profile(self, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_connection_status()

            assert result['connected'] is True
            assert result['profile_name'] == 'Test User'

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    def test_clears_token_and_returns_not_connected_when_fetch_fails(
        self, mock_fetch, fernet_key,
    ):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('stale-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.profile_name = ''
            token.save()

            result = linkedin_service.get_connection_status()

            assert result['connected'] is False
            token.refresh_from_db()
            assert token.get_access_token() is None
