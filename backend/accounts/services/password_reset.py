"""Business logic for the platform forgot-password flow.

State between the three HTTP steps is carried in short-lived JWTs (see
``accounts.services.tokens``). The OTP itself lives in ``VerificationCode``.
"""
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from rest_framework_simplejwt.exceptions import TokenError

from accounts.models import VerificationCode
from accounts.services.tokens import (
    PASSWORD_RESET_REQUEST_PURPOSE,
    PASSWORD_RESET_VERIFIED_PURPOSE,
    decode_password_reset_token,
    get_decoy_password_reset_request_token,
    get_password_reset_password_version,
    get_password_reset_request_token,
    get_password_reset_verified_token,
    get_tokens_for_user,
)
from accounts.services.verification import create_and_send_otp
from content.services.email_delivery_service import (
    DeliveryClassification,
    EmailDeliveryGateway,
)

logger = logging.getLogger('accounts.services.password_reset')
User = get_user_model()

COOLDOWN_SECONDS = 60


class PasswordResetError(Exception):
    """Service-level error with a stable code + optional payload extras.

    Views map this to HTTP responses.
    """

    def __init__(self, code: str, http_status: int = 400, extra: dict | None = None):
        self.code = code
        self.http_status = http_status
        self.extra = extra or {}
        super().__init__(code)


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.encode('utf-8')).hexdigest()[:12]


def request_password_reset(email: str) -> str:
    """Step 1. Always returns a request token (real or decoy)."""
    email_lower = (email or '').lower().strip()
    user = User.objects.filter(email__iexact=email_lower).first()

    if user is None:
        logger.info(
            'password_reset_requested',
            extra={'email_hash': _email_hash(email_lower), 'user_found': False, 'cooldown_hit': False},
        )
        return get_decoy_password_reset_request_token()

    cutoff = timezone.now() - timedelta(seconds=COOLDOWN_SECONDS)
    cooldown_hit = VerificationCode.objects.filter(
        user=user,
        purpose=VerificationCode.PURPOSE_PASSWORD_RESET,
        created_at__gte=cutoff,
    ).exists()

    if not cooldown_hit:
        create_and_send_otp(user, purpose=VerificationCode.PURPOSE_PASSWORD_RESET)

    logger.info(
        'password_reset_requested',
        extra={'email_hash': _email_hash(email_lower), 'user_found': True, 'cooldown_hit': cooldown_hit},
    )
    return get_password_reset_request_token(user)


def verify_reset_code(request_token: str, code: str) -> str:
    """Step 2. Validates the OTP and returns a verified token."""
    try:
        payload = decode_password_reset_token(request_token, expected_purpose=PASSWORD_RESET_REQUEST_PURPOSE)
    except TokenError:
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    user_id = payload.get('user_id')
    if not user_id:
        # decoy token — generic failure
        raise PasswordResetError('invalid_code')

    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise PasswordResetError('invalid_code')

    latest = (
        VerificationCode.objects
        .filter(user=user, purpose=VerificationCode.PURPOSE_PASSWORD_RESET, is_used=False)
        .order_by('-created_at')
        .first()
    )

    if not latest:
        raise PasswordResetError('invalid_code')

    if latest.is_expired:
        raise PasswordResetError('code_expired')

    if latest.attempts >= VerificationCode.MAX_ATTEMPTS:
        raise PasswordResetError('too_many_attempts')

    if latest.code != code:
        latest.increment_attempts()
        remaining = VerificationCode.MAX_ATTEMPTS - latest.attempts
        if remaining <= 0:
            raise PasswordResetError('too_many_attempts')
        raise PasswordResetError('invalid_code', extra={'attempts_left': remaining})

    latest.mark_used()
    logger.info('password_reset_code_verified', extra={'user_id': user.pk})
    return get_password_reset_verified_token(user)


def confirm_password_reset(verified_token: str, new_password: str) -> dict:
    """Step 3. Sets the new password, fires the confirmation email, and returns
    a session payload identical in shape to a successful /login/ response."""
    try:
        payload = decode_password_reset_token(verified_token, expected_purpose=PASSWORD_RESET_VERIFIED_PURPOSE)
    except TokenError:
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    user_id = payload.get('user_id')
    if not user_id:
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    user = User.objects.filter(pk=user_id).first()
    if not user:
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    password_version = payload.get('password_version')
    if not isinstance(password_version, str) or not constant_time_compare(
        password_version, get_password_reset_password_version(user),
    ):
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    original_password = user.password
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise PasswordResetError('weak_password', extra={'errors': list(exc.messages)})

    user.set_password(new_password)
    # A password change after the token check must win over this stale reset.
    with transaction.atomic():
        updated = User.objects.filter(
            pk=user.pk, password=original_password,
        ).update(password=user.password)
    if updated != 1:
        raise PasswordResetError('invalid_or_expired_token', http_status=401)

    password_validation.password_changed(new_password, user)

    try:
        send_password_changed_notification(user)
    except Exception as exc:  # noqa: BLE001 — email failures must not roll back password change
        logger.warning(
            'password_reset_email_failure',
            extra={'user_id': user.pk, 'reason': str(exc)},
        )

    logger.info('password_reset_completed', extra={'user_id': user.pk})

    tokens = get_tokens_for_user(user)
    profile = getattr(user, 'profile', None)
    # Lazy import: serializer pulls models we want to keep out of the
    # service module's import graph for testability.
    from accounts.serializers import UserProfileSerializer
    return {
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': UserProfileSerializer(profile).data if profile else None,
    }


def send_password_changed_notification(user) -> None:
    """Renders and sends the post-reset confirmation email. Best-effort:
    callers are responsible for swallowing exceptions."""
    context = {
        'user': user,
        'changed_at': timezone.now(),
        'support_email': 'team@projectapp.co',
    }
    html_message = render_to_string('emails/password_reset_completed.html', context)
    text_message = render_to_string('emails/password_reset_completed.txt', context)
    EmailDeliveryGateway.send_plain(
        subject='Se restableció la contraseña de tu cuenta — ProjectApp',
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipients=[user.email],
        html_body=html_message,
        template_key='password_changed',
        classification=DeliveryClassification.SECURITY,
        fail_silently=False,
    )
