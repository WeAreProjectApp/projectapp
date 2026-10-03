"""Tests for the platform password recovery flow."""
import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from freezegun import freeze_time
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from accounts.models import VerificationCode
from accounts.services.tokens import (
    PASSWORD_RESET_REQUEST_PURPOSE,
    PASSWORD_RESET_VERIFIED_PURPOSE,
    decode_password_reset_token,
    get_decoy_password_reset_request_token,
    get_password_reset_request_token,
    get_password_reset_verified_token,
)
from accounts.services.verification import create_and_send_otp

User = get_user_model()
pytestmark = pytest.mark.django_db


class ConcurrentPasswordChangeValidator:
    """Changes the stored password during validation to exercise reset CAS."""

    changed_calls = []

    def validate(self, password, user=None):
        """Persist a competing password without changing the reset snapshot."""
        competing_user = User.objects.get(pk=user.pk)
        competing_user.set_password('ConcurrentStrongPass789!')
        User.objects.filter(pk=user.pk).update(password=competing_user.password)

    def get_help_text(self):
        """Provide the validator interface without adding policy copy."""
        return ''

    def password_changed(self, password, user=None):
        """Record whether a losing compare-and-swap invokes this hook."""
        type(self).changed_calls.append((password, user.pk))


class RecordingPasswordChangedValidator:
    """Records Django's post-change callback for a successful reset."""

    changed_calls = []

    def validate(self, password, user=None):
        """Accept the supplied password so confirmation reaches the hook."""
        return None

    def get_help_text(self):
        """Provide the validator interface without adding policy copy."""
        return ''

    def password_changed(self, password, user=None):
        """Record the concrete password and user supplied by Django."""
        type(self).changed_calls.append((password, user.pk))


def _token_without_password_version(user):
    token = AccessToken.for_user(user)
    token['purpose'] = PASSWORD_RESET_VERIFIED_PURPOSE
    return str(token)


def _token_with_non_string_password_version(user):
    token = AccessToken.for_user(user)
    token['purpose'] = PASSWORD_RESET_VERIFIED_PURPOSE
    token['password_version'] = 1
    return str(token)


def _token_with_incorrect_password_version(user):
    token = AccessToken.for_user(user)
    token['purpose'] = PASSWORD_RESET_VERIFIED_PURPOSE
    token['password_version'] = 'not-the-current-password-version'
    return str(token)


@pytest.fixture
def reset_user(db):
    """Create an account whose original password anchors reset assertions."""
    return User.objects.create_user(
        username='reset@example.com',
        email='reset@example.com',
        password='OldPass123!',
    )


@pytest.fixture(autouse=True)
def locmem_mailer(settings):
    """Route password-reset notices to the deterministic in-memory outbox."""
    settings.MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
        },
    }


def test_request_token_contains_user_id_and_purpose(reset_user):
    """Fails if a step-one token cannot be tied to its account and purpose."""
    raw = get_password_reset_request_token(reset_user)
    decoded = AccessToken(raw)
    assert decoded['purpose'] == PASSWORD_RESET_REQUEST_PURPOSE
    assert int(decoded['user_id']) == reset_user.pk


def test_verified_token_contains_user_id(reset_user):
    """Fails if verified recovery authority cannot identify its account."""
    raw = get_password_reset_verified_token(reset_user)
    decoded = AccessToken(raw)
    assert int(decoded['user_id']) == reset_user.pk


def test_verified_token_marks_verified_purpose(reset_user):
    """Fails if a verified recovery token loses its dedicated authorization scope."""
    raw = get_password_reset_verified_token(reset_user)

    assert AccessToken(raw)['purpose'] == PASSWORD_RESET_VERIFIED_PURPOSE


def test_verified_token_version_changes_after_password_change(reset_user):
    """Fails if password binding stays stable or exposes an encoded password hash."""
    initial_password = reset_user.password
    initial_token = get_password_reset_verified_token(reset_user)
    initial_version = AccessToken(initial_token)['password_version']
    reset_user.set_password('SeparateStrongPass789!')
    reset_user.save(update_fields=['password'])
    current_token = get_password_reset_verified_token(reset_user)
    current_version = AccessToken(current_token)['password_version']

    assert initial_version != initial_password
    assert current_version != reset_user.password
    assert current_version != initial_version


