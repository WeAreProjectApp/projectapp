"""MCP secret-read confirmations keep confidential values ephemeral."""

import json
from datetime import timedelta

import pytest
from content.models import McpActionIntent, McpConnector, McpCredential, McpRequestLog
from django.utils import timezone
from freezegun import freeze_time

from secure_links import services
from secure_links.models import SecureLink, SecureLinkEvent

from .conftest import CREDENTIALS, token_from

pytestmark = pytest.mark.django_db


@pytest.fixture
def credential_factory():
    """Build active scoped communications credentials."""
    connector, _ = McpConnector.objects.get_or_create(
        slug='communications', defaults={'name': 'Gestor de Comunicaciones'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])

    def create(label, allowed_tools):
        credential = McpCredential.objects.create(
            connector=connector,
            label=label,
            token_hash='placeholder',
            allowed_tools=allowed_tools,
        )
        return credential, credential.generate_token()

    return create


@pytest.fixture
def secret_reader(credential_factory):
    """Return a credential explicitly allowed to read secure-link content."""
    return credential_factory('Secret reader', ['reveal_secure_link_content'])


def call_tool(api_client, token, name, arguments):
    """Call one communications MCP tool through JSON-RPC."""
    return api_client.post(
        f'/api/mcp/communications/{token}/',
        {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': arguments},
        },
        format='json',
    )


def result(response):
    """Return the JSON-RPC result payload."""
    return response.data['result']


def text(response):
    """Return the MCP text representation of a tool response."""
    return result(response)['content'][0]['text']


def error_code(response):
    """Return a structured tool error code."""
    return result(response)['structuredContent']['error']['code']


def _consume_link(link, url):
    """Put a link into its consumed state."""
    services.reveal(token_from(url))


def _expire_link(link, _url):
    """Put a link into its expired state."""
    SecureLink.objects.filter(pk=link.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )


def _revoke_link(link, _url):
    """Put a link into its revoked state."""
    services.revoke(link, actor=link.created_by)


def test_confirmed_secret_read_delivers_once_without_consuming_or_persisting_content(
    api_client, secret_reader, make_link,
):
    """Falla si una lectura MCP consume el enlace o deja el secreto en su recibo."""
    credential, token = secret_reader
    link, _url = make_link()
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    confirmation_id = result(preview)['structuredContent']['confirmation_id']

    confirmed = call_tool(
        api_client, token, 'confirm_action', {'confirmation_id': confirmation_id},
    )
    replay = call_tool(
        api_client, token, 'confirm_action', {'confirmation_id': confirmation_id},
    )

    link.refresh_from_db()
    intent = McpActionIntent.objects.get(pk=confirmation_id)
    content = json.loads(text(confirmed))['result']
    fields = {field['key']: field['value'] for field in content['fields']}
    acknowledgement = {
        'delivered': True,
        'content_available': False,
        'new_confirmation_required': True,
    }
    assert fields['password'] == CREDENTIALS['password']
    assert link.status == 'active'
    assert link.events.filter(
        kind=SecureLinkEvent.Kind.MCP_VIEWED,
        details__credential_id=credential.pk,
    ).exists() is True
    assert intent.result == acknowledgement
    assert json.loads(text(replay))['result'] == acknowledgement
    assert CREDENTIALS['password'] not in text(replay)
    assert CREDENTIALS['password'] not in str(list(McpRequestLog.objects.values()))


def test_confirmation_rechecks_secret_read_permission_before_delivery(
    api_client, secret_reader, make_link,
):
    """Falla si quitar el permiso aún permite entregar un secreto previsualizado."""
    credential, token = secret_reader
    link, _url = make_link()
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    credential.allowed_tools = []
    credential.save(update_fields=['allowed_tools'])

    confirmed = call_tool(
        api_client, token, 'confirm_action',
        {'confirmation_id': result(preview)['structuredContent']['confirmation_id']},
    )

    assert error_code(confirmed) == 'FORBIDDEN'
    assert link.events.filter(kind=SecureLinkEvent.Kind.MCP_VIEWED).exists() is False


