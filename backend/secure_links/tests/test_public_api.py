"""Anonymous endpoints: status, reveal and client-side creation."""

from unittest.mock import patch

import pytest
from projectapp.recaptcha import CaptchaError
from rest_framework.test import APIClient

from secure_links.models import SecureLink

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db

STATUS_URL = '/api/secure-links/public/status/'
REVEAL_URL = '/api/secure-links/public/reveal/'
CREATE_URL = '/api/secure-links/public/create/'


def _public_payload(**overrides):
    return {
        'secret_type': 'credentials',
        'fields': {'service': 'GoDaddy', 'password': 'Cliente-Clave-1'},
        'creator_name': 'Laura Gómez',
        'creator_email': 'laura@example.com',
        **overrides,
    }


def test_status_does_not_consume_the_link(make_link):
    """Falla si abrir la página (o una vista previa de WhatsApp) gasta el enlace."""
    link, url = make_link()

    response = APIClient().post(STATUS_URL, {'token': token_from(url)}, format='json')

    link.refresh_from_db()
    assert response.status_code == 200
    assert response.json()['status'] == 'active' and response.json()['can_reveal'] is True
    assert 'fields' not in response.json() and link.consumed_at is None


def test_reveal_returns_content_once_with_no_store(make_link):
    """Falla si el contenido se puede cachear o pedir dos veces."""
    _link, url = make_link()
    client = APIClient()

    first = client.post(REVEAL_URL, {'token': token_from(url)}, format='json')
    second = client.post(REVEAL_URL, {'token': token_from(url)}, format='json')

    assert first.status_code == 200 and first['Cache-Control'] == 'no-store, max-age=0'
    assert CREDENTIALS['password'] in str(first.json()['fields'])
    assert second.status_code == 410 and second.json()['code'] == 'link_consumed'


def test_unknown_token_is_not_found():
    """Falla si un token inventado revela algo distinto de 'no existe'."""
    response = APIClient().post(REVEAL_URL, {'token': 'x' * 43}, format='json')

    assert response.status_code == 404 and response.json()['code'] == 'link_not_found'


def test_team_only_link_requires_staff_session(make_link, staff_client):
    """Falla si un tercero abre lo que un cliente le envió a ProjectApp."""
    _link, url = make_link(origin=SecureLink.Origin.PUBLIC)

    anonymous = APIClient().post(REVEAL_URL, {'token': token_from(url)}, format='json')
    staff = staff_client.post(REVEAL_URL, {'token': token_from(url)}, format='json')

    assert anonymous.status_code == 403 and anonymous.json()['code'] == 'staff_only'
    assert staff.status_code == 200


def test_public_create_stores_team_only_link_and_notifies(settings):
    """Falla si la creación del cliente no queda reservada al equipo o no avisa."""
    with patch('secure_links.views.notify_team_secure_link_received') as notify:
        response = APIClient().post(CREATE_URL, _public_payload(), format='json')

    link = SecureLink.objects.get()
    assert response.status_code == 201 and '#' in response.json()['url']
    assert link.origin == SecureLink.Origin.PUBLIC and link.team_only
    assert link.creator_name == 'Laura Gómez' and link.validity_days == 7
    notify.assert_called_once_with(link.pk)


def test_public_create_honeypot_stores_nothing():
    """Falla si un bot que llena el campo oculto logra guardar contenido."""
    response = APIClient().post(CREATE_URL, _public_payload(website='http://spam.example'), format='json')

    assert response.status_code == 201 and 'url' not in response.json()
    assert not SecureLink.objects.exists()


def test_public_create_rejects_failed_captcha():
    """Falla si la creación pública ignora el resultado del captcha."""
    with patch('secure_links.views.verify_captcha', side_effect=CaptchaError('captcha_invalid', 'Captcha')):
        response = APIClient().post(CREATE_URL, _public_payload(), format='json')

    assert response.status_code == 400 and response.json()['code'] == 'captcha_invalid'
    assert not SecureLink.objects.exists()


def test_public_create_rejects_thirty_day_validity():
    """Falla si un visitante mantiene un enlace vivo más de 7 días."""
    response = APIClient().post(CREATE_URL, _public_payload(validity_days=30), format='json')

    assert response.status_code == 400 and response.json()['code'] == 'invalid_validity'


def test_public_create_is_throttled_per_ip():
    """Falla si un script puede crear enlaces sin límite desde una IP."""
    client = APIClient()
    with patch('secure_links.views.notify_team_secure_link_received'):
        statuses = [client.post(CREATE_URL, _public_payload(), format='json').status_code for _ in range(11)]

    assert statuses[:10] == [201] * 10 and statuses[10] == 429


def test_team_notice_email_never_contains_link_or_content(mailoutbox, settings):
    """Falla si el correo al equipo filtra la URL o el secreto."""
    from secure_links.tasks import send_received_notice

    settings.NOTIFICATION_EMAIL = 'equipo@projectapp.co'
    response = APIClient().post(CREATE_URL, _public_payload(), format='json')
    link = SecureLink.objects.get()
    mailoutbox.clear()

    assert send_received_notice(link.pk) is True
    message = mailoutbox[0]
    body = message.body + str(message.alternatives)
    assert token_from(response.json()['url']) not in body
    assert 'Cliente-Clave-1' not in body and f'link={link.pk}' in body
