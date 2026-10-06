"""MCP parity for the administrative Communications actions."""
import json
from datetime import UTC, datetime, timedelta
from importlib import import_module

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model

from accounts.models import Project, UserProfile
from content.models import CommunicationMessage, CommunicationThread, McpConnector, ProjectRetentionContext
from content.services import communication_service


pytestmark = pytest.mark.django_db
User = get_user_model()
OCCURRED_AT = datetime(2026, 9, 2, 15, 0, tzinfo=UTC)


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
        username='mcp_communication_admin',
        email='mcp-communication-admin@example.com',
        password='testpass123',
    )


def make_client(email):
    user = User.objects.create_user(
        username=email,
        email=email,
        password='testpass123',
    )
    return UserProfile.objects.create(user=user, role=UserProfile.ROLE_CLIENT)


@pytest.fixture
def communication_context(mcp_superuser):
    client = make_client('communication-admin@example.com')
    project = Project.objects.create(name='Proyecto principal', client=client.user)
    thread = communication_service.create_thread(
        actor=mcp_superuser,
        client=client,
        project=project,
        title='Conversación administrable',
    )
    return {
        'client': client,
        'project': project,
        'thread': thread,
        'root': project.communication_root_thread,
    }


def make_message(context, actor, *, status=CommunicationMessage.Status.SENT):
    return CommunicationMessage.objects.create(
        thread=context['thread'],
        channel=CommunicationMessage.Channel.EMAIL,
        direction=CommunicationMessage.Direction.OUTGOING,
        status=status,
        subject='Seguimiento',
        content='Contenido histórico',
        occurred_at=OCCURRED_AT,
        created_by=actor,
        updated_by=actor,
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


def call_confirmed_tool(api_client, token, name, arguments):
    preview = call_tool(api_client, token, name, arguments)
    confirmation_id = preview.data['result']['structuredContent']['confirmation_id']
    return call_tool(
        api_client,
        token,
        'confirm_action',
        {'confirmation_id': confirmation_id},
    )


def payload(response):
    result = json.loads(response.data['result']['content'][0]['text'])
    return result.get('result', result) if result.get('confirmed') else result


def tool_text(response):
    return response.data['result']['content'][0]['text']


def test_update_thread_changes_title(
    api_client, communications_connector, communication_context,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_thread', {
        'thread_id': communication_context['thread'].pk,
        'title': 'Título corregido',
    })

    communication_context['thread'].refresh_from_db()
    assert response.data['result']['isError'] is False
    assert payload(response)['title'] == 'Título corregido'
    assert communication_context['thread'].title == 'Título corregido'


def test_update_thread_clears_project(
    api_client, communications_connector, communication_context,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_thread', {
        'thread_id': communication_context['thread'].pk,
        'project_id': None,
    })

    communication_context['thread'].refresh_from_db()
    assert response.data['result']['isError'] is False
    assert payload(response)['project_id'] is None
    assert communication_context['thread'].project_id is None


def test_update_thread_rejects_foreign_project(
    api_client, communications_connector, communication_context,
):
    foreign_client = make_client('foreign-project@example.com')
    foreign_project = Project.objects.create(
        name='Proyecto ajeno',
        client=foreign_client.user,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_thread', {
        'thread_id': communication_context['thread'].pk,
        'project_id': foreign_project.pk,
    })

    communication_context['thread'].refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'no pertenece al cliente' in tool_text(response)
    assert communication_context['thread'].project_id == communication_context['project'].pk


def test_update_thread_rejects_closed_thread(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    communication_service.close_thread(
        communication_context['thread'],
        actor=mcp_superuser,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_thread', {
        'thread_id': communication_context['thread'].pk,
        'title': 'No debe guardarse',
    })

    communication_context['thread'].refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'Reabre el hilo' in tool_text(response)
    assert communication_context['thread'].title == 'Conversación administrable'


def test_close_thread_sets_closed_state(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'close_thread', {
        'thread_id': communication_context['thread'].pk,
    })

    communication_context['thread'].refresh_from_db()
    assert payload(response)['status'] == CommunicationThread.Status.CLOSED
    assert communication_context['thread'].closed_at is not None
    assert communication_context['thread'].updated_by.username == 'mcp_communications'


