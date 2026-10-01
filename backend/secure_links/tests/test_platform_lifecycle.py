"""Managed links retain evidence and use a new token on every reactivation."""

import pytest

from secure_links import services
from secure_links.models import SecureLink, SecureLinkEvent

from .conftest import token_from
from .test_platform_api import base

pytestmark = pytest.mark.django_db


def test_client_cannot_open_the_secret(create_owned):
    link, url, _ = create_owned()

    with pytest.raises(services.SecureLinkError) as error:
        services.reveal(token_from(url))

    assert (error.value.code, error.value.status) == ('staff_only', 403)
    link.refresh_from_db()
    assert link.consumed_at is None


def test_staff_consumes_owned_link_once(create_owned, staff_user):
    link, url, _ = create_owned()
    services.reveal(token_from(url), staff=True, actor=staff_user)

    with pytest.raises(services.SecureLinkError) as error:
        services.reveal(token_from(url), staff=True, actor=staff_user)

    assert error.value.code == 'link_consumed'
    assert link.events.filter(kind=SecureLinkEvent.Kind.REVEALED).count() == 1


def test_revoke_is_idempotent(platform_client, project, create_owned):
    link, _, _ = create_owned()
    first = platform_client.post(f'{base(project)}{link.pk}/revoke/', {}, format='json')

    second = platform_client.post(f'{base(project)}{link.pk}/revoke/', {}, format='json')

    assert (first.status_code, second.status_code) == (200, 200)
    assert first.data['revoked_at'] == second.data['revoked_at']
    assert link.events.filter(kind=SecureLinkEvent.Kind.REVOKED).count() == 1


def test_reactivation_invalidates_the_old_token(platform_client, project, create_owned, staff_user):
    link, old_url, _ = create_owned()
    services.reveal(token_from(old_url), staff=True, actor=staff_user)
    link.refresh_from_db()

    response = platform_client.post(f'{base(project)}{link.pk}/reactivate/', {
        'expected_updated_at': link.updated_at.isoformat(), 'validity_days': 3,
    }, format='json')

    assert response.status_code == 200
    assert response.data['url'] != old_url
    assert services.public_status(token_from(response.data['url']))['team_only'] is True
    with pytest.raises(services.SecureLinkError) as error:
        services.public_status(token_from(old_url))
    assert error.value.status == 404
    assert link.events.filter(kind=SecureLinkEvent.Kind.REVEALED).count() == 1
    assert link.events.filter(kind=SecureLinkEvent.Kind.ROTATED).count() == 1


def test_stale_reactivation_cannot_rotate_twice(platform_client, project, create_owned):
    link, _, _ = create_owned()
    link = services.revoke(link, actor=link.created_by)
    data = {'expected_updated_at': link.updated_at.isoformat(), 'validity_days': 7}
    platform_client.post(f'{base(project)}{link.pk}/reactivate/', data, format='json')

    second = platform_client.post(f'{base(project)}{link.pk}/reactivate/', data, format='json')

    assert (second.status_code, second.data['code']) == (409, 'version_conflict')
    link.refresh_from_db()
    assert link.activation_count == 2


def test_replacement_preserves_previous_ciphertext(create_owned, client_profile):
    previous, _, _ = create_owned()
    ciphertext = previous.payload_encrypted
    services.revoke(previous, actor=client_profile.user)

    replacement, _, _ = create_owned(replaces=previous.pk, fields={'password': 'Corrected-secret'})

    previous.refresh_from_db()
    assert replacement.replaces_id == previous.pk
    assert previous.payload_encrypted == ciphertext
    assert previous.status == 'revoked'
    assert previous.events.get(kind=SecureLinkEvent.Kind.REPLACED).details == {'replacement_id': replacement.pk}


def test_replacement_requires_revocation(create_owned):
    previous, _, _ = create_owned()

    with pytest.raises(services.SecureLinkError) as error:
        create_owned(replaces=previous.pk)

    assert error.value.code == 'invalid_replacement'
    assert SecureLink.objects.count() == 1


def test_replaced_link_cannot_reactivate(create_owned, client_profile):
    previous, _, _ = create_owned()
    services.revoke(previous, actor=client_profile.user)
    create_owned(replaces=previous.pk)

    with pytest.raises(services.SecureLinkError) as error:
        services.reactivate(previous, actor=client_profile.user)

    assert (error.value.status, error.value.code) == (409, 'invalid_reactivation')
    previous.refresh_from_db()
    assert previous.status == 'revoked'


def test_only_one_direct_replacement_is_allowed(create_owned, client_profile):
    previous, _, _ = create_owned()
    services.revoke(previous, actor=client_profile.user)
    create_owned(replaces=previous.pk)

    with pytest.raises(services.SecureLinkError) as error:
        create_owned(replaces=previous.pk)

    assert error.value.code == 'invalid_replacement'
    assert SecureLink.objects.count() == 2


def test_unavailable_link_url_is_rejected(platform_client, project, create_owned):
    link, _, _ = create_owned()
    services.revoke(link, actor=link.created_by)

    response = platform_client.post(f'{base(project)}{link.pk}/link/', {}, format='json')

    assert response.status_code == 409
    assert 'url' not in response.data


def test_explicit_url_access_is_audited(platform_client, project, create_owned):
    link, url, _ = create_owned()

    response = platform_client.post(f'{base(project)}{link.pk}/link/', {}, format='json')

    assert response.data['url'] == url
    event = link.events.get(kind=SecureLinkEvent.Kind.URL_ACCESSED)
    assert event.details == {'channel': 'platform'}
    assert token_from(url) not in str(event.__dict__)


def test_staff_cannot_move_a_managed_link(create_owned, staff_user):
    link, _, _ = create_owned()

    with pytest.raises(services.SecureLinkError) as error:
        services.update_link(link, actor=staff_user, project=None)

    assert error.value.code == 'immutable_ownership'


def test_staff_reactivation_always_rotates_managed_link(create_owned, staff_user):
    link, url, _ = create_owned()
    services.revoke(link, actor=staff_user)

    _, new_url = services.reactivate(link, actor=staff_user, rotate=False)

    assert new_url != url
