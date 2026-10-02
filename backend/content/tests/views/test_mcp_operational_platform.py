"""Cross-cutting behavior of the operational MCP platform."""
import base64
import hashlib
import io
import zipfile
from datetime import date, timedelta
from urllib.parse import urlsplit

import pytest
from django.core.files.base import ContentFile
from django.utils import timezone as tz
from rest_framework.test import APIRequestFactory

from content.mcp.common_tools import build_common_tools
from content.mcp.confirmation import cancel_action, confirm_action, preview_sensitive_action
from content.mcp.context import McpExecutionContext, use_mcp_context
from content.mcp.operation_catalogs import CARD_PARITY_TOOLS, LEDGER_PARITY_TOOLS
from content.mcp.panel_bridge import panel_operation
from content.mcp.principal import service_actor_for_connector
from content.mcp.protocol import ToolError, handle_message
from content.mcp.registry import normalize_tools
from content.mcp.upload_tools import (
    abort_upload,
    begin_upload,
    complete_upload,
    consume_upload,
    store_artifact,
    upload_asset_chunk,
)
from content.models import (
    CreditCardStatement,
    McpActionIntent,
    McpConnector,
    McpCredential,
    McpRequestLog,
    McpUpload,
    Task,
)


pytestmark = pytest.mark.django_db


VALID_UPLOAD_ARGUMENTS = {
    'filename': 'evidencia.txt',
    'content_type': 'text/plain',
    'size': 1,
    'sha256': hashlib.sha256(b'x').hexdigest(),
}
VALID_CHUNK = base64.b64encode(b'x').decode('ascii')
VALID_CHUNK_HASH = hashlib.sha256(b'x').hexdigest()
NO_UPLOAD_FILE = object()
UNKNOWN_CONFIRMATION_ID = '00000000-0000-0000-0000-000000000001'


def _upload_row(
    context,
    *,
    body=NO_UPLOAD_FILE,
    filename='evidencia.txt',
    content_type='text/plain',
    expected_size=None,
    expected_sha256=None,
    received_size=None,
    next_chunk_index=0,
    status=McpUpload.STATUS_PENDING,
    expires_at=None,
):
    payload = b'x' if body is NO_UPLOAD_FILE else body
    upload = McpUpload.objects.create(
        connector=context.connector,
        credential=context.credential,
        filename=filename,
        content_type=content_type,
        expected_size=len(payload) if expected_size is None else expected_size,
        expected_sha256=(
            hashlib.sha256(payload).hexdigest()
            if expected_sha256 is None else expected_sha256
        ),
        received_size=(
            0 if body is NO_UPLOAD_FILE else len(payload)
        ) if received_size is None else received_size,
        next_chunk_index=next_chunk_index,
        status=status,
        expires_at=expires_at or (tz.now() + timedelta(minutes=10)),
    )
    if body is not NO_UPLOAD_FILE:
        upload.file.save(filename, ContentFile(payload), save=True)
    return upload


def _incomplete_docx_payload():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
    return buffer.getvalue()


def _rpc(method, params=None, msg_id=1):
    message = {'jsonrpc': '2.0', 'id': msg_id, 'method': method}
    if params is not None:
        message['params'] = params
    return message


def _modern_rpc(method, params=None, msg_id=1):
    payload = dict(params or {})
    payload['_meta'] = {
        'io.modelcontextprotocol/protocolVersion': '2026-07-28',
        'io.modelcontextprotocol/clientCapabilities': {},
        'io.modelcontextprotocol/clientInfo': {
            'name': 'projectapp-tests',
            'version': '1.0.0',
        },
    }
    return _rpc(method, payload, msg_id)


def _call(api_client, slug, token, name, arguments=None, *, bearer=False):
    url = f'/api/mcp/{slug}/' if bearer else f'/api/mcp/{slug}/{token}/'
    headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'} if bearer else {}
    return api_client.post(
        url,
        _rpc('tools/call', {'name': name, 'arguments': arguments or {}}),
        format='json',
        **headers,
    )


@pytest.fixture
def tasks_connector():
    connector, _ = McpConnector.objects.get_or_create(
        slug='tasks', defaults={'name': 'Gestor de Tareas'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()
    return connector, token


@pytest.fixture
def upload_context(settings, tmp_path, tasks_connector):
    settings.MEDIA_ROOT = tmp_path
    connector, _ = tasks_connector
    return McpExecutionContext(
        connector=connector,
        credential=connector.credentials.get(label='Default'),
        request_id='upload-safety-request',
        request=APIRequestFactory().get('/', HTTP_HOST='testserver'),
    )


@pytest.fixture
def accounting_context(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    connector, _ = McpConnector.objects.get_or_create(
        slug='accounting', defaults={'name': 'Contabilidad'},
    )
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    connector.generate_token()
    return McpExecutionContext(
        connector=connector,
        credential=connector.credentials.get(label='Default'),
        request_id='accounting-bridge-request',
        actor=service_actor_for_connector(connector),
        request=APIRequestFactory().get('/', HTTP_HOST='testserver'),
    )


@pytest.fixture
def confirmation_runtime(tasks_connector):
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')
    calls = []

    def destroy(arguments):
        calls.append(arguments['record_id'])
        return {'deleted': arguments['record_id']}

    sensitive = {
        'name': 'delete_record',
        'description': 'Elimina de forma controlada el registro solicitado.',
        'risk': 'sensitive',
        'requires_confirmation': True,
        'input_schema': {
            'type': 'object',
            'properties': {'record_id': {'type': 'integer'}},
            'required': ['record_id'],
        },
        'handler': destroy,
    }
    tools = []
    tools.extend(normalize_tools([
        sensitive,
        *build_common_tools('tasks', lambda: tools),
    ], 'tasks'))
    context = McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id='test-request-id',
    )
    return tools, context, calls


def _preview(tools, context):
    with use_mcp_context(context):
        _, response = handle_message(
            _rpc('tools/call', {
                'name': 'delete_record',
                'arguments': {'record_id': 42},
            }),
            tools,
            context=context,
        )
    return response['result']['structuredContent']


def _runtime_call(tools, context, name, arguments):
    with use_mcp_context(context):
        _, response = handle_message(
            _rpc('tools/call', {'name': name, 'arguments': arguments}),
            tools,
            context=context,
        )
    return response['result']['structuredContent']


def test_default_token_is_mirrored_into_a_scoped_credential(tasks_connector):
    connector, token = tasks_connector

    credential = connector.credentials.get(label='Default')

    assert credential.check_token(token) is True
    assert credential.allowed_tools == []


def test_service_actor_does_not_take_over_a_matching_human_username(
    api_client, django_user_model, tasks_connector,
):
    connector, token = tasks_connector
    human = django_user_model.objects.create_user(
        username='mcp_tasks',
        password='human-password',
        is_staff=False,
        is_superuser=False,
    )

    response = _call(api_client, 'tasks', token, 'list_tasks')

    human.refresh_from_db()
    credential = connector.credentials.get(label='Default')
    assert response.status_code == 200
    assert credential.actor_id != human.id
    assert credential.actor.username.startswith('mcp_tasks_')
    assert human.is_superuser is False
    assert human.has_usable_password() is True


def test_panel_creates_a_scoped_credential_and_reveals_the_secret_once(
    super_client, tasks_connector,
):
    connector, _ = tasks_connector

    response = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Sólo tablero', 'allowed_tools': ['list_tasks']},
        format='json',
    )

    assert response.status_code == 201
    assert response.data['credential'] not in McpCredential.objects.get(
        pk=response.data['id'],
    ).token_hash
    assert response.data['connector_url'].startswith('http://testserver/api/mcp/tasks/')


def test_panel_rejects_an_oversized_credential_label(super_client, tasks_connector):
    response = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'x' * 101, 'allowed_tools': ['list_tasks']},
        format='json',
    )

    assert response.status_code == 400
    assert response.data['label'] == 'La etiqueta no puede superar 100 caracteres.'


