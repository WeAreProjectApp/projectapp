"""Idempotency compares normalized input by keyed MAC, never stored plaintext."""

import uuid

import pytest
from django.db import IntegrityError, transaction

from secure_links.models import SecureLink
from secure_links.services import SecureLinkError

from .conftest import CREDENTIALS

pytestmark = pytest.mark.django_db


def test_exact_retry_does_not_disclose_url(create_owned):
    request_id = uuid.uuid4()
    original, _, _ = create_owned(request_id=request_id)

    repeated, url, replayed = create_owned(request_id=request_id)

    assert repeated.pk == original.pk
    assert (url, replayed) == (None, True)
    assert SecureLink.objects.count() == 1
    assert original.events.count() == 1


@pytest.mark.parametrize('change', [
    {'title': 'Otra etiqueta'}, {'fields': {**CREDENTIALS, 'password': 'new-password'}},
    {'validity_days': 1}, {'language': 'en'},
])
def test_changed_input_conflicts(create_owned, change):
    request_id = uuid.uuid4()
    create_owned(request_id=request_id)

    with pytest.raises(SecureLinkError) as error:
        create_owned(request_id=request_id, **change)

    assert (error.value.code, error.value.status) == ('request_id_conflict', 409)
    assert SecureLink.objects.count() == 1


def test_normalized_whitespace_is_the_same_request(create_owned):
    request_id = uuid.uuid4()
    link, _, _ = create_owned(request_id=request_id, title=' Etiqueta ', fields={**CREDENTIALS, 'service': ' Portal '})

    repeated, _, replayed = create_owned(request_id=request_id, title='Etiqueta', fields={**CREDENTIALS, 'service': 'Portal'})

    assert repeated.pk == link.pk
    assert replayed is True


def test_mac_contains_no_secret(create_owned):
    link, _, _ = create_owned()

    assert len(link.creation_request_fingerprint) == 64
    assert CREDENTIALS['password'] not in str(SecureLink.objects.values().get(pk=link.pk))


def test_database_rejects_duplicate_request(create_owned):
    link, _, _ = create_owned()

    with pytest.raises(IntegrityError), transaction.atomic():
        link.pk = None
        link.token_hash = 'different-token-hash'
        link.save(force_insert=True)

    assert SecureLink.objects.count() == 1


def test_fallback_signing_key_can_verify_existing_request(create_owned, settings):
    request_id = uuid.uuid4()
    original_key = settings.SECRET_KEY
    create_owned(request_id=request_id)
    settings.SECRET_KEY = 'test-only-rotated-signing-key'
    settings.SECRET_KEY_FALLBACKS = [original_key]

    _, url, replayed = create_owned(request_id=request_id)

    assert (url, replayed) == (None, True)