def test_close_thread_rejects_closed_state(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    communication_service.close_thread(
        communication_context['thread'],
        actor=mcp_superuser,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'close_thread', {
        'thread_id': communication_context['thread'].pk,
    })

    assert response.data['result']['isError'] is True
    assert 'ya está cerrado' in tool_text(response)


def test_reopen_thread_sets_open_state(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    communication_service.close_thread(
        communication_context['thread'],
        actor=mcp_superuser,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'reopen_thread', {
        'thread_id': communication_context['thread'].pk,
    })

    communication_context['thread'].refresh_from_db()
    assert payload(response)['status'] == CommunicationThread.Status.OPEN
    assert communication_context['thread'].closed_at is None


def test_archive_thread_sets_archive_state(
    api_client, communications_connector, communication_context,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'archive_thread', {
        'thread_id': communication_context['thread'].pk,
    })

    communication_context['thread'].refresh_from_db()
    assert payload(response)['is_archived'] is True
    assert communication_context['thread'].archived_at is not None


def test_archive_thread_rejects_project_root(
    api_client, communications_connector, communication_context,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'archive_thread', {
        'thread_id': communication_context['root'].pk,
    })

    communication_context['root'].refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'comunicación madre' in tool_text(response)
    assert communication_context['root'].is_archived is False


def test_list_threads_filters_archived_scope(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    communication_service.archive_thread(
        communication_context['thread'],
        actor=mcp_superuser,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'list_threads', {
        'scope': 'archived',
    })

    assert [item['id'] for item in payload(response)['results']] == [
        communication_context['thread'].pk,
    ]


def test_unarchive_thread_clears_archive_state(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    communication_service.archive_thread(
        communication_context['thread'],
        actor=mcp_superuser,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'unarchive_thread', {
        'thread_id': communication_context['thread'].pk,
    })

    communication_context['thread'].refresh_from_db()
    assert payload(response)['is_archived'] is False
    assert communication_context['thread'].archived_at is None


def test_delete_draft_removes_message(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(
        communication_context,
        mcp_superuser,
        status=CommunicationMessage.Status.DRAFT,
    )
    _, token = communications_connector

    response = call_confirmed_tool(api_client, token, 'delete_draft', {
        'message_id': message.pk,
    })

    assert payload(response) == {
        'deleted': True,
        'id': message.pk,
        'thread_id': communication_context['thread'].pk,
    }
    assert not CommunicationMessage.objects.filter(pk=message.pk).exists()


def test_delete_draft_rejects_sent_message(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(communication_context, mcp_superuser)
    _, token = communications_connector

    response = call_confirmed_tool(api_client, token, 'delete_draft', {
        'message_id': message.pk,
    })

    assert response.data['result']['isError'] is True
    assert 'borradores activos' in tool_text(response)
    assert CommunicationMessage.objects.filter(pk=message.pk).exists()


def test_mcp_rejects_deleting_retained_draft(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    """Fails if MCP can delete a retained draft after its project has been removed."""
    message = make_message(
        communication_context,
        mcp_superuser,
        status=CommunicationMessage.Status.DRAFT,
    )
    context = ProjectRetentionContext.objects.create(
        client=communication_context['client'].user,
        original_project_id=communication_context['project'].pk,
        project_name=communication_context['project'].name,
        retained_records={},
        created_by=mcp_superuser,
    )
    CommunicationThread.objects.filter(pk=communication_context['thread'].pk).update(
        project=None,
        retention_context=context,
    )
    _, token = communications_connector

    response = call_confirmed_tool(api_client, token, 'delete_draft', {
        'message_id': message.pk,
    })

    assert response.data['result']['isError'] is True
    assert 'sólo permiten consulta' in tool_text(response)
    assert CommunicationMessage.objects.filter(pk=message.pk).exists()


def test_mcp_rejects_updating_retained_draft(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    """Fails if MCP can edit a retained draft after project deletion."""
    message = make_message(
        communication_context,
        mcp_superuser,
        status=CommunicationMessage.Status.DRAFT,
    )
    context = ProjectRetentionContext.objects.create(
        client=communication_context['client'].user,
        original_project_id=communication_context['project'].pk,
        project_name=communication_context['project'].name,
        retained_records={},
        created_by=mcp_superuser,
    )
    CommunicationThread.objects.filter(pk=communication_context['thread'].pk).update(
        project=None,
        retention_context=context,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'update_message', {
        'message_id': message.pk,
        'content': 'Cambio prohibido',
    })

    message.refresh_from_db()
    assert response.data['result']['isError'] is True
    assert 'sólo permiten consulta' in tool_text(response)
    assert message.content == 'Contenido histórico'


def test_void_message_records_reason(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(communication_context, mcp_superuser)
    _, token = communications_connector

    response = call_confirmed_tool(api_client, token, 'void_message', {
        'message_id': message.pk,
        'reason': 'Duplicado registrado por error',
    })

    message.refresh_from_db()
    assert payload(response)['void_reason'] == 'Duplicado registrado por error'
    assert message.voided_at is not None
    assert message.voided_by.username == 'mcp_communications'
    assert message.content == 'Contenido histórico'


def test_void_message_rejects_draft(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(
        communication_context,
        mcp_superuser,
        status=CommunicationMessage.Status.DRAFT,
    )
    _, token = communications_connector

    response = call_confirmed_tool(api_client, token, 'void_message', {
        'message_id': message.pk,
        'reason': 'No aplica',
    })

    assert response.data['result']['isError'] is True
    assert 'Elimina el borrador' in tool_text(response)


def test_correct_message_date_appends_correction(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(communication_context, mcp_superuser)
    corrected_at = OCCURRED_AT + timedelta(hours=2)
    _, token = communications_connector

    response = call_tool(api_client, token, 'correct_message_date', {
        'message_id': message.pk,
        'occurred_at': corrected_at.isoformat(),
        'reason': 'Hora confirmada con el cliente',
    })

    result = payload(response)
    correction = result['date_corrections'][0]
    message.refresh_from_db()
    assert message.occurred_at == corrected_at
    assert correction['reason'] == 'Hora confirmada con el cliente'
    assert correction['corrected_by_name'] == 'MCP Gestor de Comunicaciones'


def test_correct_message_date_rejects_draft(
    api_client, communications_connector, communication_context, mcp_superuser,
):
    message = make_message(
        communication_context,
        mcp_superuser,
        status=CommunicationMessage.Status.DRAFT,
    )
    _, token = communications_connector

    response = call_tool(api_client, token, 'correct_message_date', {
        'message_id': message.pk,
        'occurred_at': (OCCURRED_AT + timedelta(hours=1)).isoformat(),
        'reason': 'No debe guardarse',
    })

    assert response.data['result']['isError'] is True
    assert 'Edita el borrador' in tool_text(response)
    assert not message.date_corrections.exists()


def test_action_rejects_unknown_field(
    api_client, communications_connector, communication_context,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'close_thread', {
        'thread_id': communication_context['thread'].pk,
        'force': True,
    })

    assert response.data['result']['isError'] is True
    assert 'force' in tool_text(response)
    assert communication_context['thread'].status == CommunicationThread.Status.OPEN


def test_action_rejects_boolean_identifier(
    api_client, communications_connector,
):
    _, token = communications_connector

    response = call_tool(api_client, token, 'close_thread', {
        'thread_id': True,
    })

    assert response.data['result']['isError'] is True
    assert 'número entero' in tool_text(response)


def test_description_refresh_preserves_connector_credentials(
    communications_connector,
):
    connector, _ = communications_connector
    connector.token_hash = 'a' * 64
    connector.token_prefix = 'existing'
    connector.last_used_at = OCCURRED_AT
    connector.save(update_fields=['token_hash', 'token_prefix', 'last_used_at'])
    migration = import_module(
        'content.migrations.0239_expand_communications_mcp_parity',
    )

    migration.update_communications_description(django_apps, None)

    connector.refresh_from_db()
    assert connector.is_active is True
    assert connector.token_hash == 'a' * 64
    assert connector.token_prefix == 'existing'
    assert connector.last_used_at == OCCURRED_AT
    assert connector.description == migration.NEW_DESCRIPTION