def test_panel_normalizes_a_naive_future_credential_expiry(
    super_client, tasks_connector,
):
    expires_at = (tz.now() + timedelta(days=1)).replace(tzinfo=None)

    response = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {
            'label': 'Vigencia local',
            'allowed_tools': ['list_tasks'],
            'expires_at': expires_at.isoformat(),
        },
        format='json',
    )

    assert response.status_code == 201
    assert McpCredential.objects.get(pk=response.data['id']).expires_at is not None


def test_bearer_credential_can_call_an_allowed_tool(
    api_client, super_client, tasks_connector,
):
    _, _ = tasks_connector
    created = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Listar', 'allowed_tools': ['list_tasks']},
        format='json',
    )

    response = _call(
        api_client, 'tasks', created.data['credential'], 'list_tasks', bearer=True,
    )

    assert response.status_code == 200
    assert response.data['result']['isError'] is False


def test_bearer_credential_rejects_an_unlisted_tool(
    api_client, super_client, tasks_connector,
):
    _, _ = tasks_connector
    created = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Listar', 'allowed_tools': ['list_tasks']},
        format='json',
    )

    response = _call(
        api_client, 'tasks', created.data['credential'], 'get_task',
        {'task_id': 1}, bearer=True,
    )

    error = response.data['result']['structuredContent']['error']
    assert error['code'] == 'FORBIDDEN'


def test_rotating_a_scoped_credential_invalidates_its_previous_secret(
    api_client, super_client, tasks_connector,
):
    _, _ = tasks_connector
    created = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Rotable', 'allowed_tools': ['list_tasks']},
        format='json',
    )
    old_token = created.data['credential']

    rotated = super_client.post(
        f"/api/mcp-connectors/tasks/credentials/{created.data['id']}/rotate/",
        {},
        format='json',
    )

    assert _call(api_client, 'tasks', old_token, 'list_tasks').status_code == 404
    assert _call(
        api_client, 'tasks', rotated.data['credential'], 'list_tasks', bearer=True,
    ).status_code == 200


def test_revoked_credential_is_rejected_by_the_transport(
    api_client, super_client, tasks_connector,
):
    _, _ = tasks_connector
    created = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Temporal', 'allowed_tools': ['list_tasks']},
        format='json',
    )
    super_client.delete(
        f"/api/mcp-connectors/tasks/credentials/{created.data['id']}/",
    )

    response = _call(
        api_client, 'tasks', created.data['credential'], 'list_tasks', bearer=True,
    )

    assert response.status_code == 404


class TestCredentialPanelValidation:
    def test_create_credential_requires_a_label(self, super_client, tasks_connector):
        """Falla si el Panel crea una credencial sin nombre auditable."""
        response = super_client.post(
            '/api/mcp-connectors/tasks/credentials/',
            {'label': '   ', 'allowed_tools': ['list_tasks']},
            format='json',
        )

        assert response.status_code == 400
        assert response.data == {'label': 'La etiqueta es obligatoria.'}

    @pytest.mark.parametrize(
        ('allowed_tools', 'message'),
        [
            pytest.param('list_tasks', 'debe ser una lista', id='string'),
            pytest.param(['unknown_tool'], 'Herramientas desconocidas', id='unknown'),
        ],
    )
    def test_create_credential_rejects_invalid_tool_scopes(
        self, super_client, tasks_connector, allowed_tools, message,
    ):
        """Falla si el Panel acepta scopes mal formados o fuera del catálogo."""
        response = super_client.post(
            '/api/mcp-connectors/tasks/credentials/',
            {'label': 'Invalid scope', 'allowed_tools': allowed_tools},
            format='json',
        )

        assert response.status_code == 400
        assert message in str(response.data['detail'])

    def test_create_credential_rejects_a_past_expiry(
        self, super_client, tasks_connector,
    ):
        """Falla si una credencial nace expirada y parece operativa en el Panel."""
        response = super_client.post(
            '/api/mcp-connectors/tasks/credentials/',
            {
                'label': 'Expired credential',
                'expires_at': (tz.now() - timedelta(days=1)).isoformat(),
            },
            format='json',
        )

        assert response.status_code == 400
        assert 'fecha futura' in str(response.data['detail'])

    def test_create_credential_rejects_a_duplicate_label(
        self, super_client, tasks_connector,
    ):
        """Falla si etiquetas duplicadas impiden identificar qué secreto se revoca."""
        payload = {'label': 'Duplicate label', 'allowed_tools': ['list_tasks']}
        created = super_client.post(
            '/api/mcp-connectors/tasks/credentials/', payload, format='json',
        )

        duplicate = super_client.post(
            '/api/mcp-connectors/tasks/credentials/', payload, format='json',
        )

        assert created.status_code == 201
        assert duplicate.status_code == 409
        assert duplicate.data == {
            'label': 'Ya existe una credencial con esa etiqueta.',
        }

    def test_patch_credential_persists_scope_and_expiry(
        self, super_client, tasks_connector,
    ):
        """Falla si editar una credencial no cambia sus límites efectivos."""
        created = super_client.post(
            '/api/mcp-connectors/tasks/credentials/',
            {'label': 'Editable scope'},
            format='json',
        )
        expires_at = (tz.now() + timedelta(days=2)).isoformat()

        response = super_client.patch(
            f"/api/mcp-connectors/tasks/credentials/{created.data['id']}/",
            {'allowed_tools': ['list_tasks'], 'expires_at': expires_at},
            format='json',
        )

        credential = McpCredential.objects.get(pk=created.data['id'])
        assert response.status_code == 200
        assert credential.allowed_tools == ['list_tasks']
        assert credential.expires_at is not None

    def test_patch_credential_rejects_an_unknown_scope(
        self, super_client, tasks_connector,
    ):
        """Falla si PATCH puede ampliar una credencial con herramientas inexistentes."""
        created = super_client.post(
            '/api/mcp-connectors/tasks/credentials/',
            {'label': 'Bounded scope', 'allowed_tools': ['list_tasks']},
            format='json',
        )

        response = super_client.patch(
            f"/api/mcp-connectors/tasks/credentials/{created.data['id']}/",
            {'allowed_tools': ['unknown_tool']},
            format='json',
        )

        credential = McpCredential.objects.get(pk=created.data['id'])
        assert response.status_code == 400
        assert credential.allowed_tools == ['list_tasks']

    def test_revoke_default_credential_clears_the_compatibility_token(
        self, super_client, tasks_connector,
    ):
        """Falla si revocar Default deja utilizable el secreto legado del conector."""
        connector, _ = tasks_connector
        credential = connector.credentials.get(label='Default')

        response = super_client.delete(
            f'/api/mcp-connectors/tasks/credentials/{credential.id}/',
        )

        connector.refresh_from_db()
        credential.refresh_from_db()
        assert response.status_code == 204
        assert credential.revoked_at is not None
        assert connector.token_hash == ''
        assert connector.token_prefix == ''

    def test_rotate_default_credential_updates_the_compatibility_token(
        self, super_client, tasks_connector,
    ):
        """Falla si rotar Default deja el transporte legado con un hash anterior."""
        connector, _ = tasks_connector
        credential = connector.credentials.get(label='Default')

        response = super_client.post(
            f'/api/mcp-connectors/tasks/credentials/{credential.id}/rotate/',
            {},
            format='json',
        )

        connector.refresh_from_db()
        credential.refresh_from_db()
        assert response.status_code == 200
        assert connector.token_hash == credential.token_hash
        assert connector.token_prefix == response.data['token_prefix']


