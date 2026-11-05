import io
import string
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from freezegun import freeze_time
from PIL import Image

from accounts.models import UserProfile, VerificationCode
from accounts.services.image_utils import MAX_DIMENSION, optimize_avatar
from accounts.services.onboarding import (
    TEMP_PASSWORD_LENGTH,
    create_client,
    generate_temp_password,
    resend_invitation,
)
from accounts.services.tokens import get_tokens_for_user, get_verification_token_for_user
from accounts.services.verification import create_and_send_otp, validate_otp

User = get_user_model()


# =========================================================================
# generate_temp_password
# =========================================================================

class TestGenerateTempPassword:
    def test_returns_string_of_correct_length(self):
        password = generate_temp_password()

        assert isinstance(password, str)
        assert len(password) == TEMP_PASSWORD_LENGTH

    def test_password_uses_allowed_alphabet(self):
        allowed = set(string.ascii_letters + string.digits + '!@#$%')

        password = generate_temp_password()

        assert all(ch in allowed for ch in password)

    def test_consecutive_calls_return_different_passwords(self):
        p1 = generate_temp_password()
        p2 = generate_temp_password()

        assert p1 != p2


# =========================================================================
# create_client
# =========================================================================

@pytest.mark.django_db
class TestCreateClient:
    def test_creates_user_and_profile_with_client_role(self, mailoutbox):
        user, temp_password = create_client(
            email='new@example.com',
            first_name='Ana',
            last_name='García',
            company_name='ACME',
            phone='+57 300 111 2222',
        )

        assert user.email == 'new@example.com'
        assert user.first_name == 'Ana'
        assert user.is_active is False
        assert user.check_password(temp_password) is True
        assert user.profile.role == UserProfile.ROLE_CLIENT
        assert user.profile.is_onboarded is False
        assert user.profile.company_name == 'ACME'

    def test_sends_invitation_email(self, mailoutbox):
        create_client(
            email='invite@example.com',
            first_name='Test',
            last_name='User',
        )

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['invite@example.com']
        assert 'Bienvenido' in mailoutbox[0].subject

    def test_normalizes_email_to_lowercase(self, mailoutbox):
        user, _ = create_client(
            email='  UPPER@Example.COM  ',
            first_name='Test',
            last_name='User',
        )

        assert user.email == 'upper@example.com'

    def test_raises_value_error_for_duplicate_email(self, mailoutbox):
        create_client(email='dup@test.com', first_name='A', last_name='B')

        with pytest.raises(ValueError, match='Ya existe'):
            create_client(email='dup@test.com', first_name='C', last_name='D')

    def test_sets_created_by_when_provided(self, mailoutbox):
        admin = User.objects.create_user(
            username='admin@test.com', email='admin@test.com', password='pass',
        )
        user, _ = create_client(
            email='client@test.com',
            first_name='X',
            last_name='Y',
            created_by=admin,
        )

        assert user.profile.created_by == admin


# =========================================================================
# resend_invitation
# =========================================================================

@pytest.mark.django_db
class TestResendInvitation:
    @pytest.fixture
    def client_user(self, mailoutbox):
        user, _ = create_client(
            email='resend@test.com', first_name='Re', last_name='Send',
        )
        mailoutbox.clear()
        return user

    def test_resets_password_and_sends_email(self, client_user, mailoutbox):
        old_password_hash = client_user.password

        new_temp = resend_invitation(client_user)

        client_user.refresh_from_db()
        assert client_user.password != old_password_hash
        assert client_user.check_password(new_temp) is True
        assert len(mailoutbox) == 1

    def test_sets_is_onboarded_to_false(self, client_user, mailoutbox):
        profile = client_user.profile
        profile.is_onboarded = True
        profile.save(update_fields=['is_onboarded'])

        resend_invitation(client_user)

        profile.refresh_from_db()
        assert profile.is_onboarded is False


# =========================================================================
# create_and_send_otp
# =========================================================================

