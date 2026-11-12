"""Receiver filesystem behavior is real; only the HTTP transport is substituted."""
import hashlib
import io
import json
from unittest.mock import patch

import pytest

from hosting_guard.receiver import apply_target, atomic_state, cycle, fetch_enrolled, read_enrollment


def wire(**changes):
    value = {'schema': 1, 'target_key': 'fixture', 'environment': 'production', 'origins': ['https://fixture.example'], 'version': 1,
             'mode': 'banner', 'message': {'title': 'Pago de prueba', 'text': 'Mensaje de prueba'}}
    value.update(changes)
    value['digest'] = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return value


class WireResponse(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


def test_atomic_state_survives_new_receiver(tmp_path):
    path = tmp_path / 'state.json'
    value = wire()
    atomic_state(path, value)
    assert json.loads(path.read_text()) == value
    assert path.stat().st_mode & 0o777 == 0o640


def test_old_revision_cannot_replace_newer_state(tmp_path):
    path = tmp_path / 'state.json'
    atomic_state(path, wire(version=2))
    with pytest.raises(ValueError, match='Stale'):
        atomic_state(path, wire(version=1))
    assert json.loads(path.read_text())['version'] == 2


def test_conflicting_revision_cannot_replace_state(tmp_path):
    path = tmp_path / 'state.json'
    atomic_state(path, wire())
    with pytest.raises(ValueError, match='Conflicting'):
        atomic_state(path, wire(mode='suspended'))
    assert json.loads(path.read_text())['mode'] == 'banner'


def test_foreign_state_is_never_written(tmp_path):
    row = {'key': 'fixture', 'origins': ['https://fixture.example'], 'state_file': str(tmp_path / 'state.json')}
    with pytest.raises(ValueError, match='Foreign'):
        apply_target({}, row, wire(target_key='other'))
    assert not (tmp_path / 'state.json').exists()


def test_receipt_requires_document_adapter(tmp_path):
    value = wire()
    row = {'key': 'fixture', 'origins': value['origins'], 'state_file': str(tmp_path / 'state.json')}
    sent = []
    def respond(request, timeout):
        if request.full_url.endswith('/state'):
            return WireResponse(json.dumps({**value, 'ready': True, 'adapter_version': 1}).encode())
        if request.full_url.endswith('/receipts/'):
            sent.append(json.loads(request.data))
            return WireResponse(b'{}')
        return WireResponse(b'<html>Unintegrated document</html>')
    with patch('hosting_guard.receiver.build_opener') as opener:
        opener.return_value.open.side_effect = respond
        apply_target({'endpoint': 'https://central.example/api/hosting-runtime', 'token': 'fixture-only'}, row, value)
    assert sent[0]['applied'] is False


def test_matching_document_is_acknowledged(tmp_path):
    value = wire()
    row = {'key': 'fixture', 'origins': value['origins'], 'state_file': str(tmp_path / 'state.json')}
    sent = []
    def respond(request, timeout):
        if request.full_url.endswith('/state'):
            return WireResponse(json.dumps({**value, 'ready': True, 'adapter_version': 1}).encode())
        if request.full_url.endswith('/receipts/'):
            sent.append(json.loads(request.data))
            return WireResponse(b'{}')
        return WireResponse(b'<head><link href="/__hosting/notice.css"><script src="/__hosting/notice.js"></script></head>', headers={
            'X-Hosting-Version': '1', 'X-Hosting-Digest': value['digest'],
        })
    with patch('hosting_guard.receiver.build_opener') as opener:
        opener.return_value.open.side_effect = respond
        apply_target({'endpoint': 'https://central.example/api/hosting-runtime', 'token': 'fixture-only'}, row, value)
    assert sent[0]['applied'] is True


def test_central_failure_preserves_local_state(tmp_path):
    path = tmp_path / 'state.json'
    atomic_state(path, wire())
    with patch('hosting_guard.receiver.build_opener') as opener:
        opener.return_value.open.side_effect = OSError('fixture offline')
        with pytest.raises(OSError):
            cycle({'endpoint': 'https://central.example', 'token': 'fixture-only'})
    assert json.loads(path.read_text()) == wire()


def test_world_readable_credential_is_rejected(tmp_path):
    token = tmp_path / 'token'
    token.write_text('fixture-only')
    token.chmod(0o644)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'endpoint': 'https://central.example', 'token_file': str(token)}))
    with pytest.raises(ValueError, match='private file'):
        read_enrollment(config)


def test_canonical_alias_redirect_is_allowed():
    with patch('hosting_guard.receiver.build_opener') as opener:
        opener.return_value.open.side_effect = [WireResponse(b'', 301, {'Location': 'https://fixture.example/'}), WireResponse(b'normal')]
        code, _, body = fetch_enrolled('https://www.fixture.example/', ['https://fixture.example', 'https://www.fixture.example'])
    assert code == 200
    assert body == b'normal'


def test_foreign_redirect_is_rejected_before_contact():
    with patch('hosting_guard.receiver.build_opener') as opener:
        opener.return_value.open.return_value = WireResponse(b'', 301, {'Location': 'https://foreign.example/'})
        with pytest.raises(ValueError, match='outside'):
            fetch_enrolled('https://fixture.example/', ['https://fixture.example'])
        assert opener.return_value.open.call_count == 1