def test_decoy_token_has_no_user_id_but_correct_purpose():
    """Fails if unknown-email tokens reveal an account identifier."""
    raw = get_decoy_password_reset_request_token()
    decoded = AccessToken(raw)
    assert decoded['purpose'] == PASSWORD_RESET_REQUEST_PURPOSE
    assert decoded.payload.get('user_id') is None


def test_decoder_rejects_wrong_purpose(reset_user):
    """Fails if a request token can satisfy verified-token decoding."""
    raw = get_password_reset_request_token(reset_user)
    with pytest.raises(TokenError):
        decode_password_reset_token(raw, expected_purpose=PASSWORD_RESET_VERIFIED_PURPOSE)


def test_decoder_returns_payload_when_purpose_matches(reset_user):
    """Fails if a correctly scoped password-reset token loses its user ID."""
    raw = get_password_reset_request_token(reset_user)
    payload = decode_password_reset_token(raw, expected_purpose=PASSWORD_RESET_REQUEST_PURPOSE)
    assert int(payload['user_id']) == reset_user.pk


def test_request_token_expires_after_10_minutes(reset_user):
    """Fails if the request step remains usable beyond its ten-minute limit."""
    with freeze_time('2026-05-16 10:00:00'):
        raw = get_password_reset_request_token(reset_user)
    with freeze_time('2026-05-16 10:11:00'):
        with pytest.raises(TokenError):
            decode_password_reset_token(raw, expected_purpose=PASSWORD_RESET_REQUEST_PURPOSE)


def test_verified_token_expires_after_5_minutes(reset_user):
    """Fails if the verified recovery authority outlives five minutes."""
    with freeze_time('2026-05-16 10:00:00'):
        raw = get_password_reset_verified_token(reset_user)
    with freeze_time('2026-05-16 10:06:00'):
        with pytest.raises(TokenError):
            decode_password_reset_token(raw, expected_purpose=PASSWORD_RESET_VERIFIED_PURPOSE)


