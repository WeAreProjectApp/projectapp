"""Integration coverage for editing Communications MCP drafts in place."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import UserProfile
from content.models import CommunicationMessage, Document, McpConnector
from content.services import communication_service


pytestmark = pytest.mark.django_db
User = get_user_model()
OCCURRED_AT = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)


@pytest.fixture
def communications_connector():
    connector, _ = McpConnector.objects.get_or_create(
        slug='communications',
        defaults={'name': 'Gestor de Comunicaciones'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    return connector, connector.generate_token()


@pytest.fixture
def mcp_superuser():
    return User.objects.create_superuser(
        username='mcp_update_message',
        email='mcp-update-message@example.com',
        password='testpass123',
    )


def make_client(email):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='testpass123',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


def make_thread(actor, email='update-message@example.com'):
    return communication_service.create_thread(
        actor=actor,
        client=make_client(email),
        title='Borrador por corregir',
    )


def make_draft(thread, actor, *, channel=CommunicationMessage.Channel.EMAIL):
    return communication_service.create_message(
        thread=thread,
        actor=actor,
        channel=channel,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=CommunicationMessage.Status.DRAFT,
        subject='Asunto inicial' if channel == CommunicationMessage.Channel.EMAIL else '',
        content='Contenido inicial',
        occurred_at=OCCURRED_AT,
    )


def rpc(method, params=None):
    message = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def call_tool(api_client, token, name, arguments):
    return api_client.post(
        f'/api/mcp/communications/{token}/',
        rpc('tools/call', {'name': name, 'arguments': arguments}),
        format='json',
    )


def payload(response):
    return json.loads(response.data['result']['content'][0]['text'])


def tool_text(response):
    return response.data['result']['content'][0]['text']


def test_tool_catalog_exposes_update_message_schema(
    api_client, communications_connector,
):
    """The published contract states the edit constraint without a root combinator."""
    _, token = communications_connector

    response = api_client.post(
        f'/api/mcp/communications/{token}/',
        rpc('tools/list'),
        format='json',
    )

    tool = next(
        item for item in response.data['result']['tools']
        if item['name'] == 'update_message'
    )
    schema = tool['inputSchema']
    assert schema['required'] == ['message_id']
    assert set(schema['properties']) == {
        'message_id', 'subject', 'content', 'document_ids',
        'reply_to_id', 'occurred_at',
    }
    assert schema['additionalProperties'] is False
    assert not {'anyOf', 'oneOf', 'allOf'} & schema.keys()
    assert 'al menos uno de subject, content, document_ids, reply_to_id u occurred_at' in tool['description']
    assert 'No crea otro mensaje ni envía' in tool['description']


def update_email_message_via_mcp(api_client, token, message):
    corrected_at = OCCURRED_AT + timedelta(hours=1)
    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'subject': 'Asunto corregido',
        'content': 'Contenido corregido',
        'occurred_at': corrected_at.isoformat(),
    })
    return response, payload(response), corrected_at


def test_update_message_returns_corrected_email_content(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si el MCP acepta la corrección pero no devuelve sus valores nuevos."""
    thread = make_thread(mcp_superuser)
    message = make_draft(thread, mcp_superuser)
    _, token = communications_connector

    response, result, corrected_at = update_email_message_via_mcp(
        api_client,
        token,
        message,
    )

    assert response.data['result']['isError'] is False
    assert result['subject'] == 'Asunto corregido'
    assert result['content'] == 'Contenido corregido'
    assert datetime.fromisoformat(
        result['occurred_at'].replace('Z', '+00:00'),
    ) == corrected_at