@pytest.mark.django_db
class TestCreateAndSendOtp:
    @pytest.fixture
    def user(self):
        user = User.objects.create_user(
            username='otp@test.com', email='otp@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        return user

    def test_creates_verification_code_and_sends_email(self, user, mailoutbox):
        otp = create_and_send_otp(user)

        assert len(otp.code) == 6
        assert otp.is_used is False
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ['otp@test.com']

    def test_invalidates_previous_codes(self, user, mailoutbox):
        first_otp = create_and_send_otp(user)
        second_otp = create_and_send_otp(user)

        first_otp.refresh_from_db()
        assert first_otp.is_used is True
        assert second_otp.is_used is False


# =========================================================================
# validate_otp
# =========================================================================

@pytest.mark.django_db
class TestValidateOtp:
    @pytest.fixture
    def user_with_otp(self):
        user = User.objects.create_user(
            username='val@test.com', email='val@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        otp = VerificationCode.create_for_user(user)
        return user, otp

    def test_valid_code_returns_success(self, user_with_otp):
        user, otp = user_with_otp

        success, error = validate_otp(user, otp.code)

        assert success is True
        assert error is None
        otp.refresh_from_db()
        assert otp.is_used is True

    def test_wrong_code_increments_attempts(self, user_with_otp):
        user, otp = user_with_otp

        success, error = validate_otp(user, '000000')

        assert success is False
        assert 'incorrecto' in error.lower()
        otp.refresh_from_db()
        assert otp.attempts == 1

    @freeze_time('2025-06-01 12:00:00')
    def test_expired_code_returns_error(self):
        user = User.objects.create_user(
            username='exp@test.com', email='exp@test.com', password='pass',
        )
        UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)
        otp = VerificationCode.create_for_user(user)

        with freeze_time('2025-06-01 12:11:00'):
            success, error = validate_otp(user, otp.code)

        assert success is False
        assert 'expirado' in error.lower()

    def test_max_attempts_returns_error(self, user_with_otp):
        user, otp = user_with_otp
        otp.attempts = VerificationCode.MAX_ATTEMPTS
        otp.save(update_fields=['attempts'])

        success, error = validate_otp(user, otp.code)

        assert success is False
        assert 'intentos' in error.lower()

    def test_no_active_code_returns_error(self):
        user = User.objects.create_user(
            username='nocode@test.com', email='nocode@test.com', password='pass',
        )

        success, error = validate_otp(user, '123456')

        assert success is False
        assert 'No hay código' in error


# =========================================================================
# get_tokens_for_user
# =========================================================================

@pytest.mark.django_db
class TestGetTokensForUser:
    def test_returns_access_and_refresh_tokens(self):
        user = User.objects.create_user(
            username='tok@test.com', email='tok@test.com', password='pass',
        )
        UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_ADMIN, is_onboarded=True,
        )

        tokens = get_tokens_for_user(user)

        assert 'access' in tokens
        assert 'refresh' in tokens
        assert isinstance(tokens['access'], str)
        assert len(tokens['access']) > 20

    def test_includes_custom_claims_for_user_with_profile(self):
        user = User.objects.create_user(
            username='claims@test.com', email='claims@test.com', password='pass',
        )
        UserProfile.objects.create(
            user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True,
        )

        tokens = get_tokens_for_user(user)

        from rest_framework_simplejwt.tokens import AccessToken
        decoded = AccessToken(tokens['access'])
        assert decoded['role'] == 'client'
        assert decoded['is_onboarded'] is True
        assert decoded['email'] == 'claims@test.com'

    def test_works_for_user_without_profile(self):
        user = User.objects.create_user(
            username='noprof@test.com', email='noprof@test.com', password='pass',
        )

        tokens = get_tokens_for_user(user)

        assert 'access' in tokens
        assert 'refresh' in tokens


# =========================================================================
# get_verification_token_for_user
# =========================================================================

@pytest.mark.django_db
class TestGetVerificationTokenForUser:
    def test_returns_token_with_purpose_claim(self):
        user = User.objects.create_user(
            username='vt@test.com', email='vt@test.com', password='pass',
        )

        token_str = get_verification_token_for_user(user)

        from rest_framework_simplejwt.tokens import AccessToken
        decoded = AccessToken(token_str)
        assert decoded['purpose'] == 'verification'
        assert decoded['email'] == 'vt@test.com'


# =========================================================================
# optimize_avatar
# =========================================================================

def _create_test_image(width, height, mode='RGB', fmt='PNG'):
    img = Image.new(mode, (width, height), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    buffer.seek(0)
    return InMemoryUploadedFile(
        file=buffer,
        field_name='avatar',
        name='test.png',
        content_type=f'image/{fmt.lower()}',
        size=buffer.getbuffer().nbytes,
        charset=None,
    )


AVATAR_MAX = 512


class TestOptimizeAvatar:
    def test_resizes_large_landscape_image(self):
        upload = _create_test_image(2400, 1600)

        result = optimize_avatar(upload)

        img = Image.open(result.file)
        assert img.size[0] == AVATAR_MAX
        assert img.size[1] == int(1600 * (AVATAR_MAX / 2400))

    def test_resizes_large_portrait_image(self):
        upload = _create_test_image(1000, 2000)

        result = optimize_avatar(upload)

        img = Image.open(result.file)
        assert img.size[1] == AVATAR_MAX
        assert img.size[0] == int(1000 * (AVATAR_MAX / 2000))

    def test_does_not_upscale_small_image(self):
        upload = _create_test_image(400, 300)

        result = optimize_avatar(upload)

        img = Image.open(result.file)
        assert img.size == (400, 300)

    def test_converts_rgba_to_rgb_jpeg(self):
        upload = _create_test_image(100, 100, mode='RGBA')

        result = optimize_avatar(upload)

        assert result.content_type == 'image/jpeg'
        img = Image.open(result.file)
        assert img.mode == 'RGB'

    def test_converts_palette_mode_to_rgb(self):
        upload = _create_test_image(100, 100, mode='P')

        result = optimize_avatar(upload)

        img = Image.open(result.file)
        assert img.mode == 'RGB'

    def test_output_filename_is_jpg(self):
        upload = _create_test_image(100, 100)

        result = optimize_avatar(upload)

        assert result.name.endswith('.jpg')
