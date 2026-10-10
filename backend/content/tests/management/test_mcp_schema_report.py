"""Local reports, safe remote discovery and version-bump enforcement."""
import io
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from requests import ConnectionError as RequestConnectionError

from content.management.commands import mcp_schema_report
from content.mcp.connectors import CONNECTORS, TOOLS_BY_SLUG
from content.mcp.contract_report import SERVER_INFO_KEY, compare, fingerprint, local_snapshot, remote_snapshot
from content.mcp.protocol import handle_message


TOKEN = 'mock-bearer-secret-for-report-tests'
REMOTE_URL = 'https://mcp.example'
TOOL_NAME = TOOLS_BY_SLUG['blog'][0]['name']


def _run(*args):
    stdout, stderr = io.StringIO(), io.StringIO()
    call_command('mcp_schema_report', *args, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


def _remote_reply(url, *, json, headers, timeout, allow_redirects):
    slug = url.rstrip('/').rsplit('/', 1)[-1]
    status, body = handle_message(json, TOOLS_BY_SLUG[slug], connector=CONNECTORS[slug])
    if 'MCP-Protocol-Version' in headers:
        body['result'].setdefault('_meta', {})[SERVER_INFO_KEY] = CONNECTORS[slug].server_info
    response = Mock(status_code=status)
    response.json.return_value = body
    return response


def _different_reply(field):
    def reply(*args, **kwargs):
        response = _remote_reply(*args, **kwargs)
        if kwargs['json']['method'] == 'tools/call':
            tools = response.json.return_value['result']['structuredContent']['tools']
            next(tool for tool in tools if tool['name'] == TOOL_NAME)[field] = 'changed-contract'
        return response
    return reply


@pytest.fixture
def remote_session(monkeypatch):
    session = MagicMock(spec=requests.Session)
    session.__enter__.return_value = session
    session.post.side_effect = _remote_reply
    monkeypatch.setattr(mcp_schema_report.requests, 'Session', Mock(return_value=session))
    monkeypatch.setenv('MCP_TOKEN_BLOG', TOKEN)
    return session


@pytest.fixture
def lock_path(tmp_path, monkeypatch):
    path = tmp_path / 'connector_contracts.json'
    monkeypatch.setattr(mcp_schema_report, 'CONTRACTS_PATH', path)
    return path


def test_local_report_contains_every_connector():
    stdout, stderr = _run('--format', 'json')
    results = json.loads(stdout)

    assert {result['slug'] for result in results} == set(CONNECTORS)
    assert all(result['ok'] for result in results)
    assert stderr == ''


def test_local_markdown_report_contains_contract_columns():
    stdout, _ = _run('--slug', 'blog')

    assert '| Conector | serverInfo (initialize) | serverInfo (discover) |' in stdout
    assert '| genéricas pendientes | abiertos documentados | huella |' in stdout
    assert fingerprint('blog')[:12] in stdout
    assert '## Diferencias\n\nNinguna.' in stdout


def test_slug_option_selects_repeated_connectors():
    stdout, _ = _run('--slug', 'tasks', '--slug', 'blog', '--format', 'json')

    assert [result['slug'] for result in json.loads(stdout)] == ['blog', 'tasks']


def test_remote_requests_use_bearer_without_exposing_token(remote_session, caplog):
    """Both transport eras use the required headers and keep tokens off output."""
    stdout, stderr = _run('--remote', REMOTE_URL, '--slug', 'blog')
    calls = remote_session.post.call_args_list
    modern = calls[1:]

    assert len(calls) == 4
    assert all(call.args == (f'{REMOTE_URL}/api/mcp/blog/',) for call in calls)
    assert all(call.kwargs['headers']['Authorization'] == f'Bearer {TOKEN}' for call in calls)
    assert all(call.kwargs['timeout'] == 20 and call.kwargs['headers']['Cache-Control'] == 'no-cache' and call.kwargs['headers']['Pragma'] == 'no-cache' and call.kwargs['headers']['Content-Type'] == 'application/json' for call in calls)
    assert calls[0].kwargs['json']['params']['protocolVersion'] == '2025-11-25'
    assert all(call.kwargs['headers']['MCP-Protocol-Version'] == '2026-07-28' and call.kwargs['headers']['Mcp-Method'] == call.kwargs['json']['method'] for call in modern)
    assert TOKEN not in stdout + stderr + caplog.text


def test_remote_capabilities_call_declares_tool_header(remote_session):
    _run('--remote', REMOTE_URL, '--slug', 'blog')
    request = remote_session.post.call_args_list[-1].kwargs

    assert request['headers']['Mcp-Name'] == 'describe_capabilities'
    assert request['json']['params']['_meta']['io.modelcontextprotocol/clientCapabilities'] == {}


def test_remote_report_omits_local_metrics(remote_session):
    stdout, _ = _run('--remote', REMOTE_URL, '--slug', 'blog', '--format', 'json')
    result = json.loads(stdout)[0]

    assert 'registry' not in result['versions']
    assert result['generic_pending'] is None
    assert result['documented_open_nodes'] is None
    assert result['fingerprint'] is None


@pytest.mark.parametrize('field,public_field', [
    ('input_schema', 'inputSchema'), ('output_schema', 'outputSchema'),
    ('description', 'description'), ('title', 'title'), ('annotations', 'annotations'),
])
def test_remote_mismatch_reports_tool(remote_session, field, public_field):
    """Every public-field mismatch prints its tool before failing the command."""
    remote_session.post.side_effect = _different_reply(field)
    stdout = io.StringIO()

    with pytest.raises(CommandError, match='blog') as error:
        call_command('mcp_schema_report', '--remote', REMOTE_URL, '--slug', 'blog', stdout=stdout)

    assert error.value.returncode == 1
    assert TOOL_NAME in stdout.getvalue()
    assert public_field in stdout.getvalue()
    assert TOKEN not in stdout.getvalue()


def test_missing_token_prevents_every_request(remote_session, monkeypatch):
    monkeypatch.delenv('MCP_TOKEN_TASKS', raising=False)

    with pytest.raises(CommandError, match='MCP_TOKEN_TASKS'):
        _run('--remote', REMOTE_URL, '--slug', 'blog', '--slug', 'tasks')

    remote_session.post.assert_not_called()


def test_token_template_normalizes_connector_slug(remote_session, monkeypatch):
    monkeypatch.setenv('CUSTOM_ACCOUNTING_LEDGER_SECRET', TOKEN)

    stdout, _ = _run('--remote', REMOTE_URL, '--slug', 'accounting-ledger', '--token-env-template', 'CUSTOM_{SLUG}_SECRET')

    assert '| accounting-ledger |' in stdout
    assert remote_session.post.call_args.kwargs['headers']['Authorization'] == f'Bearer {TOKEN}'


def test_remote_404_reports_inactive_connector(remote_session):
    remote_session.post.side_effect = None
    remote_session.post.return_value = SimpleNamespace(status_code=404)

    with pytest.raises(CommandError, match='conector inactivo o token inválido'):
        _run('--remote', REMOTE_URL, '--slug', 'blog')

    assert remote_session.post.call_count == 1


def test_remote_network_error_hides_credentials(remote_session, caplog):
    remote_session.post.side_effect = RequestConnectionError(f'Failed with {TOKEN}')

    with pytest.raises(CommandError, match='No se pudo consultar initialize') as error:
        _run('--remote', REMOTE_URL, '--slug', 'blog')

    assert TOKEN not in str(error.value) + caplog.text


def test_remote_snapshot_redacts_echoed_credentials(remote_session):
    """A remote server cannot echo the credential into a captured snapshot."""
    original_reply = remote_session.post.side_effect

    def echoed_reply(*args, **kwargs):
        response = original_reply(*args, **kwargs)
        response.json.return_value['result']['echo'] = TOKEN
        return response

    remote_session.post.side_effect = echoed_reply
    snapshot = remote_snapshot(REMOTE_URL, 'blog', TOKEN, session=remote_session)

    assert TOKEN not in json.dumps(snapshot)
    assert snapshot['initialize']['echo'] == '[REDACTADO]'


@pytest.mark.parametrize('channel', ['initialize', 'discover', 'capabilities', 'tools_list'])
def test_compare_rejects_version_disagreement(channel):
    """Every announced version, including optional list metadata, is checked."""
    snapshot = local_snapshot('blog')
    locations = {
        'initialize': snapshot['initialize']['serverInfo'],
        'discover': snapshot['discover']['_meta'][SERVER_INFO_KEY],
        'capabilities': snapshot['capabilities'],
        'tools_list': snapshot['tools_list'].setdefault('_meta', {}).setdefault(SERVER_INFO_KEY, dict(CONNECTORS['blog'].server_info)),
    }
    locations[channel]['version'] = '99.0.0'

    result = compare(snapshot)

    assert result['ok'] is False
    assert result['versions_match'] is False


def test_compare_reports_names_on_both_sides():
    snapshot = local_snapshot('blog')
    listed_name = snapshot['tools_list']['tools'][0]['name']
    snapshot['capabilities']['tools'][0]['name'] = 'remote_only_tool'

    result = compare(snapshot)

    assert result['only_tools_list'] == [listed_name]
    assert result['only_describe'] == ['remote_only_tool']
    assert result['ok'] is False


def test_write_fingerprints_requires_version_bump(lock_path):
    """A changed contract cannot overwrite a lock at the same version."""
    existing = {'blog': {'version': CONNECTORS['blog'].version, 'sha256': '0' * 64}}
    lock_path.write_text(json.dumps(existing))
    before = lock_path.read_bytes()

    with pytest.raises(CommandError, match='blog') as error:
        _run('--slug', 'blog', '--write-fingerprints')

    assert error.value.returncode == 1
    assert lock_path.read_bytes() == before


def test_write_fingerprints_accepts_bumped_version(lock_path):
    lock_path.write_text(json.dumps({'blog': {'version': '0.0.1', 'sha256': '0' * 64}}))

    _run('--slug', 'blog', '--write-fingerprints')

    assert json.loads(lock_path.read_text()) == {'blog': {'version': CONNECTORS['blog'].version, 'sha256': fingerprint('blog')}}
    assert lock_path.read_text().endswith('\n')


def test_write_fingerprints_creates_sorted_lock(lock_path):
    _run('--write-fingerprints')
    locked = json.loads(lock_path.read_text())

    assert list(locked) == sorted(CONNECTORS)
    assert all(entry == {'version': CONNECTORS[slug].version, 'sha256': fingerprint(slug)} for slug, entry in locked.items())


def test_write_fingerprints_preserves_unselected_connectors(lock_path):
    existing = {'tasks': {'version': CONNECTORS['tasks'].version, 'sha256': fingerprint('tasks')}}
    lock_path.write_text(json.dumps(existing))

    _run('--slug', 'blog', '--write-fingerprints')

    assert json.loads(lock_path.read_text())['tasks'] == existing['tasks']


def test_print_backlog_emits_python_literals():
    stdout, _ = _run('--print-backlog')

    assert 'GENERIC_ADAPTER_BACKLOG = frozenset({' in stdout
    assert 'UNDESCRIBED_ARGUMENT_BACKLOG = frozenset({' in stdout
    assert 'DEFERRED_SCHEMA_BACKLOG = {' in stdout


@pytest.mark.parametrize('option', ['--print-backlog', '--write-fingerprints'])
def test_remote_rejects_local_only_actions(remote_session, option):
    with pytest.raises(CommandError, match='requieren el modo local'):
        _run('--remote', REMOTE_URL, '--slug', 'blog', option)

    remote_session.post.assert_not_called()
