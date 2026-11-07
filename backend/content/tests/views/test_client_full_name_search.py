"""PA-243: the visible client name is searchable on every client surface."""
from datetime import datetime, timezone

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('query', ['PA-216 QA client', 'pa-216 qa client', 'QA client', 'qa-pa216', 'Atlas'])
def test_autocomplete_finds_the_existing_client(admin_client, make_client_profile, query):
    profile = make_client_profile(
        first_name='PA-216 QA', last_name='client',
        email='qa-pa216-client@example.com', company='Atlas',
    )

    response = admin_client.get(reverse('search-proposal-clients'), {'q': query})

    assert response.status_code == 200
    assert [row['id'] for row in response.data] == [profile.pk]
    assert response['X-Total-Count'] == '1'


def test_register_counts_match_the_full_name_result(admin_client, make_client_profile):
    profile = make_client_profile(first_name='PA-216 QA', last_name='client')
    make_client_profile(first_name='Otro', last_name='Cliente')

    listing = admin_client.get(reverse('list-proposal-clients'), {'search': 'PA-216 QA client'})
    counts = admin_client.get(reverse('proposal-client-status-counts'), {'search': 'PA-216 QA client'})

    assert [row['id'] for row in listing.data] == [profile.pk]
    assert counts.data == {'all': 1, 'active': 0, 'orphans': 1, 'archived': 0}


def test_autocomplete_excludes_an_archived_full_name(admin_client, make_client_profile):
    active = make_client_profile(first_name='PA-216 QA', last_name='client')
    make_client_profile(first_name='PA-216 QA', last_name='client', archived_at=datetime(2026, 11, 7, tzinfo=timezone.utc))

    response = admin_client.get(reverse('search-proposal-clients'), {'q': 'PA-216 QA client'})

    assert response.status_code == 200
    assert [row['id'] for row in response.data] == [active.pk]
    assert response['X-Total-Count'] == '1'


def test_full_name_search_keeps_non_admin_access_denied(api_client, make_client_profile):
    profile = make_client_profile()
    api_client.force_authenticate(user=profile.user)

    response = api_client.get(reverse('search-proposal-clients'), {'q': 'PA-216 QA client'})

    assert response.status_code == 403