def test_confirm_rejects_expired_verified_token(reset_user):
    """Fails if confirmation accepts a verified token after its five-minute lifetime."""
    with freeze_time('2026-05-16 10:00:00'):
        verified_token = get_password_reset_verified_token(reset_user)

    with freeze_time('2026-05-16 10:06:00'):
        with pytest.raises(PasswordResetError) as exc:
            confirm_password_reset(verified_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()
    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('OldPass123!')


# ==========================================================================
# verification.create_and_send_otp template routing
# ==========================================================================


def test_create_and_send_otp_uses_password_reset_template_for_reset_purpose(reset_user):
    """Fails if recovery codes send generic onboarding content instead."""
    mail.outbox = []
    create_and_send_otp(reset_user, purpose=VerificationCode.PURPOSE_PASSWORD_RESET)
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    body_html = sent.alternatives[0][0] if sent.alternatives else ''
    body_text = sent.body
    assert 'restablec' in body_text.lower() or 'restablec' in body_html.lower()
    assert reset_user.email in sent.to


def test_create_and_send_otp_default_purpose_still_uses_onboarding_template(reset_user):
    """Fails if ordinary verification adopts password-recovery copy."""
    mail.outbox = []
    create_and_send_otp(reset_user)  # defaults to PURPOSE_ONBOARDING
    assert len(mail.outbox) == 1
    sent = mail.outbox[0]
    body_html = sent.alternatives[0][0] if sent.alternatives else ''
    # The onboarding email body should NOT contain password-reset copy.
    assert 'restablecer' not in sent.body.lower()
    assert 'restablecer' not in body_html.lower()


# ==========================================================================
# password_reset service — request/verify/confirm
# ==========================================================================


from accounts.services.password_reset import (  # noqa: E402
    PasswordResetError,
    confirm_password_reset,
    request_password_reset,
    verify_reset_code,
)


def test_request_with_existing_email_creates_code_and_sends_email(reset_user):
    """Fails if a recognized account receives neither a usable code nor notice."""
    mail.outbox = []
    token = request_password_reset(reset_user.email)
    assert token  # non-empty string
    assert len(mail.outbox) == 1
    assert VerificationCode.objects.filter(
        user=reset_user, purpose=VerificationCode.PURPOSE_PASSWORD_RESET, is_used=False,
    ).count() == 1


def test_request_with_nonexistent_email_returns_decoy_token():
    """Fails if an unknown address gets a real account-linked recovery token."""
    mail.outbox = []
    token = request_password_reset('ghost@example.com')
    assert token
    decoded = AccessToken(token)
    assert decoded.payload.get('user_id') is None
    assert len(mail.outbox) == 0


def test_request_cooldown_skips_resend(reset_user):
    """Fails if repeated recovery requests bypass the resend cooldown."""
    mail.outbox = []
    request_password_reset(reset_user.email)
    request_password_reset(reset_user.email)
    assert len(mail.outbox) == 1
    # Even on the second call we still hand back a valid token.
    second = request_password_reset(reset_user.email)
    assert int(AccessToken(second)['user_id']) == reset_user.pk


def test_request_cooldown_lapsed_resends(reset_user):
    """Fails if a request remains throttled after the cooldown has elapsed."""
    mail.outbox = []
    with freeze_time('2026-05-16 10:00:00'):
        request_password_reset(reset_user.email)
    with freeze_time('2026-05-16 10:01:30'):
        request_password_reset(reset_user.email)
    assert len(mail.outbox) == 2


def test_verify_with_valid_code_returns_verified_token(reset_user):
    """Fails if the correct OTP does not advance recovery authorization."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    code = VerificationCode.objects.filter(
        user=reset_user, purpose=VerificationCode.PURPOSE_PASSWORD_RESET, is_used=False,
    ).latest('created_at').code
    verified_token = verify_reset_code(request_token, code)
    assert AccessToken(verified_token)['purpose'] == 'password_reset_verified'
    assert int(AccessToken(verified_token)['user_id']) == reset_user.pk


def test_verify_with_wrong_code_decrements_attempts(reset_user):
    """Fails if an invalid OTP does not expose the remaining attempt count."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    with pytest.raises(PasswordResetError) as exc:
        verify_reset_code(request_token, '000000')
    assert exc.value.code == 'invalid_code'
    assert exc.value.extra.get('attempts_left') == 4


def test_verify_with_wrong_code_5_times_returns_too_many_attempts(reset_user):
    """Fails if five invalid OTP submissions leave recovery available."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    for _ in range(4):
        with pytest.raises(PasswordResetError):
            verify_reset_code(request_token, '000000')
    with pytest.raises(PasswordResetError) as exc:
        verify_reset_code(request_token, '000000')
    assert exc.value.code == 'too_many_attempts'


def test_verify_with_expired_code_returns_expiry_error(reset_user):
    """Reject recovery after both the OTP and request token expire.

    At +11min both the OTP (10-min EXPIRY) and the request token (10-min
    lifetime) have expired. The decoder rejects the token first → service
    raises `invalid_or_expired_token`. If lifetimes ever diverge so the
    request token still validates, the code-level checks would surface
    `code_expired` instead — accept both.
    """
    mail.outbox = []
    with freeze_time('2026-05-16 10:00:00'):
        request_token = request_password_reset(reset_user.email)
        real_code = VerificationCode.objects.latest('created_at').code
    with freeze_time('2026-05-16 10:11:00'):
        with pytest.raises(PasswordResetError) as exc:
            verify_reset_code(request_token, real_code)
        assert exc.value.code in {'code_expired', 'invalid_or_expired_token'}


def test_verify_with_decoy_token_returns_invalid_code():
    """Fails if a decoy token can reach OTP verification."""
    decoy = get_decoy_password_reset_request_token()
    with pytest.raises(PasswordResetError) as exc:
        verify_reset_code(decoy, '123456')
    assert exc.value.code == 'invalid_code'


def test_confirm_with_valid_token_returns_session_for_changed_password(reset_user):
    """Fails if confirmed recovery cannot issue a session for the new password."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    real_code = VerificationCode.objects.latest('created_at').code
    verified_token = verify_reset_code(request_token, real_code)
    payload = confirm_password_reset(verified_token, 'NewStrongPass456!')
    reset_user.refresh_from_db()

    assert reset_user.check_password('NewStrongPass456!')
    assert int(AccessToken(payload['access'])['user_id']) == reset_user.pk
    assert int(RefreshToken(payload['refresh'])['user_id']) == reset_user.pk


def test_weak_password_rejection_keeps_verified_token_usable(reset_user):
    """Fails if validation failure consumes recovery authority before a retry."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    real_code = VerificationCode.objects.latest('created_at').code
    verified_token = verify_reset_code(request_token, real_code)
    with pytest.raises(PasswordResetError) as exc:
        confirm_password_reset(verified_token, '12345')

    payload = confirm_password_reset(verified_token, 'NewStrongPass456!')
    reset_user.refresh_from_db()

    assert exc.value.code == 'weak_password'
    assert exc.value.extra.get('errors')
    assert int(AccessToken(payload['access'])['user_id']) == reset_user.pk
    assert int(RefreshToken(payload['refresh'])['user_id']) == reset_user.pk
    assert reset_user.check_password('NewStrongPass456!')


def test_confirm_rejects_request_token_used_as_verified(reset_user):
    """Fails if a step-one request token authorizes the final password change."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    outbox_before_confirmation = len(mail.outbox)
    with pytest.raises(PasswordResetError) as exc:
        confirm_password_reset(request_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()

    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('OldPass123!')
    assert len(mail.outbox) == outbox_before_confirmation


def test_confirm_rejects_replayed_verified_token(reset_user):
    """Fails if a verified reset token can overwrite a password after first use."""
    mail.outbox = []
    verified_token = get_password_reset_verified_token(reset_user)
    confirm_password_reset(verified_token, 'NewStrongPass456!')
    outbox_after_first_confirmation = len(mail.outbox)

    with pytest.raises(PasswordResetError) as exc:
        confirm_password_reset(verified_token, 'DifferentStrongPass789!')

    reset_user.refresh_from_db()
    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('NewStrongPass456!')
    assert not reset_user.check_password('DifferentStrongPass789!')
    assert len(mail.outbox) == outbox_after_first_confirmation


def test_confirm_rejects_token_after_separate_password_change(reset_user):
    """Fails if a stale verified token overrides a separately persisted password."""
    mail.outbox = []
    verified_token = get_password_reset_verified_token(reset_user)
    reset_user.set_password('SeparateStrongPass789!')
    reset_user.save(update_fields=['password'])

    with pytest.raises(PasswordResetError) as exc:
        confirm_password_reset(verified_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()
    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('SeparateStrongPass789!')
    assert len(mail.outbox) == 0


def test_confirm_rejects_concurrent_password_change(reset_user):
    """Fails if validation-time password changes are overwritten by the reset write."""
    ConcurrentPasswordChangeValidator.changed_calls = []
    mail.outbox = []
    verified_token = get_password_reset_verified_token(reset_user)

    with override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME': 'accounts.tests.test_password_reset.ConcurrentPasswordChangeValidator',
    }]):
        with pytest.raises(PasswordResetError) as exc:
            confirm_password_reset(verified_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()
    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('ConcurrentStrongPass789!')
    assert mail.outbox == []
    assert ConcurrentPasswordChangeValidator.changed_calls == []


def test_confirm_calls_configured_password_changed_hook(reset_user):
    """Fails if a successful conditional reset bypasses configured password-change hooks."""
    RecordingPasswordChangedValidator.changed_calls = []
    verified_token = get_password_reset_verified_token(reset_user)

    with override_settings(AUTH_PASSWORD_VALIDATORS=[{
        'NAME': 'accounts.tests.test_password_reset.RecordingPasswordChangedValidator',
    }]):
        confirm_password_reset(verified_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()
    assert reset_user.check_password('NewStrongPass456!')
    assert RecordingPasswordChangedValidator.changed_calls == [
        ('NewStrongPass456!', reset_user.pk),
    ]


@pytest.mark.parametrize('token_factory', [
    _token_without_password_version,
    _token_with_non_string_password_version,
    _token_with_incorrect_password_version,
])
def test_confirm_rejects_invalid_password_version_claim(reset_user, token_factory):
    """Fails if confirmation accepts missing, malformed, or stale password binding claims."""
    mail.outbox = []
    verified_token = token_factory(reset_user)

    with pytest.raises(PasswordResetError) as exc:
        confirm_password_reset(verified_token, 'NewStrongPass456!')

    reset_user.refresh_from_db()
    assert exc.value.code == 'invalid_or_expired_token'
    assert exc.value.http_status == 401
    assert reset_user.check_password('OldPass123!')
    assert mail.outbox == []


def test_confirm_sends_confirmation_email_to_user(reset_user):
    """Fails if a completed reset omits its account-security notification."""
    mail.outbox = []
    request_token = request_password_reset(reset_user.email)
    real_code = VerificationCode.objects.latest('created_at').code
    verified_token = verify_reset_code(request_token, real_code)
    confirm_password_reset(verified_token, 'NewStrongPass456!')
    confirmation_emails = [m for m in mail.outbox if 'restableci' in m.subject.lower()]
    assert len(confirmation_emails) == 1
    assert confirmation_emails[0].to == [reset_user.email]


# ==========================================================================
# HTTP-level integration tests (views + routes)
# ==========================================================================


from rest_framework.test import APIClient  # noqa: E402


@pytest.fixture
def api_client():
    """Provide an unauthenticated client for recovery endpoint contracts."""
    return APIClient()


def test_request_view_returns_token_for_existing_email(api_client, reset_user):
    """Fails if the request endpoint cannot start recovery for a known user."""
    mail.outbox = []
    resp = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': reset_user.email}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['reset_request_token']
    assert len(mail.outbox) == 1


def test_request_view_returns_decoy_token_for_unknown_email(api_client):
    """Fails if the request endpoint distinguishes unknown addresses by status."""
    mail.outbox = []
    resp = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': 'ghost@example.com'}, format='json',
    )
    assert resp.status_code == 200
    assert resp.json()['reset_request_token']
    assert len(mail.outbox) == 0


def test_request_view_rejects_malformed_email(api_client):
    """Fails if malformed account identifiers bypass request validation."""
    resp = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': 'not-an-email'}, format='json',
    )
    assert resp.status_code == 400


