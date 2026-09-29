"""Manual sharing remains independent from one-time secret consumption."""
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from secure_links import services
from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


def test_mark_sent_records_actor_without_consuming_link(make_link, staff_user):
    link, url = make_link()

    marked = services.mark_sent(link, actor=staff_user)

    assert marked.lifecycle_status == 'sent'
    assert marked.status == 'active'
    assert marked.sent_by == staff_user
    assert marked.sent_at is not None
    assert services.link_url(marked) == url
    assert marked.events.get(kind='marked_sent').actor == staff_user


def test_repeated_mark_preserves_original_acknowledgement(make_link, staff_user):
    link, _ = make_link()
    marked = services.mark_sent(link, actor=staff_user)
    first_sent_at = marked.sent_at

    with freeze_time(first_sent_at + timedelta(hours=1)):
        repeated = services.mark_sent(link, actor=staff_user)

    assert repeated.sent_at == first_sent_at
    assert repeated.events.filter(kind='marked_sent').count() == 1


@pytest.mark.parametrize('state', ['expired', 'consumed', 'revoked'])
def test_mark_rejects_unavailable_links(make_link, staff_user, state):
    link, _ = make_link()
    field = {'expired': 'expires_at', 'consumed': 'consumed_at', 'revoked': 'revoked_at'}[state]
    setattr(link, field, timezone.now() - timedelta(days=1))
    link.save(update_fields=[field])

    with pytest.raises(services.SecureLinkError, match='Sólo puedes') as error:
        services.mark_sent(link, actor=staff_user)

    assert error.value.status == 409
    link.refresh_from_db()
    assert link.sent_at is None
    assert not link.events.filter(kind='marked_sent').exists()


def test_mark_rejects_received_links(make_link, staff_user):
    link, _ = make_link(origin=SecureLink.Origin.PUBLIC)

    with pytest.raises(services.SecureLinkError) as error:
        services.mark_sent(link, actor=staff_user)

    assert error.value.code == 'invalid_send_state'
    assert not link.events.filter(kind='marked_sent').exists()


def test_recipient_reveal_changes_sent_to_opened(make_link, staff_user):
    link, url = make_link()
    services.mark_sent(link, actor=staff_user)

    revealed, _ = services.reveal(token_from(url))

    assert revealed.lifecycle_status == 'opened'
    assert revealed.status == 'consumed'


def test_expiration_takes_precedence_over_sent(make_link, staff_user):
    link, _ = make_link()
    link = services.mark_sent(link, actor=staff_user)

    with freeze_time(link.expires_at):
        assert link.lifecycle_status == 'expired'
        assert list(SecureLink.objects.with_lifecycle_status('expired')) == [link]
        assert not SecureLink.objects.with_lifecycle_status('sent').exists()


def test_reactivation_clears_current_send_acknowledgement(make_link, staff_user):
    link, url = make_link()
    services.mark_sent(link, actor=staff_user)
    services.revoke(link, actor=staff_user)

    activated, current_url = services.reactivate(link, actor=staff_user)

    assert activated.lifecycle_status == 'ready'
    assert activated.sent_at is None
    assert activated.sent_by is None
    assert current_url == url
    assert activated.events.filter(kind='marked_sent').count() == 1


def test_panel_content_does_not_change_delivery_state(make_link, staff_user):
    link, _ = make_link()
    services.mark_sent(link, actor=staff_user)

    services.panel_content(link, actor=staff_user)

    link.refresh_from_db()
    assert link.lifecycle_status == 'sent'


def test_mark_endpoint_returns_only_metadata(staff_client, make_link):
    link, url = make_link()

    response = staff_client.post(f'/api/secure-links/{link.pk}/mark-sent/', {}, format='json')

    assert response.status_code == 200
    assert response.data['lifecycle_status'] == 'sent'
    assert response.data['sent_by'] == link.created_by_id
    assert url not in str(response.data)
    assert CREDENTIALS['password'] not in str(response.data)


@pytest.mark.parametrize('state', ['expired', 'consumed', 'revoked'])
def test_mark_endpoint_rejects_unavailable_links(staff_client, make_link, state):
    link, url = make_link()
    field = {'expired': 'expires_at', 'consumed': 'consumed_at', 'revoked': 'revoked_at'}[state]
    setattr(link, field, timezone.now() - timedelta(days=1))
    link.save(update_fields=[field])

    response = staff_client.post(f'/api/secure-links/{link.pk}/mark-sent/', {}, format='json')

    assert response.status_code == 409
    assert response.data['code'] == 'invalid_send_state'
    assert url not in str(response.data)
    assert CREDENTIALS['password'] not in str(response.data)
    link.refresh_from_db()
    assert link.sent_at is None
    assert not link.events.filter(kind='marked_sent').exists()


@pytest.mark.parametrize('client_fixture', ['api_client', 'regular_client'])
def test_mark_endpoint_rejects_nonstaff(request, client_fixture, make_link):
    link, _ = make_link()
    client = request.getfixturevalue(client_fixture)

    response = client.post(f'/api/secure-links/{link.pk}/mark-sent/', {}, format='json')

    assert response.status_code == 403
    link.refresh_from_db()
    assert link.sent_at is None


def test_panel_lifecycle_filter_preserves_legacy_counts(staff_client, make_link, staff_user):
    ready, _ = make_link(title='Not shared')
    sent, _ = make_link(title='Shared')
    services.mark_sent(sent, actor=staff_user)

    response = staff_client.get('/api/secure-links/', {'lifecycle_status': 'sent'})

    assert response.status_code == 200
    assert [row['id'] for row in response.data['results']] == [sent.pk]
    assert response.data['counts']['active'] == 2
    assert response.data['lifecycle_counts']['ready'] == 1
    assert response.data['lifecycle_counts']['sent'] == 1
    assert response.data['lifecycle_counts']['all'] == 2
    assert ready.lifecycle_status == 'ready'


def test_legacy_active_filter_includes_sent_links(staff_client, make_link, staff_user):
    ready, _ = make_link()
    sent, _ = make_link()
    services.mark_sent(sent, actor=staff_user)

    response = staff_client.get('/api/secure-links/', {'status': 'active'})

    assert {row['id'] for row in response.data['results']} == {ready.pk, sent.pk}


def test_panel_rejects_unknown_lifecycle_filter(staff_client):
    response = staff_client.get('/api/secure-links/', {'lifecycle_status': 'draft'})

    assert response.status_code == 400
