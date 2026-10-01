"""Idempotency compares normalized input by keyed MAC, never stored plaintext."""

import uuid

import pytest
from accounts.models import Project, UserProfile
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from secure_links.models import SecureLink
from secure_links.services import SecureLinkError

from .conftest import CREDENTIALS

pytestmark = pytest.mark.django_db

REQUEST_ID_EXACT_RETRY = uuid.UUID('00000000-0000-4000-8000-000000000001')
REQUEST_ID_CHANGED_INPUT = uuid.UUID('00000000-0000-4000-8000-000000000002')
REQUEST_ID_NORMALIZED_INPUT = uuid.UUID('00000000-0000-4000-8000-000000000003')
REQUEST_ID_FALLBACK_KEY = uuid.UUID('00000000-0000-4000-8000-000000000004')
REQUEST_ID_OTHER_PROJECT = uuid.UUID('00000000-0000-4000-8000-000000000005')
REQUEST_ID_OTHER_OWNER = uuid.UUID('00000000-0000-4000-8000-000000000006')


def test_exact_retry_does_not_disclose_url(create_owned):
    """An identical request reuses the link without returning its URL again."""
    original, _, _ = create_owned(request_id=REQUEST_ID_EXACT_RETRY)

    repeated, url, replayed = create_owned(request_id=REQUEST_ID_EXACT_RETRY)

    assert repeated.pk == original.pk
    assert (url, replayed) == (None, True)
    assert SecureLink.objects.count() == 1
    assert original.events.count() == 1


@pytest.mark.parametrize('change', [
    {'title': 'Otra etiqueta'}, {'fields': {**CREDENTIALS, 'password': 'new-password'}},
    {'validity_days': 1}, {'language': 'en'},
])
def test_changed_input_conflicts(create_owned, change):
    """A reused request ID with changed normalized input returns conflict."""
    create_owned(request_id=REQUEST_ID_CHANGED_INPUT)

    with pytest.raises(SecureLinkError) as error:
        create_owned(request_id=REQUEST_ID_CHANGED_INPUT, **change)

    assert (error.value.code, error.value.status) == ('request_id_conflict', 409)
    assert SecureLink.objects.count() == 1


def test_normalized_whitespace_is_the_same_request(create_owned):
    """Whitespace-only changes reuse the original normalized request."""
    link, _, _ = create_owned(request_id=REQUEST_ID_NORMALIZED_INPUT, title=' Etiqueta ', fields={**CREDENTIALS, 'service': ' Portal '})

    repeated, _, replayed = create_owned(request_id=REQUEST_ID_NORMALIZED_INPUT, title='Etiqueta', fields={**CREDENTIALS, 'service': 'Portal'})

    assert repeated.pk == link.pk
    assert replayed is True


def test_mac_contains_no_secret(create_owned):
    """The stored idempotency MAC is fixed-length and omits credential text."""
    link, _, _ = create_owned()

    assert len(link.creation_request_fingerprint) == 64
    assert CREDENTIALS['password'] not in str(SecureLink.objects.values().get(pk=link.pk))


def test_database_rejects_duplicate_request(create_owned):
    """The database prevents two rows for one owner request ID."""
    link, _, _ = create_owned()
    link.pk = None
    link.token_hash = 'different-token-hash'

    with pytest.raises(IntegrityError), transaction.atomic():
        link.save(force_insert=True)

    assert SecureLink.objects.count() == 1


def test_fallback_signing_key_can_verify_existing_request(create_owned, settings):
    """A fallback signing key recognizes a request made before key rotation."""
    original_key = settings.SECRET_KEY
    create_owned(request_id=REQUEST_ID_FALLBACK_KEY)
    settings.SECRET_KEY = 'test-only-rotated-signing-key'
    settings.SECRET_KEY_FALLBACKS = [original_key]

    _, url, replayed = create_owned(request_id=REQUEST_ID_FALLBACK_KEY)

    assert (url, replayed) == (None, True)


def test_same_request_for_another_owned_project_conflicts(create_owned, client_profile):
    """One owner cannot reuse a request ID to create a different project link."""
    original, _, _ = create_owned(request_id=REQUEST_ID_OTHER_PROJECT)
    other_project = Project.objects.create(client=client_profile.user, name='Otro proyecto propio')

    with pytest.raises(SecureLinkError) as error:
        create_owned(request_id=REQUEST_ID_OTHER_PROJECT, project_id=other_project.pk)

    assert (error.value.code, error.value.status) == ('request_id_conflict', 409)
    assert list(SecureLink.objects.values_list('pk', 'project_id')) == [(original.pk, original.project_id)]


def test_another_owner_has_an_independent_request_namespace(create_owned):
    """Different owners may independently use the same request ID."""
    original, _, _ = create_owned(request_id=REQUEST_ID_OTHER_OWNER)
    other_user = get_user_model().objects.create_user(username='otro-propietario')
    other_owner, _ = UserProfile.objects.get_or_create(user=other_user)
    other_owner.role = UserProfile.ROLE_CLIENT
    other_owner.is_onboarded = True
    other_owner.save(update_fields=['role', 'is_onboarded'])
    other_project = Project.objects.create(client=other_user, name='Proyecto de otro cliente')

    created, url, replayed = create_owned(
        request_id=REQUEST_ID_OTHER_OWNER, owner_id=other_owner.pk, project_id=other_project.pk, actor=other_user,
    )

    assert created.pk != original.pk
    assert (created.owner_id, created.project_id) == (other_owner.pk, other_project.pk)
    assert url is not None
    assert replayed is False