def test_tools_list_exposes_output_schema_and_annotations(api_client, tasks_connector):
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/', _rpc('tools/list'), format='json',
    )
    listed = next(
        tool for tool in response.data['result']['tools']
        if tool['name'] == 'list_tasks'
    )

    assert listed['outputSchema']['type'] == 'object'
    assert listed['annotations']['readOnlyHint'] is True


def test_sensitive_call_returns_preview_without_executing(confirmation_runtime):
    tools, context, calls = confirmation_runtime

    preview = _preview(tools, context)

    assert preview['confirmation_required'] is True
    assert calls == []


def test_confirm_action_executes_the_exact_previewed_arguments(confirmation_runtime):
    tools, context, calls = confirmation_runtime
    preview = _preview(tools, context)

    with use_mcp_context(context):
        _, response = handle_message(
            _rpc('tools/call', {
                'name': 'confirm_action',
                'arguments': {'confirmation_id': preview['confirmation_id']},
            }),
            tools,
            context=context,
        )

    assert response['result']['structuredContent']['result'] == {'deleted': 42}
    assert calls == [42]


def test_confirm_action_replay_does_not_execute_twice(confirmation_runtime):
    tools, context, calls = confirmation_runtime
    preview = _preview(tools, context)
    request = _rpc('tools/call', {
        'name': 'confirm_action',
        'arguments': {'confirmation_id': preview['confirmation_id']},
    })

    with use_mcp_context(context):
        handle_message(request, tools, context=context)
        _, replay = handle_message(request, tools, context=context)

    assert replay['result']['structuredContent']['replayed'] is True
    assert calls == [42]


def test_confirmation_cannot_cross_credentials(confirmation_runtime):
    tools, context, _ = confirmation_runtime
    preview = _preview(tools, context)
    other = McpCredential.objects.create(
        connector=context.connector,
        label='Other',
        token_hash=McpCredential.hash_token('other-token'),
    )
    foreign_context = McpExecutionContext(
        connector=context.connector,
        credential=other,
        request_id='foreign-request',
    )

    with use_mcp_context(foreign_context):
        _, response = handle_message(
            _rpc('tools/call', {
                'name': 'confirm_action',
                'arguments': {'confirmation_id': preview['confirmation_id']},
            }),
            tools,
            context=foreign_context,
        )

    assert response['result']['structuredContent']['error']['code'] == 'FORBIDDEN'


