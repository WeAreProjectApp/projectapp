"""Published native document contracts reject drift before execution."""

from unittest.mock import Mock

import pytest
from rest_framework import serializers

from content.mcp.confirmation import CANCEL_ACTION_INPUT_SCHEMA
from content.mcp.errors import normalize_error
from content.mcp.protocol import handle_message
from content.models import McpConnector, McpCredential
from content.tests.mcp_parity import assert_no_writes, call_tool_inprocess
from content.tests.mcp_schema_rules import schema_problems
from content.views.mcp_blog import TOOLS_BY_SLUG

DOCUMENT_NATIVE_NAMES = (
    'create_folder', 'list_documents', 'read_document', 'create_document',
    'update_document', 'append_document', 'delete_document',
    'list_document_states', 'set_document_state', 'close_document_state',
    'add_document_note', 'finish_document_note', 'delete_document_notes',
    'list_deleted_document_notes', 'restore_document_note',
)
THREAD_NAMES = (
    'get_document_thread', 'list_document_threads', 'create_document_thread',
    'update_document_thread', 'dissolve_document_thread',
)
MIGRATION_NAMES = (
    'preview_folder_migration', 'apply_folder_migration', 'get_folder_migration',
    'preview_folder_migration_undo', 'undo_folder_migration',
    'adopt_folder_as_project_root',
)
UPLOAD_NAMES = ('begin_upload', 'upload_asset_chunk', 'complete_upload', 'abort_upload')
DOCUMENT_NAMES = DOCUMENT_NATIVE_NAMES + THREAD_NAMES + MIGRATION_NAMES + ('preview_move',) + UPLOAD_NAMES


@pytest.mark.parametrize(('slug', 'names'), [('documents', DOCUMENT_NAMES), ('projects', UPLOAD_NAMES)])
def test_published_native_contracts_pass_schema_policy(slug, names):
    tools = {tool['name']: tool for tool in TOOLS_BY_SLUG[slug]}

    problems = {name: schema_problems(tools[name]) for name in names}

    assert problems == {name: [] for name in names}, problems


def test_cancel_action_reusable_contract_passes_schema_policy():
    # common_tools belongs to PR #503; its builder must import this contract.
    tool = {'name': 'cancel_action', 'input_schema': CANCEL_ACTION_INPUT_SCHEMA}

    problems = schema_problems(tool)

    assert not problems, problems


@pytest.fixture
def documents_credential(db, superuser):
    connector, _ = McpConnector.objects.get_or_create(
        slug='documents', defaults={'name': 'Documents native schemas'},
    )
    return McpCredential.objects.create(
        connector=connector, actor=superuser, label='Native schema rejection',
    )


def _block_execution_callbacks(tool, monkeypatch):
    boundary = Mock(side_effect=AssertionError(f'{tool["name"]}: execution preceded schema rejection'))
    for callback in ('handler', 'impact_builder', 'prepare_arguments', 'confirmation_predicate', 'etag_resolver'):
        if callable(tool.get(callback)):
            monkeypatch.setitem(tool, callback, boundary)
    return boundary


@pytest.mark.parametrize(('name', 'arguments'), [
    ('add_document_note', {'document_id': 1, 'content': 'Review note'}),
    ('close_document_state', {'document_id': 1, 'episode_id': 1}),
    ('delete_document', {'document_id': 1}),
    ('delete_document_notes', {'document_id': 1, 'note_ids': [1]}),
    ('finish_document_note', {'document_id': 1, 'note_id': 1}),
    ('list_deleted_document_notes', {'document_id': 1}),
    ('list_document_states', {}),
    ('list_documents', {}),
    ('read_document', {'document_id': 1}),
    ('restore_document_note', {'document_id': 1, 'note_id': 1}),
    ('set_document_state', {'document_id': 1, 'state_id': 1}),
    ('get_document_thread', {'document_id': 1}),
    ('list_document_threads', {}),
    ('create_document_thread', {'items': [{'document_id': 1}, {'document_id': 2}]}),
    ('update_document_thread', {'thread_id': 1, 'title': 'Revised thread'}),
    ('dissolve_document_thread', {'thread_id': 1}),
], ids=lambda value: value if isinstance(value, str) else None)
def test_formerly_open_root_rejects_unknown_argument(name, arguments, documents_credential, monkeypatch):
    tool = next(tool for tool in TOOLS_BY_SLUG['documents'] if tool['name'] == name)
    boundary = _block_execution_callbacks(tool, monkeypatch)
    unknown = '__native_unknown_argument__'

    result = assert_no_writes(
        call_tool_inprocess, 'documents', name, {**arguments, unknown: True},
        credential=documents_credential,
    )

    boundary.assert_not_called()
    assert result == {
        'ok': False,
        'error': {
            'code': 'unknown_field',
            'message': f'{unknown}: Campo desconocido o de solo lectura.',
            'details': {
                unknown: ['Campo desconocido o de solo lectura.'],
                'errors': [{
                    'field': unknown, 'code': 'unknown_field',
                    'message': 'Campo desconocido o de solo lectura.',
                }],
            },
        },
    }


def test_missing_message_argument_keeps_its_field_name():
    boundary = Mock(side_effect=AssertionError('A missing message reached its handler'))
    tool = {
        'name': 'private_note', 'strict_arguments': True,
        'input_schema': {
            'type': 'object', 'properties': {'message': {'type': 'string'}},
            'required': ['message'], 'additionalProperties': False,
        },
        'handler': boundary,
    }

    _, response = handle_message({
        'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
        'params': {'name': tool['name'], 'arguments': {}},
    }, [tool])

    boundary.assert_not_called()
    assert response['result']['structuredContent']['error'] == {
        'code': 'VALIDATION_ERROR', 'message': 'message es obligatorio.',
        'details': {
            'message': ['message es obligatorio.'], 'detail': 'message es obligatorio.',
            'errors': [{
                'field': 'message', 'code': 'required', 'message': 'message es obligatorio.',
            }],
        },
    }


@pytest.mark.parametrize(('value', 'field', 'error_code', 'text'), [
    (serializers.ErrorDetail('Falta el mensaje.', code='required'), 'message', 'required', 'Falta el mensaje.'),
    ([serializers.ErrorDetail('Falta el mensaje.', code='required')], 'message', 'required', 'Falta el mensaje.'),
    ({'subject': [serializers.ErrorDetail('Asunto inválido.', code='invalid')]}, 'message.subject', 'invalid', 'Asunto inválido.'),
], ids=['scalar', 'list', 'nested'])
def test_serializer_message_error_keeps_its_field_path(value, field, error_code, text):
    payload = {'message': value}

    message, code, details = normalize_error(payload)

    assert (message, code, details['errors']) == (
        text, 'VALIDATION_ERROR',
        [{'field': field, 'code': error_code, 'message': text}],
    )


def test_error_envelope_message_keeps_its_text():
    payload = {
        'message': 'La acción está bloqueada.', 'code': 'conflict',
        'document_id': [serializers.ErrorDetail('Documento inválido.', code='invalid')],
    }

    message, code, details = normalize_error(payload)

    assert (message, code, details['errors']) == (
        'La acción está bloqueada.', 'CONFLICT',
        [{'field': 'document_id', 'code': 'invalid', 'message': 'Documento inválido.'}],
    )
