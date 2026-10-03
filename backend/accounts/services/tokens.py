import json
from datetime import timedelta

from django.utils.crypto import salted_hmac
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken


def get_tokens_for_user(user):
    """Generate JWT access + refresh tokens with custom claims."""
    refresh = RefreshToken.for_user(user)

    profile = getattr(user, 'profile', None)
    if profile:
        refresh['role'] = profile.role
        refresh['is_onboarded'] = profile.is_onboarded
        refresh['email'] = user.email

    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


def get_verification_token_for_user(user):
    """
    Generate a short-lived signed token used during the verification step.
    This is NOT a full access token — just proves the user passed step 1 (temp password).
    """
    refresh = RefreshToken.for_user(user)
    refresh['purpose'] = 'verification'
    refresh['email'] = user.email
    return str(refresh.access_token)


# ==========================================================================
# Password recovery — state-machine tokens
# ==========================================================================

PASSWORD_RESET_REQUEST_PURPOSE = 'password_reset_request'
PASSWORD_RESET_VERIFIED_PURPOSE = 'password_reset_verified'

REQUEST_TOKEN_LIFETIME = timedelta(minutes=10)
VERIFIED_TOKEN_LIFETIME = timedelta(minutes=5)


def get_password_reset_request_token(user) -> str:
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=REQUEST_TOKEN_LIFETIME)
    token['purpose'] = PASSWORD_RESET_REQUEST_PURPOSE
    return str(token)


def get_password_reset_verified_token(user) -> str:
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=VERIFIED_TOKEN_LIFETIME)
    token['purpose'] = PASSWORD_RESET_VERIFIED_PURPOSE
    token['password_version'] = get_password_reset_password_version(user)
    return str(token)


def get_password_reset_password_version(user) -> str:
    """Bind verified tokens to the current password without exposing its hash."""
    return salted_hmac(
        'accounts.password-reset-verified-v1',
        json.dumps([user.pk, user.password]),
        algorithm='sha256',
    ).hexdigest()


def get_decoy_password_reset_request_token() -> str:
    """Returned when the requested email does not match a registered user.
    Same shape and lifetime as the real token but without a ``user_id`` claim,
    so any follow-up step fails with the generic invalid_code response."""
    token = AccessToken()
    token.set_exp(lifetime=REQUEST_TOKEN_LIFETIME)
    token['purpose'] = PASSWORD_RESET_REQUEST_PURPOSE
    return str(token)


def decode_password_reset_token(token_str: str, expected_purpose: str) -> dict:
    """Decode a password-reset token. Raises ``rest_framework_simplejwt.TokenError``
    when the signature is invalid, the token is expired, or the ``purpose`` claim
    does not match ``expected_purpose``."""
    token = AccessToken(token_str)
    if token.get('purpose') != expected_purpose:
        raise TokenError('Token purpose mismatch.')
    return token.payload