class TestConfirmationGuards:
    def test_sensitive_preview_requires_an_identified_credential(
        self, confirmation_runtime,
    ):
        """Falla si una acción sensible puede generar intención sin propietario."""
        tools, _, _ = confirmation_runtime
        sensitive = next(tool for tool in tools if tool['name'] == 'delete_record')

        with pytest.raises(ToolError) as error:
            preview_sensitive_action(sensitive, {'record_id': 42})

        assert error.value.code == 'FORBIDDEN'

    def test_confirm_action_requires_an_identified_credential(
        self, confirmation_runtime,
    ):
        """Falla si confirm_action acepta una ejecución fuera de contexto MCP."""
        tools, _, _ = confirmation_runtime

        with pytest.raises(ToolError) as error:
            confirm_action({'confirmation_id': UNKNOWN_CONFIRMATION_ID}, tools)

        assert error.value.code == 'FORBIDDEN'

    def test_cancel_action_requires_an_identified_credential(self):
        """Falla si cancel_action puede operar sin credencial autenticada."""
        with pytest.raises(ToolError) as error:
            cancel_action({'confirmation_id': UNKNOWN_CONFIRMATION_ID})

        assert error.value.code == 'FORBIDDEN'

    def test_confirm_action_rejects_a_cancelled_intent(self, confirmation_runtime):
        """Falla si una intención cancelada vuelve a estar disponible."""
        tools, context, calls = confirmation_runtime
        preview = _preview(tools, context)
        intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
        intent.status = McpActionIntent.STATUS_CANCELLED
        intent.save(update_fields=['status'])

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        assert result['error']['code'] == 'CONFIRMATION_EXPIRED'
        assert calls == []

    def test_confirm_action_marks_an_expired_intent(self, confirmation_runtime):
        """Falla si una intención vencida se ejecuta o no conserva su estado terminal."""
        tools, context, calls = confirmation_runtime
        preview = _preview(tools, context)
        intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
        intent.expires_at = tz.now() - timedelta(seconds=1)
        intent.save(update_fields=['expires_at'])

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        intent.refresh_from_db()
        assert result['error']['code'] == 'CONFIRMATION_EXPIRED'
        assert intent.status == McpActionIntent.STATUS_EXPIRED
        assert calls == []

    def test_confirm_action_rejects_a_retired_tool(self, confirmation_runtime):
        """Falla si una confirmación ejecuta una herramienta retirada del catálogo."""
        tools, context, calls = confirmation_runtime
        preview = _preview(tools, context)
        intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
        intent.tool_name = 'retired_action'
        intent.save(update_fields=['tool_name'])

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        assert result['error']['code'] == 'CONFLICT'
        assert calls == []

    def test_confirm_action_rechecks_the_current_credential_scope(
        self, confirmation_runtime,
    ):
        """Falla si reducir scopes no invalida una confirmación pendiente."""
        tools, context, calls = confirmation_runtime
        preview = _preview(tools, context)
        context.credential.allowed_tools = ['list_tasks']
        context.credential.save(update_fields=['allowed_tools'])

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        assert result['error']['code'] == 'FORBIDDEN'
        assert calls == []

    def test_confirm_action_rejects_tampered_arguments(self, confirmation_runtime):
        """Falla si cambiar argumentos persistidos conserva una confirmación válida."""
        tools, context, calls = confirmation_runtime
        preview = _preview(tools, context)
        intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
        intent.arguments = {'record_id': 99}
        intent.save(update_fields=['arguments'])

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        assert result['error']['code'] == 'CONFLICT'
        assert calls == []

    def test_confirm_action_rejects_a_stale_resource_version(
        self, confirmation_runtime,
    ):
        """Falla si un recurso modificado desde preview aún puede mutarse."""
        tools, context, calls = confirmation_runtime
        sensitive = next(tool for tool in tools if tool['name'] == 'delete_record')
        sensitive['etag_resolver'] = lambda arguments: {'record': 'v1'}
        preview = _preview(tools, context)
        sensitive['etag_resolver'] = lambda arguments: {'record': 'v2'}

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': preview['confirmation_id']},
        )

        assert result['error']['code'] == 'STALE_VERSION'
        assert result['error']['details'] == {
            'expected': {'record': 'v1'},
            'current': {'record': 'v2'},
        }
        assert calls == []

    def test_confirm_action_rejects_an_unknown_intent(self, confirmation_runtime):
        """Falla si un UUID inexistente se trata como confirmación ejecutable."""
        tools, context, calls = confirmation_runtime

        result = _runtime_call(
            tools,
            context,
            'confirm_action',
            {'confirmation_id': UNKNOWN_CONFIRMATION_ID},
        )

        assert result['error']['code'] == 'NOT_FOUND'
        assert calls == []

    def test_cancel_action_closes_a_pending_intent(self, confirmation_runtime):
        """Falla si cancelar no persiste el estado terminal de la intención."""
        tools, context, _ = confirmation_runtime
        preview = _preview(tools, context)

        with use_mcp_context(context):
            result = cancel_action({'confirmation_id': preview['confirmation_id']})

        intent = McpActionIntent.objects.get(pk=preview['confirmation_id'])
        assert result == {
            'cancelled': True,
            'confirmation_id': preview['confirmation_id'],
        }
        assert intent.status == McpActionIntent.STATUS_CANCELLED

    def test_cancel_action_rejects_an_unknown_intent(self, confirmation_runtime):
        """Falla si cancelar un UUID inexistente informa éxito engañoso."""
        _, context, _ = confirmation_runtime

        with use_mcp_context(context), pytest.raises(ToolError) as error:
            cancel_action({'confirmation_id': UNKNOWN_CONFIRMATION_ID})

        assert error.value.code == 'NOT_FOUND'


def test_signed_upload_verifies_size_and_sha256(
    api_client, settings, tmp_path, tasks_connector,
):
    settings.MEDIA_ROOT = tmp_path
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')
    body = b'contenido mcp'
    context = McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id='upload-request',
        request=APIRequestFactory().get('/', HTTP_HOST='testserver'),
    )
    with use_mcp_context(context):
        upload = begin_upload({
            'filename': 'evidencia.txt',
            'content_type': 'text/plain',
            'size': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
        })
    path = urlsplit(upload['upload_url']).path
    received = api_client.generic('PUT', path, body, content_type='text/plain')

    with use_mcp_context(context):
        completed = complete_upload({'asset_id': upload['asset_id']})

    assert received.status_code == 200
    assert completed['sha256'] == hashlib.sha256(body).hexdigest()


def test_upload_rejects_an_extension_that_does_not_match_its_mime_type(
    tasks_connector,
):
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')
    context = McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id='upload-extension-request',
    )

    with use_mcp_context(context), pytest.raises(ToolError, match='extensión'):
        begin_upload({
            'filename': 'evidencia.exe',
            'content_type': 'image/png',
            'size': 3,
            'sha256': hashlib.sha256(b'png').hexdigest(),
        })


def test_upload_rejects_content_that_does_not_match_its_mime_type(
    api_client, settings, tmp_path, tasks_connector,
):
    settings.MEDIA_ROOT = tmp_path
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')
    body = b'not really a png'
    context = McpExecutionContext(
        connector=connector,
        credential=credential,
        request_id='upload-content-request',
        request=APIRequestFactory().get('/', HTTP_HOST='testserver'),
    )
    with use_mcp_context(context):
        upload = begin_upload({
            'filename': 'evidencia.png',
            'content_type': 'image/png',
            'size': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
        })
    path = urlsplit(upload['upload_url']).path
    received = api_client.generic('PUT', path, body, content_type='image/png')

    with use_mcp_context(context), pytest.raises(
        ToolError,
        match='contenido no coincide',
    ):
        complete_upload({'asset_id': upload['asset_id']})

    assert received.status_code == 200


def test_temporary_output_artifact_has_a_signed_download(
    api_client, settings, tmp_path, tasks_connector,
):
    settings.MEDIA_ROOT = tmp_path
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')
    request = APIRequestFactory().get('/', HTTP_HOST='testserver')

    artifact = store_artifact(
        connector=connector,
        credential=credential,
        filename='reporte.csv',
        content_type='text/csv',
        content=b'a,b\n1,2\n',
        request=request,
    )
    response = api_client.get(urlsplit(artifact['download_url']).path)

    assert response.status_code == 200
    assert b''.join(response.streaming_content) == b'a,b\n1,2\n'