@pytest.mark.parametrize(
    ('prepare_link', 'expected_status'),
    [
        (_consume_link, 'consumed'),
        (_expire_link, 'expired'),
        (_revoke_link, 'revoked'),
    ],
)
def test_secret_read_preserves_an_unavailable_public_link_state(
    api_client, secret_reader, make_link, prepare_link, expected_status,
):
    """Falla si una consulta administrativa cambia un enlace vencido, usado o revocado."""
    _credential, token = secret_reader
    link, url = make_link()
    prepare_link(link, url)
    link.refresh_from_db()
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )

    confirmed = call_tool(
        api_client, token, 'confirm_action',
        {'confirmation_id': result(preview)['structuredContent']['confirmation_id']},
    )

    link.refresh_from_db()
    fields = {
        field['key']: field['value']
        for field in json.loads(text(confirmed))['result']['fields']
    }
    assert fields['password'] == CREDENTIALS['password']
    assert link.status == expected_status


def test_cancelled_secret_read_confirmation_does_not_deliver_content(
    api_client, secret_reader, make_link,
):
    """Falla si cancelar una lectura confidencial todavía permite confirmar su entrega."""
    _credential, token = secret_reader
    link, _url = make_link()
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    call_tool(api_client, token, 'cancel_action', {'confirmation_id': confirmation_id})

    confirmed = call_tool(
        api_client, token, 'confirm_action', {'confirmation_id': confirmation_id},
    )

    assert error_code(confirmed) == 'CONFIRMATION_EXPIRED'
    assert link.events.filter(kind=SecureLinkEvent.Kind.MCP_VIEWED).exists() is False


@freeze_time('2030-01-01 12:00:00')
def test_expired_secret_read_confirmation_does_not_deliver_content(
    api_client, secret_reader, make_link,
):
    """Falla si una confirmación vencida todavía entrega contenido confidencial."""
    _credential, token = secret_reader
    link, _url = make_link()
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    confirmation_id = result(preview)['structuredContent']['confirmation_id']
    McpActionIntent.objects.filter(pk=confirmation_id).update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    confirmed = call_tool(
        api_client, token, 'confirm_action', {'confirmation_id': confirmation_id},
    )

    intent = McpActionIntent.objects.get(pk=confirmation_id)
    assert error_code(confirmed) == 'CONFIRMATION_EXPIRED'
    assert intent.status == McpActionIntent.STATUS_EXPIRED
    assert link.events.filter(kind=SecureLinkEvent.Kind.MCP_VIEWED).exists() is False


def test_secret_read_confirmation_rejects_a_foreign_credential(
    api_client, credential_factory, secret_reader, make_link,
):
    """Falla si otra credencial puede confirmar la lectura confidencial ajena."""
    _reader, reader_token = secret_reader
    _other, other_token = credential_factory(
        'Other secret reader', ['reveal_secure_link_content'],
    )
    link, _url = make_link()
    preview = call_tool(
        api_client, reader_token, 'reveal_secure_link_content', {'link_id': link.pk},
    )

    confirmed = call_tool(
        api_client, other_token, 'confirm_action',
        {'confirmation_id': result(preview)['structuredContent']['confirmation_id']},
    )

    assert error_code(confirmed) == 'FORBIDDEN'
    assert link.events.filter(kind=SecureLinkEvent.Kind.MCP_VIEWED).exists() is False


def test_unknown_secure_link_identifier_is_not_persisted_in_mcp_metadata(
    api_client, secret_reader, make_link,
):
    """Falla si un identificador desconocido queda registrado tras rechazar la solicitud."""
    _credential, token = secret_reader
    link, _url = make_link()
    marker = 'malicious-tenant-id'

    rejected = call_tool(api_client, token, 'reveal_secure_link_content', {
        'link_id': link.pk, 'tenant_id': marker,
    })

    assert error_code(rejected) == 'VALIDATION_ERROR'
    assert marker not in str(list(McpRequestLog.objects.values()))
    assert McpActionIntent.objects.exists() is False


def test_decryption_failure_does_not_audit_or_receipt_a_secret_read(
    api_client, secret_reader, make_link,
):
    """Falla si un descifrado fallido deja una lectura ejecutada o auditada."""
    _credential, token = secret_reader
    link, _url = make_link()
    SecureLink.objects.filter(pk=link.pk).update(payload_encrypted='broken-ciphertext')
    preview = call_tool(
        api_client, token, 'reveal_secure_link_content', {'link_id': link.pk},
    )
    confirmation_id = result(preview)['structuredContent']['confirmation_id']

    confirmed = call_tool(
        api_client, token, 'confirm_action', {'confirmation_id': confirmation_id},
    )

    intent = McpActionIntent.objects.get(pk=confirmation_id)
    assert error_code(confirmed) == 'content_unavailable'
    assert intent.status == McpActionIntent.STATUS_PENDING
    assert intent.result is None
    assert link.events.filter(kind=SecureLinkEvent.Kind.MCP_VIEWED).exists() is False