def test_verify_view_happy_path(api_client, reset_user):
    """Fails if a correct OTP cannot produce the confirmation authority."""
    mail.outbox = []
    r1 = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': reset_user.email}, format='json',
    )
    request_token = r1.json()['reset_request_token']
    code = VerificationCode.objects.latest('created_at').code
    r2 = api_client.post(
        '/api/accounts/password-reset/verify-code/',
        {'reset_request_token': request_token, 'code': code}, format='json',
    )
    assert r2.status_code == 200
    assert r2.json()['reset_verified_token']


def test_verify_view_wrong_code_surfaces_attempts_left(api_client, reset_user):
    """Fails if the verification endpoint hides remaining OTP attempts."""
    mail.outbox = []
    r1 = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': reset_user.email}, format='json',
    )
    request_token = r1.json()['reset_request_token']
    r2 = api_client.post(
        '/api/accounts/password-reset/verify-code/',
        {'reset_request_token': request_token, 'code': '000000'}, format='json',
    )
    assert r2.status_code == 400
    body = r2.json()
    assert body['detail'] == 'invalid_code'
    assert body['attempts_left'] == 4


def test_confirm_view_completes_flow_and_returns_session(api_client, reset_user):
    """Fails if the HTTP confirmation flow changes a password without a session."""
    mail.outbox = []
    r1 = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': reset_user.email}, format='json',
    )
    request_token = r1.json()['reset_request_token']
    code = VerificationCode.objects.latest('created_at').code
    r2 = api_client.post(
        '/api/accounts/password-reset/verify-code/',
        {'reset_request_token': request_token, 'code': code}, format='json',
    )
    verified_token = r2.json()['reset_verified_token']
    r3 = api_client.post(
        '/api/accounts/password-reset/confirm/',
        {'reset_verified_token': verified_token, 'new_password': 'NewStrongPass456!'}, format='json',
    )
    assert r3.status_code == 200
    body = r3.json()
    assert 'access' in body
    assert 'refresh' in body
    reset_user.refresh_from_db()
    assert reset_user.check_password('NewStrongPass456!')


def test_confirm_view_weak_password_returns_errors(api_client, reset_user):
    """Fails if the confirmation endpoint accepts a weak replacement password."""
    mail.outbox = []
    r1 = api_client.post(
        '/api/accounts/password-reset/request/',
        {'email': reset_user.email}, format='json',
    )
    request_token = r1.json()['reset_request_token']
    code = VerificationCode.objects.latest('created_at').code
    r2 = api_client.post(
        '/api/accounts/password-reset/verify-code/',
        {'reset_request_token': request_token, 'code': code}, format='json',
    )
    verified_token = r2.json()['reset_verified_token']
    r3 = api_client.post(
        '/api/accounts/password-reset/confirm/',
        {'reset_verified_token': verified_token, 'new_password': '12345678'}, format='json',
    )
    # 8-char all-numeric password: passes serializer min_length but should fail
    # Django's NumericPasswordValidator inside the service.
    assert r3.status_code == 400
    body = r3.json()
    assert body['detail'] == 'weak_password'
    assert isinstance(body['errors'], list)
    assert body['errors']