class TestUploadMetadataGuards:
    def test_begin_upload_requires_an_identified_credential(self):
        """Falla si un caller sin credencial puede reservar almacenamiento MCP."""
        with pytest.raises(ToolError) as error:
            begin_upload(VALID_UPLOAD_ARGUMENTS)

        assert error.value.code == 'FORBIDDEN'

    @pytest.mark.parametrize(
        ('overrides', 'message'),
        [
            pytest.param({'size': 'invalid'}, 'entero positivo', id='non-integer-size'),
            pytest.param({'filename': ''}, 'filename es obligatorio', id='missing-filename'),
            pytest.param(
                {'filename': f'{"x" * 252}.txt'},
                '255 caracteres',
                id='oversized-filename',
            ),
            pytest.param(
                {'content_type': 'application/octet-stream'},
                'Tipo de archivo no permitido',
                id='unsupported-mime',
            ),
            pytest.param({'size': 0}, 'size debe estar entre', id='empty-file'),
            pytest.param({'sha256': 'xyz'}, '64 caracteres', id='invalid-sha256'),
        ],
    )
    def test_begin_upload_rejects_unsafe_metadata(
        self, upload_context, overrides, message,
    ):
        """Falla si metadatos inseguros alcanzan la creación del asset temporal."""
        arguments = {**VALID_UPLOAD_ARGUMENTS, **overrides}

        with use_mcp_context(upload_context), pytest.raises(
            ToolError,
            match=message,
        ):
            begin_upload(arguments)

    def test_begin_upload_aborts_expired_assets(self, upload_context):
        """Falla si una reserva vencida conserva estado activo o bytes en storage."""
        expired = _upload_row(
            upload_context,
            body=b'old',
            status=McpUpload.STATUS_COMPLETE,
            expires_at=tz.now() - timedelta(minutes=1),
        )
        old_name = expired.file.name
        storage = expired.file.storage

        with use_mcp_context(upload_context):
            created = begin_upload(VALID_UPLOAD_ARGUMENTS)

        expired.refresh_from_db()
        assert expired.status == McpUpload.STATUS_ABORTED
        assert storage.exists(old_name) is False
        assert McpUpload.objects.get(pk=created['asset_id']).status == McpUpload.STATUS_PENDING

    def test_store_artifact_rejects_content_over_the_configured_limit(
        self, settings, upload_context,
    ):
        """Falla si una salida generada puede evadir el máximo de bytes MCP."""
        settings.MCP_UPLOAD_MAX_BYTES = 3

        with pytest.raises(ToolError) as error:
            store_artifact(
                connector=upload_context.connector,
                credential=upload_context.credential,
                filename='large.txt',
                content_type='text/plain',
                content=b'four',
                request=upload_context.request,
            )

        assert error.value.code == 'CONFLICT'
        assert McpUpload.objects.filter(
            connector=upload_context.connector,
            credential=upload_context.credential,
        ).count() == 0


class TestUploadChunkGuards:
    @pytest.mark.parametrize(
        ('arguments', 'code', 'message'),
        [
            pytest.param(
                {'base64': 12},
                'VALIDATION_ERROR',
                'base64 debe ser texto',
                id='non-string-base64',
            ),
            pytest.param(
                {'base64': '***'},
                'VALIDATION_ERROR',
                'datos válidos',
                id='malformed-base64',
            ),
            pytest.param(
                {'base64': ''},
                'VALIDATION_ERROR',
                'Cada chunk debe medir',
                id='empty-chunk',
            ),
            pytest.param(
                {
                    'base64': VALID_CHUNK,
                    'index': 'invalid',
                    'chunk_sha256': VALID_CHUNK_HASH,
                },
                'VALIDATION_ERROR',
                'index debe ser un entero',
                id='non-integer-index',
            ),
            pytest.param(
                {'base64': VALID_CHUNK, 'index': 0, 'chunk_sha256': '0' * 64},
                'CONFLICT',
                'hash del chunk',
                id='hash-mismatch',
            ),
        ],
    )
    def test_chunk_upload_rejects_malformed_transport_data(
        self, arguments, code, message,
    ):
        """Falla si un chunk corrupto alcanza la reserva o modifica sus contadores."""
        with pytest.raises(ToolError, match=message) as error:
            upload_asset_chunk(arguments)

        assert error.value.code == code

    @pytest.mark.parametrize(
        ('row_overrides', 'message'),
        [
            pytest.param(
                {'status': McpUpload.STATUS_COMPLETE},
                'ya no acepta chunks',
                id='closed-upload',
            ),
            pytest.param(
                {'expected_size': 10, 'next_chunk_index': 2},
                'índice del chunk',
                id='out-of-order-index',
            ),
            pytest.param(
                {'expected_size': 1, 'received_size': 1},
                'excede el tamaño declarado',
                id='declared-size-overflow',
            ),
        ],
    )
    def test_chunk_upload_rejects_conflicting_reservation_state(
        self, upload_context, row_overrides, message,
    ):
        """Falla si una reserva cerrada, desordenada o llena acepta más bytes."""
        upload = _upload_row(upload_context, **row_overrides)
        arguments = {
            'asset_id': str(upload.id),
            'base64': VALID_CHUNK,
            'index': 0,
            'chunk_sha256': VALID_CHUNK_HASH,
        }

        with use_mcp_context(upload_context), pytest.raises(
            ToolError,
            match=message,
        ) as error:
            upload_asset_chunk(arguments)

        assert error.value.code == 'CONFLICT'

    def test_chunked_upload_preserves_the_completed_payload(self, upload_context):
        """Falla si chunks válidos se desordenan, truncan o cambian su digest final."""
        payload = b'hello world'
        first = b'hello '
        second = b'world'
        arguments = {
            'filename': 'payload.txt',
            'content_type': 'text/plain',
            'size': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(),
        }

        with use_mcp_context(upload_context):
            reservation = begin_upload(arguments)
            first_result = upload_asset_chunk({
                'asset_id': reservation['asset_id'],
                'base64': base64.b64encode(first).decode('ascii'),
                'index': 0,
                'chunk_sha256': hashlib.sha256(first).hexdigest(),
            })
            second_result = upload_asset_chunk({
                'asset_id': reservation['asset_id'],
                'base64': base64.b64encode(second).decode('ascii'),
                'index': 1,
                'chunk_sha256': hashlib.sha256(second).hexdigest(),
            })
            completed = complete_upload({'asset_id': reservation['asset_id']})

        upload = McpUpload.objects.get(pk=reservation['asset_id'])
        with upload.file.open('rb') as source:
            stored = source.read()
        assert first_result['next_chunk_index'] == 1
        assert second_result['received_size'] == len(payload)
        assert completed['status'] == McpUpload.STATUS_COMPLETE
        assert stored == payload

    def test_upload_lookup_is_scoped_to_its_credential(self, upload_context):
        """Falla si una credencial puede consumir el asset privado de otra."""
        upload = _upload_row(
            upload_context,
            status=McpUpload.STATUS_COMPLETE,
        )
        other = McpCredential.objects.create(
            connector=upload_context.connector,
            label='Other upload owner',
            token_hash=McpCredential.hash_token('other-upload-token'),
        )
        foreign_context = McpExecutionContext(
            connector=upload_context.connector,
            credential=other,
            request_id='foreign-upload-request',
        )

        with use_mcp_context(foreign_context), pytest.raises(ToolError) as error:
            consume_upload(upload.id)

        assert error.value.code == 'NOT_FOUND'

    def test_upload_lookup_rejects_an_expired_asset(self, upload_context):
        """Falla si una reserva vencida continúa disponible para operaciones MCP."""
        upload = _upload_row(
            upload_context,
            status=McpUpload.STATUS_COMPLETE,
            expires_at=tz.now() - timedelta(seconds=1),
        )

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            consume_upload(upload.id)

        assert error.value.code == 'CONFIRMATION_EXPIRED'