def test_update_message_preserves_draft_identity(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si el MCP modifica la identidad o los metadatos fijos del borrador."""
    thread = make_thread(mcp_superuser)
    message = make_draft(thread, mcp_superuser)
    original_recorded_at = message.recorded_at
    _, token = communications_connector

    _, result, _ = update_email_message_via_mcp(api_client, token, message)

    message.refresh_from_db()
    assert result['id'] == message.pk
    assert result['thread_id'] == thread.pk
    assert result['channel'] == CommunicationMessage.Channel.EMAIL
    assert result['direction'] == CommunicationMessage.Direction.OUTGOING
    assert result['status'] == CommunicationMessage.Status.DRAFT
    assert message.recorded_at == original_recorded_at


def test_update_message_records_email_revision(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si el MCP actualiza el correo sin registrar la corrección de asunto."""
    thread = make_thread(mcp_superuser)
    message = make_draft(thread, mcp_superuser)
    _, token = communications_connector

    _, result, _ = update_email_message_via_mcp(api_client, token, message)

    assert result['revisions'][0]['changes'][0] == {
        'field': 'subject',
        'old': 'Asunto inicial',
        'new': 'Asunto corregido',
    }


def test_get_thread_returns_updated_draft(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si get_thread devuelve la versión anterior tras una edición MCP."""
    thread = make_thread(mcp_superuser)
    message = make_draft(thread, mcp_superuser)
    _, token = communications_connector

    _, _, corrected_at = update_email_message_via_mcp(api_client, token, message)
    thread_response = call_tool(
        api_client,
        token,
        'get_thread',
        {'thread_id': thread.pk},
    )
    thread_message = next(
        item for item in payload(thread_response)['messages']
        if item['id'] == message.pk
    )
    assert thread_message['subject'] == 'Asunto corregido'
    assert thread_message['content'] == 'Contenido corregido'
    assert datetime.fromisoformat(
        thread_message['occurred_at'].replace('Z', '+00:00'),
    ) == corrected_at
    assert thread_message['revisions'][0]['changes'][0] == {
        'field': 'subject',
        'old': 'Asunto inicial',
        'new': 'Asunto corregido',
    }


def test_update_message_keeps_whatsapp_subject_empty(
    api_client, communications_connector, mcp_superuser,
):
    thread = make_thread(mcp_superuser, 'whatsapp-update@example.com')
    message = make_draft(
        thread,
        mcp_superuser,
        channel=CommunicationMessage.Channel.WHATSAPP,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'content': 'WhatsApp corregido',
    })

    result = payload(response)
    assert result['id'] == message.pk
    assert result['subject'] == ''
    assert result['content'] == 'WhatsApp corregido'
    assert result['status'] == CommunicationMessage.Status.DRAFT


def test_update_message_replaces_related_documents(
    api_client, communications_connector, mcp_superuser,
):
    thread = make_thread(mcp_superuser, 'document-update@example.com')
    message = make_draft(thread, mcp_superuser)
    original = Document.objects.create(
        title='Documento original',
        client_user=thread.client.user,
    )
    replacement = Document.objects.create(
        title='Documento reemplazo',
        client_user=thread.client.user,
    )
    message.documents.add(original, through_defaults={})
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'document_ids': [replacement.pk],
    })

    result = payload(response)
    assert [document['id'] for document in result['documents']] == [replacement.pk]
    assert result['revisions'][0]['changes'] == [{
        'field': 'document_ids',
        'old': [original.pk],
        'new': [replacement.pk],
    }]


def test_update_message_rejects_foreign_client_document_without_changes(
    api_client, communications_connector, mcp_superuser,
):
    thread = make_thread(mcp_superuser, 'document-owner@example.com')
    message = make_draft(thread, mcp_superuser)
    foreign_client = make_client('document-foreign@example.com')
    foreign_document = Document.objects.create(
        title='Documento ajeno',
        client_user=foreign_client.user,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'content': 'No debe persistir',
        'document_ids': [foreign_document.pk],
    })

    message.refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'otro cliente' in tool_text(response)
    assert message.content == 'Contenido inicial'
    assert not message.documents.exists()
    assert not message.revisions.exists()


@pytest.mark.parametrize(
    ('status', 'direction', 'voided_at'),
    [
        (CommunicationMessage.Status.SENT, CommunicationMessage.Direction.OUTGOING, None),
        (CommunicationMessage.Status.RECEIVED, CommunicationMessage.Direction.INCOMING, None),
        (CommunicationMessage.Status.FAILED, CommunicationMessage.Direction.OUTGOING, None),
        (
            CommunicationMessage.Status.DRAFT,
            CommunicationMessage.Direction.OUTGOING,
            timezone.now(),
        ),
    ],
)
def test_update_message_rejects_non_editable_message_states(
    api_client, communications_connector, mcp_superuser,
    status, direction, voided_at,
):
    thread = make_thread(
        mcp_superuser,
        f'mcp-{status}-{direction}-{bool(voided_at)}@example.com',
    )
    message = CommunicationMessage.objects.create(
        thread=thread,
        channel=CommunicationMessage.Channel.WHATSAPP,
        direction=direction,
        status=status,
        subject='',
        content='Contenido protegido',
        occurred_at=OCCURRED_AT,
        created_by=mcp_superuser,
        updated_by=mcp_superuser,
        voided_at=voided_at,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'content': 'Contenido alterado',
    })

    message.refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'borradores salientes activos' in tool_text(response)
    assert message.content == 'Contenido protegido'
    assert not message.revisions.exists()


def test_update_message_requires_message_id(
    api_client, communications_connector,
):
    _, token = communications_connector

    response = call_tool(
        api_client,
        token,
        'update_message',
        {'content': 'Sin identificador'},
    )

    assert response.data['result']['isError'] is True
    assert 'message_id es obligatorio' in tool_text(response)


def test_update_message_requires_an_editable_field(
    api_client, communications_connector, mcp_superuser,
):
    thread = make_thread(mcp_superuser, 'empty-update@example.com')
    message = make_draft(thread, mcp_superuser)
    _, token = communications_connector

    response = call_tool(
        api_client,
        token,
        'update_message',
        {'message_id': message.pk},
    )

    assert response.data['result']['isError'] is True
    assert 'al menos un campo' in tool_text(response)
    assert not message.revisions.exists()


def test_update_message_rejects_reply_from_another_thread(
    api_client, communications_connector, mcp_superuser,
):
    thread = make_thread(mcp_superuser, 'reply-owner@example.com')
    other_thread = make_thread(mcp_superuser, 'reply-other@example.com')
    message = make_draft(thread, mcp_superuser)
    incoming = communication_service.create_message(
        thread=other_thread,
        actor=mcp_superuser,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.INCOMING,
        status=CommunicationMessage.Status.RECEIVED,
        subject='Respuesta ajena',
        content='No corresponde a este hilo',
        occurred_at=OCCURRED_AT,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'reply_to_id': incoming.pk,
    })

    message.refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'mismo hilo' in tool_text(response)
    assert message.reply_to_id is None


def test_update_message_assigns_same_thread_incoming_reply(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si el MCP no mapea reply_to_id al campo interno reply_to."""
    thread = make_thread(mcp_superuser, 'reply-same-thread@example.com')
    message = make_draft(thread, mcp_superuser)
    incoming = communication_service.create_message(
        thread=thread,
        actor=mcp_superuser,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.INCOMING,
        status=CommunicationMessage.Status.RECEIVED,
        subject='Respuesta recibida',
        content='Confirmado',
        occurred_at=OCCURRED_AT - timedelta(hours=1),
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'reply_to_id': incoming.pk,
    })

    result = payload(response)
    message.refresh_from_db()
    assert response.data['result']['isError'] is False
    assert result['reply_to_id'] == incoming.pk
    assert message.reply_to_id == incoming.pk
    assert result['revisions'][0]['changes'] == [{
        'field': 'reply_to_id',
        'old': None,
        'new': incoming.pk,
    }]


def test_update_message_clears_existing_reply_reference(
    api_client, communications_connector, mcp_superuser,
):
    """Falla si el MCP trata reply_to_id nulo como un campo ausente."""
    thread = make_thread(mcp_superuser, 'reply-clear@example.com')
    message = make_draft(thread, mcp_superuser)
    incoming = communication_service.create_message(
        thread=thread,
        actor=mcp_superuser,
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.INCOMING,
        status=CommunicationMessage.Status.RECEIVED,
        subject='Respuesta recibida',
        content='Confirmado',
        occurred_at=OCCURRED_AT - timedelta(hours=1),
    )
    communication_service.update_draft(
        message,
        actor=mcp_superuser,
        reply_to=incoming,
    )
    message.refresh_from_db()
    original_id = message.pk
    message_count = CommunicationMessage.objects.filter(thread=thread).count()
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'reply_to_id': None,
    })

    result = payload(response)
    message.refresh_from_db()
    assert response.data['result']['isError'] is False
    assert result['id'] == original_id
    assert result['reply_to_id'] is None
    assert message.reply_to_id is None
    assert CommunicationMessage.objects.filter(thread=thread).count() == message_count
    assert result['revisions'][0]['changes'] == [{
        'field': 'reply_to_id',
        'old': incoming.pk,
        'new': None,
    }]


@pytest.mark.parametrize(
    ('channel', 'subject', 'error_text'),
    [
        (CommunicationMessage.Channel.EMAIL, '   ', 'asunto es obligatorio'),
        (CommunicationMessage.Channel.WHATSAPP, 'No permitido', 'no llevan asunto'),
    ],
)
def test_update_message_enforces_channel_subject_rule(
    api_client, communications_connector, mcp_superuser,
    channel, subject, error_text,
):
    thread = make_thread(mcp_superuser, f'subject-{channel}@example.com')
    message = make_draft(thread, mcp_superuser, channel=channel)
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'subject': subject,
    })

    message.refresh_from_db()
    assert response.data['result']['isError'] is True
    assert error_text in tool_text(response)
    assert message.subject == ('Asunto inicial' if channel == 'email' else '')
