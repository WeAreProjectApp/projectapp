"""The Linktree browser worker refuses requests outside its contract before Chromium starts."""
import io
import json

import pytest

from linktree_sandbox import worker

MIB = 1024 * 1024
FONT = {'mime': 'font/woff2', 'b64': 'AAAA'}


def fail_if_launched():
    """Stand-in for sync_playwright that must never be reached."""
    raise AssertionError('Chromium must not start for a rejected request')


def valid_request(**changes):
    """A request the worker accepts, with ``changes`` applied."""
    body = {'v': 1, 'document': '<main>Hola</main>', 'csp': "default-src 'none'", 'widths': [320, 375, 430],
            'resources': {'/api/linktrees/templates/1/assets/logo/1/': {'mime': 'image/webp', 'b64': 'AAAA'}},
            'fonts': {}, 'google_css': '', 'motion_declared': False, 'pwa_enabled': False}
    body.update(changes)
    return body


REFUSED = {
    'unknown_key': (valid_request(extra=1), 'invalid_request'),
    'boolean_version': (valid_request(v=True), 'invalid_request'),
    'foreign_width': (valid_request(widths=[320, 999]), 'invalid_request'),
    'html_resource': (valid_request(resources={'/page': {'mime': 'text/html', 'b64': 'AAAA'}}), 'invalid_request'),
    'foreign_font_host': (valid_request(fonts={'https://fonts.example.com/s/a.woff2': FONT}), 'invalid_request'),
    'broken_base64': (valid_request(resources={'/logo': {'mime': 'image/webp', 'b64': '%%%%'}}), 'invalid_request'),
    'forty_one_fonts': (valid_request(fonts={f'https://fonts.gstatic.com/s/f/{n}.woff2': FONT for n in range(41)}),
                        'request_too_large'),
}


@pytest.mark.parametrize('case', sorted(REFUSED))
def test_out_of_contract_request_is_refused_without_chromium(monkeypatch, case):
    """Fails if a request outside the contract can make the worker start Chromium."""
    monkeypatch.setattr(worker, 'sync_playwright', fail_if_launched)
    body, code = REFUSED[case]

    reply = json.loads(worker.serve(json.dumps(body).encode()))

    assert reply == {'v': 1, 'error': code}


def test_oversized_request_is_refused_before_it_is_parsed(monkeypatch):
    """Fails if the request size limit is checked only after decoding a huge JSON body."""
    monkeypatch.setattr(worker, 'sync_playwright', fail_if_launched)
    monkeypatch.setattr(worker, 'MAX_REQUEST_BYTES', 64)

    reply = json.loads(worker.serve(json.dumps(valid_request()).encode()))

    assert reply == {'v': 1, 'error': 'request_too_large'}


def test_socket_entry_point_answers_malformed_json(monkeypatch):
    """Fails if the socket entry point crashes instead of answering a malformed request on stdout."""
    monkeypatch.setattr(worker, 'sync_playwright', fail_if_launched)
    stdout = io.BytesIO()

    worker.main(stdin=io.BytesIO(b'{"v": 1,'), stdout=stdout)

    assert json.loads(stdout.getvalue()) == {'v': 1, 'error': 'invalid_json'}


def test_contract_limits_stay_pinned():
    """Fails if a contract limit changes without updating the socket contract documented for the toolkit."""
    limits = (worker.MAX_REQUEST_BYTES, worker.MAX_RESPONSE_BYTES, worker.MAX_DOCUMENT_BYTES, worker.MAX_RESOURCES,
              worker.MAX_RESOURCE_BYTES, worker.MAX_RESOURCES_BYTES, worker.MAX_FONT_FILES, worker.MAX_FONT_BYTES,
              worker.MAX_FONTS_BYTES, worker.MAX_SCREENSHOT_BYTES, worker.MAX_SCREENSHOT_HEIGHT, worker.MAX_ISSUES,
              worker.MAX_FONTS_REQUESTED)

    assert limits == (96 * MIB, 81 * MIB, 8 * MIB, 384, 6 * MIB, 48 * MIB, 40, 2 * MIB, 16 * MIB, 20 * MIB,
                      12000, 150, 64)