class TestUploadCompletionGuards:
    @pytest.mark.parametrize(
        ('row_kwargs', 'message'),
        [
            pytest.param({}, 'no tiene datos pendientes', id='missing-file'),
            pytest.param(
                {'body': b'x', 'expected_size': 2},
                'tamaño recibido no coincide',
                id='size-mismatch',
            ),
            pytest.param(
                {'body': b'x', 'expected_sha256': '0' * 64},
                'SHA-256 final no coincide',
                id='digest-mismatch',
            ),
        ],
    )
    def test_complete_upload_rejects_failed_integrity_checks(
        self, upload_context, row_kwargs, message,
    ):
        """Falla si un asset incompleto o alterado llega al estado complete."""
        upload = _upload_row(upload_context, **row_kwargs)

        with use_mcp_context(upload_context), pytest.raises(
            ToolError,
            match=message,
        ) as error:
            complete_upload({'asset_id': upload.id})

        upload.refresh_from_db()
        assert error.value.code == 'CONFLICT'
        assert upload.status == McpUpload.STATUS_PENDING

    def test_complete_upload_rejects_non_utf8_text(self, upload_context):
        """Falla si un archivo declarado como texto contiene bytes UTF-8 inválidos."""
        upload = _upload_row(upload_context, body=b'\xff')

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            complete_upload({'asset_id': upload.id})

        assert error.value.code == 'INVALID_FILE_CONTENT'

    def test_complete_upload_rejects_a_malformed_docx(self, upload_context):
        """Falla si bytes arbitrarios pueden presentarse como documento DOCX."""
        upload = _upload_row(
            upload_context,
            body=b'not-a-zip',
            filename='document.docx',
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            complete_upload({'asset_id': upload.id})

        assert error.value.code == 'INVALID_FILE_CONTENT'

    def test_complete_upload_rejects_docx_without_document_xml(self, upload_context):
        """Falla si un ZIP sin la estructura DOCX mínima pasa la firma de contenido."""
        upload = _upload_row(
            upload_context,
            body=_incomplete_docx_payload(),
            filename='document.docx',
            content_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
        )

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            complete_upload({'asset_id': upload.id})

        assert error.value.code == 'INVALID_FILE_CONTENT'

    def test_complete_upload_replays_an_already_completed_asset(self, upload_context):
        """Falla si reintentar complete altera un asset ya confirmado."""
        upload = _upload_row(
            upload_context,
            body=b'done',
            status=McpUpload.STATUS_COMPLETE,
        )

        with use_mcp_context(upload_context):
            result = complete_upload({'asset_id': upload.id})

        assert result == {
            'asset_id': str(upload.id),
            'status': McpUpload.STATUS_COMPLETE,
            'filename': 'evidencia.txt',
            'content_type': 'text/plain',
            'size': 4,
            'sha256': hashlib.sha256(b'done').hexdigest(),
            'expires_at': upload.expires_at.isoformat(),
        }

    def test_abort_upload_removes_pending_bytes(self, upload_context):
        """Falla si cancelar una reserva deja bytes privados en storage."""
        upload = _upload_row(upload_context, body=b'temporary')
        stored_name = upload.file.name
        storage = upload.file.storage

        with use_mcp_context(upload_context):
            result = abort_upload({'asset_id': upload.id})

        upload.refresh_from_db()
        assert result == {'asset_id': str(upload.id), 'aborted': True}
        assert upload.status == McpUpload.STATUS_ABORTED
        assert storage.exists(stored_name) is False

    def test_abort_upload_preserves_a_consumed_asset(self, upload_context):
        """Falla si abort permite borrar un asset que ya consumió el dominio."""
        upload = _upload_row(
            upload_context,
            body=b'used',
            status=McpUpload.STATUS_CONSUMED,
        )

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            abort_upload({'asset_id': upload.id})

        assert error.value.code == 'CONFLICT'
        assert upload.file.storage.exists(upload.file.name) is True

    @pytest.mark.parametrize(
        ('row_kwargs', 'allowed_types', 'code'),
        [
            pytest.param(
                {'status': McpUpload.STATUS_PENDING},
                None,
                'CONFLICT',
                id='pending',
            ),
            pytest.param(
                {
                    'status': McpUpload.STATUS_COMPLETE,
                    'content_type': 'image/png',
                },
                {'application/pdf'},
                'VALIDATION_ERROR',
                id='mime-mismatch',
            ),
        ],
    )
    def test_consume_upload_rejects_an_incompatible_asset(
        self, upload_context, row_kwargs, allowed_types, code,
    ):
        """Falla si el dominio recibe un asset pendiente o de MIME no permitido."""
        upload = _upload_row(upload_context, **row_kwargs)

        with use_mcp_context(upload_context), pytest.raises(ToolError) as error:
            consume_upload(upload.id, allowed_content_types=allowed_types)

        assert error.value.code == code


class TestPanelBridgeContracts:
    def test_panel_export_becomes_a_signed_mcp_asset(self, accounting_context):
        """Falla si una descarga del Panel no se conserva como asset MCP descargable."""
        tool = next(
            item for item in LEDGER_PARITY_TOOLS
            if item['name'] == 'export_accounting_records'
        )

        with use_mcp_context(accounting_context):
            result = tool['handler']({
                'query': {'section': 'income', 'file_format': 'csv'},
            })

        upload = McpUpload.objects.get(pk=result['asset_id'])
        assert upload.status == McpUpload.STATUS_COMPLETE
        assert upload.content_type == 'text/csv; charset=utf-8'
        assert result['download_url'].startswith('http://testserver/api/mcp-assets/')
        assert result['size'] > 0

    def test_panel_bridge_preserves_the_machine_error_code(self, accounting_context):
        """Falla si un error del Panel pierde el código accionable para el caller MCP."""
        tool = next(
            item for item in LEDGER_PARITY_TOOLS
            if item['name'] == 'export_accounting_records'
        )

        with use_mcp_context(accounting_context), pytest.raises(ToolError) as error:
            tool['handler']({'query': {'section': 'unknown'}})

        assert error.value.code == 'INVALID_SECTION'
        assert error.value.details['code'] == 'invalid_section'

    def test_panel_bridge_requires_every_route_identifier(self):
        """Falla si el bridge construye una ruta mutante sin su identificador."""
        tool = panel_operation(
            'test_update_task',
            'Actualiza una tarea existente mediante el contrato vigente del Panel.',
            'update-task',
            method='PATCH',
            path_params=('task_id',),
            risk='write',
        )

        with pytest.raises(ToolError, match='task_id es obligatorio'):
            tool['handler']({'data': {'title': 'No target'}})

    @pytest.mark.parametrize(
        'arguments',
        [
            pytest.param({'query': []}, id='query-array'),
            pytest.param({'data': []}, id='data-array'),
        ],
    )
    def test_panel_bridge_requires_json_objects_for_request_sections(self, arguments):
        """Falla si query o data aceptan formas que el endpoint no puede validar."""
        tool = panel_operation(
            'test_list_tasks',
            'Lista tareas usando exactamente el contrato vigente del Panel administrativo.',
            'list-tasks',
        )

        with pytest.raises(ToolError, match='deben ser objetos JSON'):
            tool['handler'](arguments)

    def test_panel_bridge_consumes_an_uploaded_statement_pdf(self, accounting_context):
        """Falla si el bridge no entrega el PDF validado ni cierra su asset temporal."""
        statement = CreditCardStatement.objects.create(
            card_name='Visa MCP',
            period_date=date(2026, 9, 1),
            purchases_total=0,
        )
        upload = _upload_row(
            accounting_context,
            body=b'%PDF-1.4\n%%EOF',
            filename='statement.pdf',
            content_type='application/pdf',
            status=McpUpload.STATUS_COMPLETE,
        )
        tool = next(
            item for item in CARD_PARITY_TOOLS
            if item['name'] == 'upload_statement_pdf'
        )

        with use_mcp_context(accounting_context):
            result = tool['handler']({
                'record_id': statement.id,
                'asset_id': str(upload.id),
            })

        statement.refresh_from_db()
        upload.refresh_from_db()
        assert result['id'] == statement.id
        assert statement.pdf_file.name.endswith('statement.pdf')
        assert upload.status == McpUpload.STATUS_CONSUMED
        assert upload.consumed_at is not None


def test_operations_connector_calls_the_existing_panel_dashboard(api_client):
    connector = McpConnector.objects.get(slug='operations')
    connector.is_active = True
    connector.save(update_fields=['is_active'])
    token = connector.generate_token()

    response = _call(
        api_client, 'operations', token, 'get_operations_dashboard', {},
    )

    assert response.status_code == 200
    assert response.data['result']['isError'] is False


def test_tool_audit_records_credential_risk_and_request_id(api_client, tasks_connector):
    connector, token = tasks_connector
    task = Task.objects.create(title='Trazable', status='todo')

    response = _call(
        api_client, 'tasks', token, 'get_task', {'task_id': task.id},
    )

    event = McpRequestLog.objects.get(connector=connector, event='tool_call')
    assert event.credential.label == 'Default'
    assert event.risk_level == 'read'
    assert event.request_id == response['Mcp-Request-Id']
    assert event.object_refs == [{'field': 'task_id', 'value': task.id}]


def test_modern_discovery_advertises_the_stateless_contract(api_client, tasks_connector):
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('server/discover'),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='server/discover',
    )

    result = response.data['result']
    assert result['supportedVersions'] == ['2026-07-28']
    assert result['resultType'] == 'complete'
    assert result['cacheScope'] == 'private'
    assert result['_meta']['io.modelcontextprotocol/serverInfo']['name'] == (
        'projectapp-tasks-mcp'
    )


