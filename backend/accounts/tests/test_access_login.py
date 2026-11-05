"""Access-login regression coverage for authorized existing accounts only."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.access_models import (
    AccessEvent,
    AccessRateBucket,
    GoogleIdentity,
    LoginChallenge,
)
from accounts.models import UserProfile
from accounts.services import access
from accounts.services.google_access import verify_google
from accounts.services.tokens import get_tokens_for_user
from accounts.tasks_access import deliver_login_code

pytestmark = pytest.mark.django_db
User = get_user_model()
REQUEST_URL = "/api/auth/platform/email-request/"
VERIFY_URL = "/api/auth/platform/email-verify/"


def make_account(*, email, active=True, staff=False, superuser=False, onboarded=True):
    """Create a platform account with the authorization state under test."""
    user = User.objects.create_user(
        username=email,
        email=email,
        password="Initial-pass-123",
        is_active=active,
        is_staff=staff,
        is_superuser=superuser,
    )
    UserProfile.objects.create(
        user=user,
        role=UserProfile.ROLE_ADMIN if staff else UserProfile.ROLE_CLIENT,
        is_onboarded=onboarded,
    )
    return user


def access_request(user_agent="Test browser"):
    """Build a stable request identity for access-service calls."""
    request = RequestFactory().post(
        "/", REMOTE_ADDR="198.51.100.31", HTTP_USER_AGENT=user_agent
    )
    return request


def request_unknown_emails(count):
    """Fill the per-IP request bucket without involving an authorized account."""
    request = access_request()
    for index in range(count):
        access.request_code(
            email=f"unknown-{index}@example.com",
            surface="platform",
            browser=f"browser-{index}",
            request=request,
        )


def create_client_accounts(count, start=0):
    """Create a deterministic range of client accounts for list-query checks."""
    return [
        make_account(email=f"list-client-{index}@example.com")
        for index in range(start, start + count)
    ]


def issued_code(challenge):
    """Deliver locally and retain the synthetic test code only in this process."""
    captured = {}

    def capture_delivery(**kwargs):
        captured["body"] = kwargs["body"]
        return 1

    with patch(
        "accounts.tasks_access.EmailDeliveryGateway.send_plain",
        side_effect=capture_delivery,
    ):
        deliver_login_code.call_local(str(challenge.pk))
    return captured["body"].split()[5].rstrip(".")


def reject_code_five_times(challenge, code):
    """Consume every permitted failed attempt against one challenge."""
    for _ in range(5):
        with pytest.raises(ValidationError):
            access.verify_code(
                challenge_id=challenge.pk,
                code=code,
                surface="platform",
                browser="browser",
            )


@pytest.fixture
def captcha_passes(monkeypatch):
    """Let tests isolate access authorization after the captcha boundary succeeds."""
    monkeypatch.setattr("accounts.views_access.verify_captcha", lambda _token: None)


@pytest.fixture(autouse=True)
def suppress_queued_login_delivery(monkeypatch):
    """Keep request tests at the boundary; task delivery is exercised locally below."""
    monkeypatch.setattr(
        "accounts.tasks_access.deliver_login_code", lambda _challenge_id: None
    )


def test_email_request_keeps_account_existence_private(captcha_passes):
    """Fails if the request response reveals whether an account may access the platform."""
    enabled = make_account(email="enabled@example.com")
    make_account(email="disabled@example.com", active=False)
    client = APIClient()

    enabled_response = client.post(
        REQUEST_URL, {"email": enabled.email, "recaptcha_token": "valid"}, format="json"
    )
    missing_response = client.post(
        REQUEST_URL,
        {"email": "missing@example.com", "recaptcha_token": "valid"},
        format="json",
    )
    disabled_response = client.post(
        REQUEST_URL,
        {"email": "disabled@example.com", "recaptcha_token": "valid"},
        format="json",
    )

    payloads = [
        response.json()
        for response in (enabled_response, missing_response, disabled_response)
    ]
    assert [
        response.status_code
        for response in (enabled_response, missing_response, disabled_response)
    ] == [200, 200, 200]
    assert [
        {key: payload[key] for key in ("detail", "expires_in", "retry_after")}
        for payload in payloads
    ] == [
        {"detail": access.GENERIC_NOTICE, "expires_in": 600, "retry_after": 60},
    ] * 3
    assert list(
        LoginChallenge.objects.filter(user=enabled).values_list("surface", flat=True)
    ) == ["platform"]
    assert LoginChallenge.objects.filter(user__isnull=True).count() == 2


def test_anonymous_access_operations_require_csrf_token():
    """Fails if anonymous code endpoints accept browser posts without CSRF protection."""
    client = APIClient(enforce_csrf_checks=True)

    request_response = client.post(
        REQUEST_URL,
        {"email": "person@example.com", "recaptcha_token": "valid"},
        format="json",
    )
    verify_response = client.post(
        VERIFY_URL,
        {"challenge_id": "00000000-0000-0000-0000-000000000000", "code": "000000"},
        format="json",
    )

    assert request_response.status_code == 403
    assert verify_response.status_code == 403


def test_email_request_rate_limit_is_shared_by_surface():
    """Fails if a browser can evade the email cooldown by switching access surfaces."""
    user = make_account(email="limited@example.com", staff=True)
    request = access_request()

    first = access.request_code(
        email=user.email, surface="panel", browser="browser", request=request
    )
    second = access.request_code(
        email=user.email, surface="platform", browser="browser", request=request
    )

    assert first["retry_after"] == 60
    assert second["retry_after"] == 60
    assert second["detail"] == first["detail"] == access.GENERIC_NOTICE
    assert second["expires_in"] == first["expires_in"] == 600
    assert second["challenge_id"] != first["challenge_id"]
    assert LoginChallenge.objects.filter(user=user).count() == 1


def test_ip_rate_limit_blocks_another_account_after_thirty_requests():
    """Fails if one connection can flood a different authorized inbox after the IP window fills."""
    target = make_account(email="ip-target@example.com")
    request_unknown_emails(30)

    response = access.request_code(
        email=target.email,
        surface="platform",
        browser="target",
        request=access_request(),
    )

    assert response["detail"] == access.GENERIC_NOTICE
    assert LoginChallenge.objects.filter(user=target).count() == 0


def test_access_list_query_count_does_not_grow_with_accounts():
    """Fails if showing more authorized accounts adds one access-event query per row."""
    actor = make_account(email="list-owner@example.com", staff=True, superuser=True)
    create_client_accounts(1)

    with CaptureQueriesContext(connection) as one_account_queries:
        access.list_accesses(actor, {})
    create_client_accounts(19, start=1)
    with CaptureQueriesContext(connection) as twenty_account_queries:
        access.list_accesses(actor, {})

    assert len(twenty_account_queries) == len(one_account_queries)


@freeze_time("2026-11-05 12:00:00")
def test_expired_code_is_rejected_before_access():
    """Fails if an expired one-time code can still authenticate an account."""
    user = make_account(email="expired@example.com")
    response = access.request_code(
        email=user.email,
        surface="platform",
        browser="browser",
        request=access_request(),
    )
    challenge = LoginChallenge.objects.get(pk=response["challenge_id"])
    code = issued_code(challenge)
    LoginChallenge.objects.filter(pk=challenge.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    with pytest.raises(ValidationError, match="código no es válido"):
        access.verify_code(
            challenge_id=challenge.pk, code=code, surface="platform", browser="browser"
        )


def test_fifth_wrong_code_attempt_closes_the_challenge():
    """Fails if repeated invalid codes leave a challenge available for brute-force attempts."""
    user = make_account(email="attempts@example.com")
    response = access.request_code(
        email=user.email,
        surface="platform",
        browser="browser",
        request=access_request(),
    )
    challenge = LoginChallenge.objects.get(pk=response["challenge_id"])
    delivered = issued_code(challenge)
    wrong_code = f"{(int(delivered) + 1) % 1_000_000:06d}"

    reject_code_five_times(challenge, wrong_code)

    challenge.refresh_from_db()
    assert challenge.attempts == 5
    assert challenge.closed is True
    assert challenge.code_digest == ""


def test_replaced_code_cannot_authenticate():
    """Fails if requesting a new code leaves the prior code usable."""
    user = make_account(email="replaced@example.com")
    first = access.request_code(
        email=user.email,
        surface="platform",
        browser="browser",
        request=access_request(),
    )
    old_challenge = LoginChallenge.objects.get(pk=first["challenge_id"])
    old_code = issued_code(old_challenge)
    AccessRateBucket.objects.update(requests=[0])
    access.request_code(
        email=user.email,
        surface="platform",
        browser="new-browser",
        request=access_request(),
    )

    with pytest.raises(ValidationError, match="código no es válido"):
        access.verify_code(
            challenge_id=old_challenge.pk,
            code=old_code,
            surface="platform",
            browser="browser",
        )


def test_code_is_consumed_after_successful_verification():
    """Fails if a verified code can be replayed to create a second session."""
    user = make_account(email="consumed@example.com")
    response = access.request_code(
        email=user.email,
        surface="platform",
        browser="browser",
        request=access_request(),
    )
    challenge = LoginChallenge.objects.get(pk=response["challenge_id"])
    code = issued_code(challenge)

    authenticated = access.verify_code(
        challenge_id=challenge.pk, code=code, surface="platform", browser="browser"
    )

    assert authenticated.pk == user.pk
    with pytest.raises(ValidationError, match="código no es válido"):
        access.verify_code(
            challenge_id=challenge.pk, code=code, surface="platform", browser="browser"
        )
    challenge.refresh_from_db()
    assert challenge.code_digest == ""
    assert challenge.code_digest != code


def test_google_login_requires_a_matching_authorized_email(settings):
    """Fails if Google creates or links an identity for an unknown local account."""
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    nonce = access.digest("browser-nonce")
    payload = {
        "iss": "accounts.google.com",
        "email_verified": True,
        "email": "missing-google@example.com",
        "sub": "google-subject",
        "nonce": "browser-nonce",
        "hd": "example.com",
    }

    with (
        patch("google.oauth2.id_token.verify_oauth2_token", return_value=payload),
        pytest.raises(PermissionDenied),
    ):
        verify_google("credential", nonce, "platform")

    assert not GoogleIdentity.objects.filter(subject="google-subject").exists()


def test_google_login_rejects_mismatched_nonce(settings):
    """Fails if a replayed Google credential can bypass the browser nonce."""
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    user = make_account(email="google@example.com")
    payload = {
        "iss": "accounts.google.com",
        "email_verified": True,
        "email": user.email,
        "sub": "google-subject",
        "nonce": "wrong-browser-nonce",
        "hd": "example.com",
    }

    with (
        patch("google.oauth2.id_token.verify_oauth2_token", return_value=payload),
        pytest.raises(PermissionDenied),
    ):
        verify_google("credential", access.digest("expected-browser-nonce"), "platform")

    assert not GoogleIdentity.objects.filter(user=user).exists()


def test_google_login_links_matching_gmail_identity(settings):
    """Fails if an authorized Gmail account cannot use its verified Google identity."""
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    user = make_account(email="matching@gmail.com")
    payload = {
        "iss": "https://accounts.google.com",
        "email_verified": True,
        "email": user.email,
        "sub": "matching-subject",
        "nonce": "browser-nonce",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=payload):
        authenticated = verify_google(
            "credential", access.digest("browser-nonce"), "platform"
        )

    assert authenticated.pk == user.pk
    assert GoogleIdentity.objects.get(user=user).subject == "matching-subject"


def test_first_code_login_runs_client_onboarding_once(
    monkeypatch, django_capture_on_commit_callbacks
):
    """Fails if repeated access recreates first-login onboarding notifications."""
    user = make_account(email="new-client@example.com", onboarded=False)
    first_login_notifications = []
    email_verified_notifications = []
    monkeypatch.setattr(
        "accounts.tasks.notify_team_client_first_login_task",
        lambda user_id: first_login_notifications.append(user_id),
    )
    monkeypatch.setattr(
        "accounts.tasks.notify_team_email_validated_task",
        lambda user_id: email_verified_notifications.append(user_id),
    )
    request = SimpleNamespace(
        META={"REMOTE_ADDR": "198.51.100.9", "HTTP_USER_AGENT": "Test browser"}
    )

    with django_capture_on_commit_callbacks(execute=True):
        access.complete_access(user, method="code", surface="platform", request=request)
    with django_capture_on_commit_callbacks(execute=True):
        access.complete_access(user, method="code", surface="platform", request=request)

    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert user.profile.is_onboarded is True
    assert user.has_usable_password() is False
    assert first_login_notifications == [user.pk]
    assert email_verified_notifications == [user.pk]


def test_google_challenge_nonce_is_consumed_after_verification(
    captcha_passes, settings
):
    """Fails if a Google browser challenge can be replayed after its first verification."""
    settings.GOOGLE_OAUTH_CLIENT_ID = "client-id"
    user = make_account(email="google-view@gmail.com")
    client = APIClient()
    client.get("/api/auth/config/")

    challenge = client.post(
        "/api/auth/platform/google-challenge/",
        {"recaptcha_token": "valid"},
        format="json",
    )
    provider_payload = {
        "iss": "accounts.google.com",
        "email_verified": True,
        "email": user.email,
        "sub": "view-subject",
        "nonce": challenge.json()["nonce"],
    }
    with patch(
        "google.oauth2.id_token.verify_oauth2_token", return_value=provider_payload
    ):
        verified = client.post(
            "/api/auth/platform/google-verify/",
            {"credential": "credential"},
            format="json",
        )
        replay = client.post(
            "/api/auth/platform/google-verify/",
            {"credential": "credential"},
            format="json",
        )

    assert challenge.status_code == 200
    assert verified.status_code == 200
    assert replay.status_code == 403


def test_disabling_account_revokes_existing_session_and_tokens():
    """Fails if disabled accounts retain panel sessions or platform tokens."""
    actor = make_account(email="owner@example.com", staff=True, superuser=True)
    user = make_account(email="revoked@example.com", staff=True)
    tokens = get_tokens_for_user(user)
    panel = Client()
    panel.force_login(user)
    access.change_access(user.pk, actor=actor, enabled=False)
    jwt_client = APIClient()

    panel_response = panel.get("/panel/")
    token_response = jwt_client.get(
        "/api/accounts/me/", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}"
    )
    refresh_response = jwt_client.post(
        "/api/accounts/token/refresh/", {"refresh": tokens["refresh"]}, format="json"
    )

    assert panel_response.wsgi_request.user.is_authenticated is False
    assert token_response.status_code == 401
    assert refresh_response.status_code == 401
    assert (
        AccessEvent.objects.filter(user=user, action="disabled", actor=actor).count()
        == 1
    )


def test_reactivated_account_rejects_unversioned_legacy_session():
    """Fails if reactivation revives a session issued before version stamping."""
    actor = make_account(email="legacy-owner@example.com", staff=True, superuser=True)
    user = make_account(email="legacy-session@example.com", staff=True)
    panel = Client()
    panel.force_login(user)
    session = panel.session
    session.pop("access_version", None)
    session.save()

    access.change_access(user.pk, actor=actor, enabled=False)
    access.change_access(user.pk, actor=actor, enabled=True)
    response = panel.get("/panel/")

    assert response.wsgi_request.user.is_authenticated is False


def test_staff_cannot_manage_team_access():
    """Fails if a non-superuser panel operator can change a team account."""
    staff = make_account(email="staff@example.com", staff=True)
    teammate = make_account(email="team@example.com", staff=True)
    client = Client()
    client.force_login(staff)

    response = client.patch(
        f"/api/accounts/access/{teammate.pk}/",
        data='{"enabled": false}',
        content_type="application/json",
    )

    teammate.refresh_from_db()
    assert response.status_code == 403
    assert teammate.is_active is True


def test_staff_can_disable_client_access():
    """Fails if a panel operator loses the permitted ability to disable a client account."""
    staff = make_account(email="client-manager@example.com", staff=True)
    client = make_account(email="managed-client@example.com")

    changed = access.change_access(client.pk, actor=staff, enabled=False)

    assert changed.is_active is False


def test_last_superuser_cannot_be_disabled():
    """Fails if the final enabled superuser can be removed from account recovery."""
    owner = make_account(email="only-owner@example.com", staff=True, superuser=True)
    actor = SimpleNamespace(
        pk=999999,
        is_active=True,
        is_staff=True,
        is_superuser=True,
        profile=SimpleNamespace(role=UserProfile.ROLE_ADMIN),
    )

    with pytest.raises(ValidationError, match="al menos un superusuario"):
        access.change_access(owner.pk, actor=actor, enabled=False)

    owner.refresh_from_db()
    assert owner.is_active is True
