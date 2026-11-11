"""PA-247: confidential messages no longer store a separate subject."""
import json

import pytest

from accounts.services.credential_cipher import decrypt_secret, encrypt_secret
from secure_links import services
from secure_links.models import SecureLink

from .conftest import token_from

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('association', ['none', 'client', 'project'])
def test_message_creation_preserves_optional_associations(staff_client, client_profile, project, association):
    """Falla si el formulario necesita cliente o pierde una asociación válida."""
    associations = {
        'none': {'client': None, 'project': None},
        'client': {'client': client_profile.pk, 'project': None},
        'project': {'client': client_profile.pk, 'project': project.pk},
    }

    response = staff_client.post('/api/secure-links/create/', {
        'title': 'Referencia interna', 'secret_type': 'confidential_message',
        'fields': {'message': 'Texto conservado'}, **associations[association],
    }, format='json')

    assert response.status_code == 201
    link = SecureLink.objects.get(pk=response.data['id'])
    assert (link.client_id, link.project_id) == tuple(associations[association].values())
    assert json.loads(decrypt_secret(link.payload_encrypted)) == {'message': 'Texto conservado'}
    assert (link.language, link.validity_days) == ('es', 7)


def test_message_creation_rejects_removed_subject(staff_client):
    """Falla si el servidor vuelve a cifrar el campo retirado."""
    response = staff_client.post('/api/secure-links/create/', {
        'title': 'Referencia', 'secret_type': 'confidential_message',
        'fields': {'subject': 'Retirado', 'message': 'Mensaje'},
    }, format='json')

    assert response.status_code == 400
    assert not SecureLink.objects.exists()


def test_message_update_rejects_removed_subject(staff_client, make_link):
    """Falla si editar acepta Asunto o altera el contenido tras el rechazo."""
    link, _url = make_link(secret_type='confidential_message', fields={'message': 'Original'})
    original = link.payload_encrypted

    response = staff_client.patch(f'/api/secure-links/{link.pk}/', {
        'fields': {'subject': 'Retirado', 'message': 'Reemplazo'},
    }, format='json')

    link.refresh_from_db()
    assert response.status_code == 400
    assert link.payload_encrypted == original


def test_historical_message_retains_one_time_reveal(make_link):
    """Falla si retirar el catálogo impide abrir un enlace anterior."""
    link, url = make_link(secret_type='confidential_message', fields={'message': 'Original'})
    SecureLink.objects.filter(pk=link.pk).update(
        payload_encrypted=encrypt_secret(json.dumps({'subject': 'Referencia antigua', 'message': 'Original'})),
    )

    revealed, content = services.reveal(token_from(url))

    assert content['fields'] == [{'key': 'message', 'label': 'Mensaje', 'kind': 'textarea', 'value': 'Original'}]
    assert revealed.pk == link.pk
    with pytest.raises(services.SecureLinkError) as error:
        services.reveal(token_from(url))
    assert error.value.code == 'link_consumed'


def test_message_update_persists_only_current_fields(staff_client, make_link):
    """Falla si editar contenido conserva una clave retirada del cifrado previo."""
    link, url = make_link(secret_type='confidential_message', fields={'message': 'Original'})
    SecureLink.objects.filter(pk=link.pk).update(
        payload_encrypted=encrypt_secret(json.dumps({'subject': 'Referencia antigua', 'message': 'Original'})),
    )

    response = staff_client.patch(f'/api/secure-links/{link.pk}/', {
        'fields': {'message': 'Texto actualizado'},
    }, format='json')

    link.refresh_from_db()
    assert response.status_code == 200
    assert json.loads(decrypt_secret(link.payload_encrypted)) == {'message': 'Texto actualizado'}
    assert services.link_url(link) == url