def test_modern_tools_list_includes_response_metadata(api_client, tasks_connector):
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('tools/list'),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='tools/list',
    )

    result = response.data['result']
    assert result['resultType'] == 'complete'
    assert result['ttlMs'] == 300_000
    assert response['Mcp-Protocol-Version'] == '2026-07-28'


def test_modern_transport_rejects_a_mismatched_tool_name(api_client, tasks_connector):
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('tools/call', {
            'name': 'list_tasks',
            'arguments': {},
        }),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='tools/call',
        HTTP_MCP_NAME='get_task',
    )

    assert response.status_code == 400
    assert response.data['error']['code'] == -32020


def test_modern_transport_requires_client_capabilities(api_client, tasks_connector):
    _, token = tasks_connector
    message = _modern_rpc('tools/list')
    del message['params']['_meta'][
        'io.modelcontextprotocol/clientCapabilities'
    ]

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        message,
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='tools/list',
    )

    assert response.status_code == 400
    assert response.data['error']['code'] == -32602


def test_path_and_bearer_credentials_must_match(api_client, tasks_connector):
    """Falla si dos credenciales distintas pueden compartir una petición MCP."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _rpc('tools/list'),
        format='json',
        HTTP_AUTHORIZATION='Bearer another-secret',
    )

    assert response.status_code == 404


def test_unsupported_protocol_returns_supported_versions(api_client, tasks_connector):
    """Falla si el transporte acepta una versión MCP no implementada."""
    _, token = tasks_connector
    message = _modern_rpc('tools/list')
    message['params']['_meta'][
        'io.modelcontextprotocol/protocolVersion'
    ] = '2099-01-01'

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        message,
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2099-01-01',
        HTTP_MCP_METHOD='tools/list',
    )

    assert response.status_code == 400
    assert response.data['error']['code'] == -32022
    assert response.data['error']['message'] == (
        'Versión MCP no soportada: 2099-01-01.'
    )
    assert '2026-07-28' in response.data['error']['data']['supportedVersions']


def test_modern_transport_rejects_invalid_client_info(api_client, tasks_connector):
    """Falla si clientInfo moderno admite un valor que no sea objeto JSON."""
    _, token = tasks_connector
    message = _modern_rpc('tools/list')
    message['params']['_meta'][
        'io.modelcontextprotocol/clientInfo'
    ] = 'invalid-client'

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        message,
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='tools/list',
    )

    assert response.status_code == 400
    assert response.data['error']['code'] == -32602


def test_modern_transport_rejects_a_mismatched_method(api_client, tasks_connector):
    """Falla si Mcp-Method puede contradecir el método del cuerpo JSON-RPC."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('tools/list'),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='server/discover',
    )

    assert response.status_code == 400
    assert response.data['error']['code'] == -32020


