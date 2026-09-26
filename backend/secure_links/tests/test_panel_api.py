"""Panel endpoints: staff-only management of secure links."""

import pytest
from rest_framework.test import APIClient

from secure_links.models import SecureLink, SecureLinkEvent

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db

BASE = '/api/secure-links/'


@pytest.mark.parametrize('path,method', [
    ('', 'get'), ('create/', 'post'), ('1/', 'get'), ('1/content/', 'post'),
    ('1/link/', 'post'), ('1/reactivate/', 'post'), ('1/revoke/', 'post'),
])
def test_panel_endpoints_reject_anonymous_and_non_staff(path, method, regular_client):
    """Falla si alguien sin rol de equipo gestiona o lee enlaces seguros."""
    anonymous = getattr(APIClient(), method)(BASE + path, {}, format='json')
    regular = getattr(regular_client, method)(BASE + path, {}, format='json')

    assert anonymous.status_code == 403 and regular.status_code == 403


def test_create_returns_url_once_and_list_never_exposes_it(staff_client, client_profile, project):
    """Falla si el listado expone el token o el contenido del enlace."""
    created = staff_client.post(BASE + 'create/', {
        'secret_type': 'credentials', 'title': 'Admin portal', 'fields': CREDENTIALS,
        'client': client_profile.pk, 'project': project.pk, 'validity_days': 3,
    }, format='json')
    listing = staff_client.get(BASE)

    token = token_from(created.json()['url'])
    assert created.status_code == 201 and created.json()['client_name'] == 'Ana Cliente'
    assert token not in str(listing.json()) and CREDENTIALS['password'] not in str(listing.json())
    assert listing.json()['counts']['active'] == 1


def test_create_reports_field_errors(staff_client):
    """Falla si el panel guarda un enlace sin el secreto obligatorio."""
    response = staff_client.post(BASE + 'create/', {
        'secret_type': 'credentials', 'title': 'Sin clave', 'fields': {'username': 'admin'},
    }, format='json')

    assert response.status_code == 400 and 'password' in response.json()


def test_panel_view_does_not_consume_and_is_audited(staff_client, make_link):
    """Falla si ver el contenido en el panel gasta el enlace o no deja rastro."""
    link, _url = make_link()

    response = staff_client.post(f'{BASE}{link.pk}/content/')

    link.refresh_from_db()
    assert response.status_code == 200 and response['Cache-Control'] == 'no-store, max-age=0'
    assert link.status == 'active'
    assert link.events.filter(kind=SecureLinkEvent.Kind.PANEL_VIEWED).exists()


def test_copy_link_returns_same_url(staff_client, make_link):
    """Falla si el equipo no puede volver a copiar un enlace ya enviado."""
    link, url = make_link()

    response = staff_client.post(f'{BASE}{link.pk}/link/')

    assert response.json()['url'] == url


def test_reactivate_and_revoke_through_panel(staff_client, make_link):
    """Falla si el panel no puede revocar ni reactivar el mismo enlace."""
    link, url = make_link()

    revoked = staff_client.post(f'{BASE}{link.pk}/revoke/')
    blocked = APIClient().post(BASE + 'public/reveal/', {'token': token_from(url)}, format='json')
    reactivated = staff_client.post(f'{BASE}{link.pk}/reactivate/', {'validity_days': 7}, format='json')
    reopened = APIClient().post(BASE + 'public/reveal/', {'token': token_from(url)}, format='json')

    assert revoked.json()['status'] == 'revoked' and blocked.json()['code'] == 'link_revoked'
    assert reactivated.json()['status'] == 'active' and reactivated.json()['url'] == url
    assert reopened.status_code == 200


def test_received_filter_and_unopened_counter(staff_client, make_link):
    """Falla si los enlaces que envían los clientes no se distinguen en el panel."""
    make_link()
    make_link(origin=SecureLink.Origin.PUBLIC)

    response = staff_client.get(BASE, {'received': 'true'})

    assert response.json()['count'] == 1 and response.json()['unopened_received'] == 1
    assert response.json()['results'][0]['team_only'] is True


def test_detail_includes_events_and_delete_removes_link(staff_client, make_link):
    """Falla si el detalle omite el historial o eliminar deja el contenido."""
    link, _url = make_link()

    detail = staff_client.get(f'{BASE}{link.pk}/')
    deleted = staff_client.delete(f'{BASE}{link.pk}/')

    assert [event['kind'] for event in detail.json()['events']] == ['created']
    assert deleted.status_code == 204 and not SecureLink.objects.exists()


def test_patch_rejects_project_from_other_client(staff_client, make_link, project, db):
    """Falla si un enlace queda asociado a un proyecto de otro cliente."""
    from accounts.models import UserProfile
    from django.contrib.auth import get_user_model

    other_user = get_user_model().objects.create_user(username='otro-cliente')
    other, _ = UserProfile.objects.get_or_create(user=other_user, defaults={'role': UserProfile.ROLE_CLIENT})
    link, _url = make_link()

    response = staff_client.patch(f'{BASE}{link.pk}/', {'client': other.pk, 'project': project.pk}, format='json')

    assert response.status_code == 400 and response.json()['code'] == 'project_client_mismatch'
