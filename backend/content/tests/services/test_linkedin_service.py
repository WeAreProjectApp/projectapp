"""Tests for LinkedIn OAuth service.

Covers: token exchange, encrypted storage, auto-refresh, publish,
connection status, and encryption round-trip.
"""
import logging
from datetime import datetime, timedelta
from datetime import timezone as dt_tz
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from freezegun import freeze_time
from requests.exceptions import Timeout

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
    """Generate a valid Fernet key for tests."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


@pytest.fixture
def token_with_access(fernet_key):
    """A LinkedInToken with a valid access token."""
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


@pytest.fixture
def token_with_refresh(fernet_key):
    """A LinkedInToken with both access and refresh tokens (access expired)."""
    with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
        token = LinkedInToken.load()
        token.set_access_token('expired-access-token')
        token.set_refresh_token('valid-refresh-token')
        token.expires_at = FROZEN_NOW - timedelta(hours=1)
        token.refresh_token_expires_at = FROZEN_NOW + timedelta(days=30)
        token.obtained_at = FROZEN_NOW - timedelta(days=30)
        token.member_sub = 'abc123'
        token.profile_name = 'Test User'
        token.save()
        return token


# ---------------------------------------------------------------------------
# TestExchangeCodeForToken
# ---------------------------------------------------------------------------

class TestExchangeCodeForToken:

    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service._cache_profile_info')
    def test_saves_encrypted_token_on_success(self, mock_cache, mock_post, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'access_token': 'new-access-token',
                'expires_in': 5_184_000,
                'refresh_token': 'new-refresh-token',
            }
            mock_post.return_value = mock_resp

            result = linkedin_service.exchange_code_for_token('auth-code-123')

            assert result['access_token'] == 'new-access-token'
            mock_post.assert_called_once()
            mock_cache.assert_called_once()
            token = LinkedInToken.load()
            assert token.get_access_token() == 'new-access-token'
            assert token.get_refresh_token() == 'new-refresh-token'
            assert token.expires_at is not None

    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service._cache_profile_info')
    def test_computes_expires_at_from_response(self, mock_cache, mock_post, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'access_token': 'tok',
                'expires_in': 3600,
            }
            mock_post.return_value = mock_resp

            linkedin_service.exchange_code_for_token('code')

            mock_post.assert_called_once()
            token = LinkedInToken.load()
            assert token.expires_at is not None
            delta = token.expires_at - token.obtained_at
            assert 3590 < delta.total_seconds() < 3610

    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_raises_value_error_on_api_failure(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = 'invalid_grant'
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError, match='token exchange failed') as exc_info:
            linkedin_service.exchange_code_for_token('bad-code')

        assert 'token exchange failed' in str(exc_info.value)
        mock_post.assert_called_once()

    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service._cache_profile_info')
    def test_handles_missing_refresh_token(self, mock_cache, mock_post, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'access_token': 'access-only',
                'expires_in': 5_184_000,
            }
            mock_post.return_value = mock_resp

            linkedin_service.exchange_code_for_token('code')

            mock_post.assert_called_once()
            token = LinkedInToken.load()
            assert token.get_access_token() == 'access-only'
            assert token.get_refresh_token() is None


# ---------------------------------------------------------------------------
# TestGetAccessToken
# ---------------------------------------------------------------------------

class TestGetAccessToken:

    @freeze_time(FROZEN_NOW)
    def test_returns_token_when_valid(self, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_access_token()
            assert result == 'test-access-token-123'

    def test_returns_none_when_no_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_access_token()
            assert result is None

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_refreshes_expired_token(self, mock_post, fernet_key, token_with_refresh):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'access_token': 'refreshed-access-token',
                'expires_in': 5_184_000,
            }
            mock_post.return_value = mock_resp

            result = linkedin_service.get_access_token()
            assert result == 'refreshed-access-token'

            mock_post.assert_called_once()
            token = LinkedInToken.load()
            assert token.get_access_token() == 'refreshed-access-token'

    @freeze_time(FROZEN_NOW)
    def test_clears_token_when_refresh_also_expired(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('expired')
            token.set_refresh_token('also-expired')
            token.expires_at = FROZEN_NOW - timedelta(hours=1)
            token.refresh_token_expires_at = FROZEN_NOW - timedelta(days=1)
            token.save()

            result = linkedin_service.get_access_token()
            assert result is None

            token.refresh_from_db()
            assert token.get_access_token() is None


# ---------------------------------------------------------------------------
# TestRefreshAccessToken
# ---------------------------------------------------------------------------

class TestRefreshAccessToken:

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_successful_refresh_updates_token(self, mock_post, fernet_key, token_with_refresh):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                'access_token': 'new-from-refresh',
                'expires_in': 5_184_000,
            }
            mock_post.return_value = mock_resp

            result = linkedin_service._refresh_access_token()
            assert result == 'new-from-refresh'
            mock_post.assert_called_once()

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_failed_refresh_clears_token(self, mock_post, fernet_key, token_with_refresh):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = 'invalid_token'
            mock_resp.json.side_effect = ValueError
            mock_post.return_value = mock_resp

            result = linkedin_service._refresh_access_token()
            assert result is None

            mock_post.assert_called_once()
            token = LinkedInToken.load()
            assert token.get_access_token() is None


def _stored_token_state():
    token = LinkedInToken.load()
    return (
        token.access_token_encrypted,
        token.refresh_token_encrypted,
        token.expires_at,
        token.refresh_token_expires_at,
        token.obtained_at,
        token.member_sub,
        token.profile_name,
        token.profile_email,
    )


def _json_failure(status, payload):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = payload
    return response


def _text_failure(status, body):
    response = MagicMock()
    response.status_code = status
    response.text = body
    response.json.side_effect = ValueError
    return response


class TestRefreshFailureClassification:
    @pytest.mark.parametrize('response_factory', [
        lambda: _text_failure(429, 'rate limited'),
        lambda: _text_failure(500, 'upstream error'),
        lambda: _text_failure(503, 'maintenance'),
        lambda: _text_failure(504, 'gateway timeout'),
        lambda: _text_failure(400, '<html>unknown error</html>'),
        lambda: _json_failure(400, ['unexpected']),
        lambda: _json_failure(400, {'error': 'invalid_request'}),
        lambda: _json_failure(401, {'error': 'invalid_client'}),
    ])
    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_unclassified_refresh_failure_preserves_connection(
        self, mock_post, fernet_key, token_with_refresh, response_factory,
    ):
        """Fails if a temporary or ambiguous OAuth response disconnects LinkedIn."""
        mock_post.return_value = response_factory()
        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            before = _stored_token_state()
            result = linkedin_service._refresh_access_token()

            after = _stored_token_state()
        assert result is None
        assert after == before

    @pytest.mark.parametrize('response_factory', [
        lambda: _json_failure(400, {'error': 'invalid_grant'}),
        lambda: _json_failure(401, {'error': 'invalid_token'}),
        lambda: _json_failure(400, {
            'error': 'invalid_request',
            'error_description': 'The  provided authorization grant or refresh token is invalid, expired or revoked',
        }),
    ])
    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_explicit_credential_rejection_clears_connection(
        self, mock_post, fernet_key, token_with_refresh, response_factory,
    ):
        """Fails if an explicit OAuth credential rejection leaves a dead token stored."""
        mock_post.return_value = response_factory()
        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            result = linkedin_service._refresh_access_token()

            token = LinkedInToken.load()
            assert result is None
            assert token.get_access_token() is None
            assert token.get_refresh_token() is None
            assert token.profile_name == ''

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_refresh_recovers_after_temporary_provider_failure(
        self, mock_post, fernet_key, token_with_refresh,
    ):
        """Fails if a retained refresh token cannot recover on the next successful call."""
        unavailable = _text_failure(503, 'maintenance')
        refreshed = _json_failure(200, {'access_token': 'recovered-access', 'expires_in': 3600})
        mock_post.side_effect = [unavailable, refreshed]
        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            first = linkedin_service._refresh_access_token()
            second = linkedin_service._refresh_access_token()

            token = LinkedInToken.load()
            assert first is None
            assert second == 'recovered-access'
            assert token.get_access_token() == 'recovered-access'

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_refresh_diagnostic_excludes_oauth_secrets(
        self, mock_post, caplog, fernet_key, token_with_refresh,
    ):
        """Fails if a failed refresh logs token values or provider response bodies."""
        mock_post.return_value = _text_failure(503, 'provider-body-sentinel')
        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override), caplog.at_level(
            logging.ERROR, logger='content.services.linkedin_service',
        ):
            result = linkedin_service._refresh_access_token()

        messages = caplog.text
        assert result is None
        assert 'status=503' in messages
        assert 'category=transient' in messages
        assert 'expired-access-token' not in messages
        assert 'valid-refresh-token' not in messages
        assert 'provider-body-sentinel' not in messages

    @freeze_time(FROZEN_NOW)
    @override_settings(**LINKEDIN_SETTINGS)
    @patch('content.services.linkedin_service.requests.post')
    def test_refresh_timeout_preserves_connection(
        self, mock_post, fernet_key, token_with_refresh,
    ):
        """Fails if a transport timeout clears OAuth credentials before it propagates."""
        mock_post.side_effect = Timeout('timeout')
        settings_override = {**LINKEDIN_SETTINGS, 'LINKEDIN_ENCRYPTION_KEY': fernet_key}
        with override_settings(**settings_override):
            before = _stored_token_state()
            with pytest.raises(Timeout, match='timeout'):
                linkedin_service._refresh_access_token()
            after = _stored_token_state()

        assert after == before


# ---------------------------------------------------------------------------
# TestPublishBlogToLinkedin
# ---------------------------------------------------------------------------

class TestPublishBlogToLinkedin:

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._upload_image_to_linkedin', return_value='urn:li:image:C4E10test')
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='valid-token')
    def test_successful_publish_returns_post_id(self, mock_token, mock_urn, mock_post, mock_upload):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {'x-restli-id': 'urn:li:share:123456'}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Test summary',
            blog_url='https://projectapp.co/blog/test',
            title='Test Post',
            cover_image_url='https://images.unsplash.com/photo-test',
        )

        assert result['success'] is True
        assert result['post_id'] == 'urn:li:share:123456'
        mock_upload.assert_called_once_with('https://images.unsplash.com/photo-test')
        mock_post.assert_called_once()
        # Verify the thumbnail is the image URN, not the raw URL
        call_payload = mock_post.call_args[1]['json']
        assert call_payload['content']['article']['thumbnail'] == 'urn:li:image:C4E10test'

    @patch('content.services.linkedin_service.get_access_token', return_value=None)
    def test_raises_when_not_connected(self, mock_token):
        with pytest.raises(ValueError, match='not connected') as exc_info:
            linkedin_service.publish_blog_to_linkedin(
                summary='Test', blog_url='https://x.co', title='T',
            )

        assert 'not connected' in str(exc_info.value)
        mock_token.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:abc')
    @patch('content.services.linkedin_service.get_access_token', return_value='valid-token')
    def test_returns_failure_on_api_error(self, mock_token, mock_urn, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = 'Forbidden'
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        result = linkedin_service.publish_blog_to_linkedin(
            summary='Test', blog_url='https://x.co', title='T',
        )
        assert result['success'] is False
        mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetConnectionStatus
# ---------------------------------------------------------------------------

class TestGetConnectionStatus:

    @freeze_time(FROZEN_NOW)
    def test_returns_connected_with_cached_profile(self, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_connection_status()
            assert result['connected'] is True
            assert result['profile_name'] == 'Test User'

    def test_returns_disconnected_when_no_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_connection_status()
            assert result['connected'] is False

    @freeze_time(FROZEN_NOW)
    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    def test_clears_token_on_invalid_profile(self, mock_fetch, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('some-token')
            token.expires_at = FROZEN_NOW + timedelta(days=30)
            token.profile_name = ''
            token.save()

            result = linkedin_service.get_connection_status()
            assert result['connected'] is False

            mock_fetch.assert_called_once()
            token.refresh_from_db()
            assert token.get_access_token() is None


# ---------------------------------------------------------------------------
# TestEncryptionHelpers
# ---------------------------------------------------------------------------

class TestEncryptionHelpers:

    def test_round_trip_encryption(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.set_access_token('super-secret-token')
            token.save()

            token.refresh_from_db()
            assert token.get_access_token() == 'super-secret-token'

    def test_returns_none_with_empty_encryption_key(self):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=''):
            token = LinkedInToken.load()
            token.access_token_encrypted = 'some-encrypted-data'
            token.save()

            assert token.get_access_token() is None


# ---------------------------------------------------------------------------
# TestGetAuthorizationUrl
# ---------------------------------------------------------------------------

class TestGetAuthorizationUrl:

    @override_settings(
        LINKEDIN_CLIENT_ID='test-client-id',
        LINKEDIN_REDIRECT_URI='https://example.com/callback',
    )
    def test_includes_state_in_url_when_provided(self):
        url = linkedin_service.get_authorization_url(state='csrf-token-abc')

        assert 'state=csrf-token-abc' in url

    @override_settings(
        LINKEDIN_CLIENT_ID='test-client-id',
        LINKEDIN_REDIRECT_URI='https://example.com/callback',
    )
    def test_omits_state_param_when_empty(self):
        url = linkedin_service.get_authorization_url()

        assert 'state=' not in url
        assert 'client_id=test-client-id' in url


# ---------------------------------------------------------------------------
# TestFetchProfileFromApi
# ---------------------------------------------------------------------------

class TestFetchProfileFromApi:

    @patch('content.services.linkedin_service.requests.get')
    def test_returns_profile_dict_on_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'sub': 'user123', 'name': 'Ada Lovelace'}
        mock_get.return_value = mock_resp

        result = linkedin_service._fetch_profile_from_api('token-abc')

        assert result['sub'] == 'user123'
        mock_get.assert_called_once()

    @patch('content.services.linkedin_service.requests.get')
    def test_returns_none_on_non_200_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = 'Unauthorized'
        mock_get.return_value = mock_resp

        result = linkedin_service._fetch_profile_from_api('bad-token')

        assert result is None
        mock_get.assert_called_once()


# ---------------------------------------------------------------------------
# TestCacheProfileInfo
# ---------------------------------------------------------------------------

class TestCacheProfileInfo:

    def test_returns_without_update_when_no_access_token(self, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            # Token exists but has no access token set
            token = LinkedInToken.load()
            token.save()

            linkedin_service._cache_profile_info()

            token.refresh_from_db()
            assert token.member_sub == ''

    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    def test_returns_without_update_when_profile_fetch_fails(self, mock_fetch, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token_with_access.member_sub = ''
            token_with_access.save()

            linkedin_service._cache_profile_info()

            token_with_access.refresh_from_db()
            assert token_with_access.member_sub == ''

    @patch('content.services.linkedin_service._fetch_profile_from_api')
    def test_updates_token_with_profile_data_on_success(self, mock_fetch, fernet_key, token_with_access):
        mock_fetch.return_value = {
            'sub': 'new-sub-xyz',
            'name': 'New Name',
            'picture': 'https://pic.test/photo.jpg',
            'email': 'new@test.com',
        }
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            linkedin_service._cache_profile_info()

            token_with_access.refresh_from_db()
            assert token_with_access.member_sub == 'new-sub-xyz'
            assert token_with_access.profile_name == 'New Name'
            assert token_with_access.profile_email == 'new@test.com'


# ---------------------------------------------------------------------------
# TestGetMemberUrn
# ---------------------------------------------------------------------------

class TestGetMemberUrn:

    def test_returns_cached_urn_when_member_sub_is_set(self, fernet_key, token_with_access):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            result = linkedin_service.get_member_urn()

            assert result == 'urn:li:person:abc123'

    @patch('content.services.linkedin_service.get_access_token', return_value=None)
    def test_returns_none_when_no_access_token_and_no_cached_sub(self, mock_token, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            # Token has no member_sub
            token = LinkedInToken.load()
            token.member_sub = ''
            token.save()

            result = linkedin_service.get_member_urn()

            assert result is None

    @patch('content.services.linkedin_service._fetch_profile_from_api', return_value=None)
    @patch('content.services.linkedin_service.get_access_token', return_value='token-xyz')
    def test_returns_none_when_profile_fetch_fails(self, mock_token, mock_fetch, fernet_key):
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.member_sub = ''
            token.save()

            result = linkedin_service.get_member_urn()

            assert result is None

    @patch('content.services.linkedin_service._fetch_profile_from_api')
    @patch('content.services.linkedin_service.get_access_token', return_value='token-xyz')
    def test_caches_and_returns_urn_when_fetched_from_api(self, mock_token, mock_fetch, fernet_key):
        mock_fetch.return_value = {'sub': 'fetched-sub-999', 'name': 'Fetched User'}
        with override_settings(LINKEDIN_ENCRYPTION_KEY=fernet_key):
            token = LinkedInToken.load()
            token.member_sub = ''
            token.save()

            result = linkedin_service.get_member_urn()

            assert result == 'urn:li:person:fetched-sub-999'
            token.refresh_from_db()
            assert token.member_sub == 'fetched-sub-999'


# ---------------------------------------------------------------------------
# TestUploadImageToLinkedin
# ---------------------------------------------------------------------------

class TestUploadImageToLinkedin:

    @patch('content.services.linkedin_service.get_access_token', return_value=None)
    def test_returns_none_when_not_connected(self, mock_token):
        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result is None

    @patch('content.services.linkedin_service.get_member_urn', return_value=None)
    @patch('content.services.linkedin_service.get_access_token', return_value='token')
    def test_returns_none_when_no_member_urn(self, mock_token, mock_urn):
        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result is None

    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:x')
    @patch('content.services.linkedin_service.get_access_token', return_value='token')
    def test_returns_none_when_image_download_fails(self, mock_token, mock_urn, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.RequestException('timeout')

        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result is None

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:x')
    @patch('content.services.linkedin_service.get_access_token', return_value='token')
    def test_returns_none_when_init_upload_fails(self, mock_token, mock_urn, mock_get, mock_post):
        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = b'fake-image-bytes'
        img_resp.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = img_resp

        init_resp = MagicMock()
        init_resp.status_code = 500
        init_resp.text = 'Internal Error'
        mock_post.return_value = init_resp

        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result is None
        mock_get.assert_called_once_with('https://img.test/photo.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:x')
    @patch('content.services.linkedin_service.get_access_token', return_value='token')
    def test_returns_none_when_init_response_missing_upload_url(self, mock_token, mock_urn, mock_get, mock_post):
        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = b'bytes'
        img_resp.headers = {}
        mock_get.return_value = img_resp

        init_resp = MagicMock()
        init_resp.status_code = 200
        init_resp.json.return_value = {'value': {'image': 'urn:li:image:123'}}  # uploadUrl missing
        mock_post.return_value = init_resp

        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result is None
        mock_get.assert_called_once_with('https://img.test/photo.jpg', timeout=30, stream=True)
        mock_post.assert_called_once()

    @patch('content.services.linkedin_service.requests.put')
    @patch('content.services.linkedin_service.requests.post')
    @patch('content.services.linkedin_service.requests.get')
    @patch('content.services.linkedin_service.get_member_urn', return_value='urn:li:person:x')
    @patch('content.services.linkedin_service.get_access_token', return_value='token')
    def test_returns_image_urn_on_successful_upload(self, mock_token, mock_urn, mock_get, mock_post, mock_put):
        img_resp = MagicMock()
        img_resp.raise_for_status.return_value = None
        img_resp.content = b'fake-bytes'
        img_resp.headers = {'Content-Type': 'image/jpeg'}
        mock_get.return_value = img_resp

        init_resp = MagicMock()
        init_resp.status_code = 200
        init_resp.json.return_value = {
            'value': {'uploadUrl': 'https://uploads.li.com/v1/img', 'image': 'urn:li:image:ABC'},
        }
        mock_post.return_value = init_resp

        upload_resp = MagicMock()
        upload_resp.status_code = 201
        mock_put.return_value = upload_resp

        result = linkedin_service._upload_image_to_linkedin('https://img.test/photo.jpg')

        assert result == 'urn:li:image:ABC'
        mock_put.assert_called_once()