def test_legacy_header_only_tool_call_is_normalized(api_client, tasks_connector):
    """Falla si clientes MCP previos no pueden enviar su método por headers."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        {'status': 'todo'},
        format='json',
        HTTP_MCP_METHOD='tools/call',
        HTTP_MCP_NAME='list_tasks',
        HTTP_MCP_REQUEST_ID='legacy-request',
    )

    assert response.status_code == 200
    assert response.data['result']['isError'] is False


def test_legacy_connector_token_recreates_default_credential(
    api_client, tasks_connector,
):
    """Falla si la ventana de despliegue pierde compatibilidad con tokens previos."""
    connector, token = tasks_connector
    connector.credentials.get(label='Default').delete()

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _rpc('tools/list'),
        format='json',
    )

    recreated = connector.credentials.get(label='Default')
    assert response.status_code == 200
    assert recreated.token_hash == connector.token_hash


def test_activity_log_failure_does_not_break_transport(
    api_client, tasks_connector, monkeypatch, caplog,
):
    """Falla si un problema de auditoría impide responder al cliente MCP."""
    _, token = tasks_connector

    def fail_to_record(*args, **kwargs):
        raise RuntimeError('audit unavailable')

    monkeypatch.setattr(McpRequestLog, 'record', fail_to_record)
    caplog.set_level('ERROR', logger='content.views.mcp_blog')

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _rpc('initialize', {
            'protocolVersion': '2025-03-26',
            'capabilities': {},
            'clientInfo': {'name': 'compat-test', 'version': '1.0'},
        }),
        format='json',
    )

    assert response.status_code == 200
    assert 'MCP_AUDIT_UNAVAILABLE' in caplog.text


def test_invalid_confirmation_identifier_returns_not_found(
    api_client, tasks_connector,
):
    """Falla si un UUID malformado de confirmación se convierte en error interno."""
    _, token = tasks_connector

    response = _call(
        api_client,
        'tasks',
        token,
        'confirm_action',
        {'confirmation_id': 'not-a-uuid'},
    )

    error = response.data['result']['structuredContent']['error']
    assert response.status_code == 200
    assert error['code'] == 'NOT_FOUND'


def test_unknown_tool_audit_discards_undeclared_object_references(api_client, tasks_connector):
    """Falla si una herramienta no registrada conserva argumentos en auditoría."""
    connector, token = tasks_connector
    arguments = {f'resource_{index}_id': index for index in range(30)}

    response = _call(
        api_client,
        'tasks',
        token,
        'missing_tool',
        arguments,
    )

    event = McpRequestLog.objects.get(connector=connector, event='tool_call')
    assert response.data['error']['code'] == -32602
    assert event.ok is False
    assert event.error_code == '-32602'
    assert event.object_refs == []


def test_array_tool_params_are_audited_as_invalid(api_client, tasks_connector):
    """Falla si params posicionales rompen la auditoría de una llamada MCP."""
    connector, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _rpc('tools/call', ['invalid']),
        format='json',
    )

    event = McpRequestLog.objects.get(connector=connector, event='tool_call')
    assert response.data['error']['code'] == -32602
    assert event.tool_name == 'unknown_tool'
    assert event.object_refs == []


def test_array_tool_arguments_keep_audit_references_empty(
    api_client, tasks_connector,
):
    """Falla si argumentos no estructurados contaminan referencias de auditoría."""
    connector, token = tasks_connector

    response = _call(
        api_client,
        'tasks',
        token,
        'missing_tool',
        ['invalid'],
    )

    event = McpRequestLog.objects.get(connector=connector, event='tool_call')
    assert response.data['error']['code'] == -32602
    assert event.object_refs == []


def test_confirmation_without_identifier_returns_not_found(
    api_client, tasks_connector,
):
    """Falla si confirm_action acepta una petición sin confirmation_id."""
    _, token = tasks_connector

    response = _call(api_client, 'tasks', token, 'confirm_action', {})

    error = response.data['result']['structuredContent']['error']
    assert error['code'] == 'NOT_FOUND'


def test_non_object_jsonrpc_request_is_rejected(api_client, tasks_connector):
    """Falla si el endpoint acepta un lote donde exige un único objeto JSON-RPC."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        ['tools/list'],
        format='json',
    )

    assert response.data['error']['code'] == -32600


def test_modern_unknown_method_keeps_jsonrpc_error(api_client, tasks_connector):
    """Falla si la decoración moderna oculta un error JSON-RPC sin result."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('resources/list'),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='resources/list',
    )

    assert response.data['error']['code'] == -32601
    assert 'result' not in response.data


def test_modern_tool_call_accepts_matching_name_header(api_client, tasks_connector):
    """Falla si Mcp-Name correcto bloquea una llamada moderna válida."""
    _, token = tasks_connector

    response = api_client.post(
        f'/api/mcp/tasks/{token}/',
        _modern_rpc('tools/call', {
            'name': 'list_tasks',
            'arguments': {'status': 'todo'},
        }),
        format='json',
        HTTP_MCP_PROTOCOL_VERSION='2026-07-28',
        HTTP_MCP_METHOD='tools/call',
        HTTP_MCP_NAME='list_tasks',
    )

    assert response.data['result']['isError'] is False


def test_empty_credential_patch_preserves_configuration(
    super_client, tasks_connector,
):
    """Falla si un PATCH vacío altera el alcance o vencimiento de la credencial."""
    connector, _ = tasks_connector
    credential = connector.credentials.get(label='Default')

    response = super_client.patch(
        f'/api/mcp-connectors/tasks/credentials/{credential.id}/',
        {},
        format='json',
    )

    credential.refresh_from_db()
    assert response.status_code == 200
    assert credential.allowed_tools == []
    assert credential.expires_at is None


def test_empty_connector_patch_preserves_activation(super_client, tasks_connector):
    """Falla si un PATCH vacío desactiva el conector por efecto lateral."""
    connector, _ = tasks_connector

    response = super_client.patch(
        '/api/mcp-connectors/tasks/',
        {},
        format='json',
    )

    connector.refresh_from_db()
    assert response.status_code == 200
    assert connector.is_active is True


def test_scoped_discovery_hides_ungranted_tools_and_keeps_controls(
    api_client, super_client, tasks_connector,
):
    created = super_client.post(
        '/api/mcp-connectors/tasks/credentials/',
        {'label': 'Lectura acotada', 'allowed_tools': ['list_tasks']},
        format='json',
    )

    response = api_client.post(
        '/api/mcp/tasks/',
        _rpc('tools/list'),
        format='json',
        HTTP_AUTHORIZATION=f"Bearer {created.data['credential']}",
    )

    names = {tool['name'] for tool in response.data['result']['tools']}
    assert {'list_tasks', 'describe_capabilities', 'confirm_action', 'cancel_action'} <= names
    assert 'get_task' not in names
