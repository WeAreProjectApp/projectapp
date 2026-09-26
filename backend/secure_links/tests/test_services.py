"""Service contract: encryption at rest, token handling and link lifecycle."""

from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from secure_links import services
from secure_links.catalog import CatalogError, clean_fields
from secure_links.models import SecureLink, SecureLinkEvent

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


def test_payload_and_token_are_never_stored_in_plaintext(make_link):
    """Falla si la contraseña o el token quedan legibles en la base de datos."""
    link, url = make_link()
    token = token_from(url)
    stored = SecureLink.objects.values().get(pk=link.pk)

    assert CREDENTIALS['password'] not in str(stored)
    assert token not in str(stored)
    assert stored['token_hash'] == SecureLink.hash_token(token)


def test_url_carries_token_in_fragment_with_recipient_locale(make_link, settings):
    """Falla si el token viaja en el path (logs, Referer) o se ignora el idioma."""
    settings.FRONTEND_BASE_URL = 'https://projectapp.co'
    _link, url = make_link(language='en')

    assert url.startswith('https://projectapp.co/en-us/secure-link/view#')
    assert '/view/' not in url


def test_reveal_consumes_once_and_second_attempt_is_gone(make_link):
    """Falla si un enlace de un solo uso puede abrirse dos veces."""
    link, url = make_link()

    _row, content = services.reveal(token_from(url), meta=services.RequestMeta(ip='198.51.100.7', user_agent='UA'))
    with pytest.raises(services.SecureLinkError) as blocked:
        services.reveal(token_from(url))

    values = {field['key']: field['value'] for field in content['fields']}
    link.refresh_from_db()
    assert values['password'] == CREDENTIALS['password']
    assert link.status == 'consumed' and link.consumed_ip == '198.51.100.7'
    assert (blocked.value.code, blocked.value.status) == ('link_consumed', 410)
    assert link.events.filter(kind=SecureLinkEvent.Kind.REVEAL_BLOCKED, details__reason='consumed').exists()


def test_expired_link_cannot_be_revealed(make_link):
    """Falla si un enlace vencido todavía entrega el contenido."""
    _link, url = make_link(validity_days=1)

    with freeze_time(timezone.now() + timedelta(days=1, minutes=1)):
        with pytest.raises(services.SecureLinkError) as blocked:
            services.reveal(token_from(url))

    assert blocked.value.code == 'link_expired'


def test_client_created_link_is_reserved_for_staff(make_link, staff_user):
    """Falla si un enlace enviado por un cliente lo puede abrir cualquiera."""
    link, url = make_link(origin=SecureLink.Origin.PUBLIC)

    with pytest.raises(services.SecureLinkError) as blocked:
        services.reveal(token_from(url))
    services.reveal(token_from(url), staff=True, actor=staff_user)

    assert blocked.value.code == 'staff_only' and blocked.value.status == 403
    link.refresh_from_db()
    assert link.status == 'consumed'


def test_reactivation_reopens_same_link_and_restarts_validity(make_link, staff_user):
    """Falla si reactivar exige un enlace nuevo o conserva el vencimiento viejo."""
    link, url = make_link(validity_days=1)
    services.reveal(token_from(url))

    with freeze_time(timezone.now() + timedelta(days=5)):
        link, same_url = services.reactivate(link, actor=staff_user, validity_days=3)
        _row, content = services.reveal(token_from(url))
        expected_expiry = timezone.now() + timedelta(days=3)

    assert same_url == url and content['fields']
    assert link.activation_count == 2
    assert abs((link.expires_at - expected_expiry).total_seconds()) < 5


def test_rotation_invalidates_previous_link(make_link, staff_user):
    """Falla si regenerar el enlace deja vivo el enlace filtrado."""
    link, old_url = make_link()
    services.revoke(link, actor=staff_user)

    _link, new_url = services.reactivate(link, actor=staff_user, rotate=True)

    assert new_url != old_url
    with pytest.raises(services.SecureLinkError) as missing:
        services.reveal(token_from(old_url))
    assert missing.value.status == 404
    services.reveal(token_from(new_url))


def test_update_audits_field_names_but_not_values(make_link, staff_user):
    """Falla si el historial de edición guarda el secreto en claro."""
    link, _url = make_link()

    link = services.update_link(link, actor=staff_user, fields={**CREDENTIALS, 'password': 'Nueva-Clave-123'})

    event = link.events.get(kind=SecureLinkEvent.Kind.UPDATED)
    assert 'Nueva-Clave-123' not in str(event.details)
    values = {field['key']: field['value'] for field in services.content_for(link)['fields']}
    assert values['password'] == 'Nueva-Clave-123'


def test_catalog_rejects_missing_required_and_unknown_fields():
    """Falla si se guarda un enlace sin el secreto o con campos ajenos al tipo."""
    with pytest.raises(CatalogError) as error:
        clean_fields('credentials', {'username': 'admin', 'color': 'rojo'})

    assert 'password' in error.value.errors and 'fields' in error.value.errors


def test_public_links_cannot_exceed_seven_days(make_link):
    """Falla si un visitante crea un enlace con vigencia de 30 días."""
    with pytest.raises(services.SecureLinkError) as error:
        make_link(origin=SecureLink.Origin.PUBLIC, validity_days=30)

    assert error.value.code == 'invalid_validity'


def test_fake_data_covers_every_state_and_type(settings):
    """Falla si los datos de desarrollo no permiten revisar todos los estados."""
    from django.core.management import call_command

    call_command('create_fake_secure_links', stdout=None)

    assert {link.status for link in SecureLink.objects.all()} == set(SecureLink.STATUSES)
    assert SecureLink.objects.values('secret_type').distinct().count() == 8


def test_corrupted_ciphertext_fails_loudly(make_link):
    """Falla si un contenido que no se puede descifrar se muestra como vacío."""
    link, url = make_link()
    SecureLink.objects.filter(pk=link.pk).update(payload_encrypted='not-a-fernet-token')

    with pytest.raises(services.SecureLinkError) as error:
        services.reveal(token_from(url))

    assert error.value.code == 'content_unavailable'
    link.refresh_from_db()
    assert link.consumed_at is None
