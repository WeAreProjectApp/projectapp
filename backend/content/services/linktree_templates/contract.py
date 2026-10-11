"""The Linktree validator wire contract, enforced on the Django side.

The browser worker is untrusted: its reply is checked here before anything is
stored, and any deviation keeps the version invalid (``run_validation`` turns
the exception into ``validator_unavailable``). docs/LINKTREE_HTML_TEMPLATES.md
documents the contract.
"""
import base64
import binascii
import io
import json

from PIL import Image

from linktree_sandbox import worker

# Every code the browser step emits (linktree_sandbox/worker.py and audit.js).
# page_weight is added on this side and static warnings never come from the worker.
KNOWN_CODES = frozenset({
    'animation_count', 'animation_property', 'complexity', 'continuous_text', 'contrast',
    'contrast_unverifiable', 'fixed_overlay', 'flash_rate', 'generated_text', 'motion_undeclared',
    'overflow', 'page_height', 'reduced_motion', 'resource_load', 'touch_target',
})
RESPONSE_KEYS = frozenset({'v', 'issues', 'page_bytes', 'fonts_requested', 'screenshots'})
ISSUE_REQUIRED = frozenset({'severity', 'code', 'message'})
ISSUE_KEYS = ISSUE_REQUIRED | {'file', 'line', 'node', 'width'}
ISSUE_FILES = frozenset({'template.html', 'template.css'})
SCREENSHOT_KEYS = frozenset(str(width) for width in worker.WIDTHS)
MAX_MESSAGE_CHARS = 300
MAX_NODE_CHARS = 64
MAX_LINE = 1_000_000
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


class ValidatorError(Exception):
    """The worker could not deliver a trustworthy result."""


def _check(condition, reason):
    if not condition:
        raise ValidatorError(reason)


def _issue(item):
    _check(isinstance(item, dict) and ISSUE_REQUIRED <= item.keys() <= ISSUE_KEYS, 'issue_keys')
    _check(item['severity'] in ('error', 'warning'), 'issue_severity')
    _check(isinstance(item['code'], str) and item['code'] in KNOWN_CODES, 'issue_code')
    _check(isinstance(item['message'], str) and len(item['message']) <= MAX_MESSAGE_CHARS, 'issue_message')
    if 'file' in item:
        _check(isinstance(item['file'], str) and item['file'] in ISSUE_FILES, 'issue_file')
    if 'line' in item:
        _check(type(item['line']) is int and 0 <= item['line'] <= MAX_LINE, 'issue_line')
    if 'node' in item:
        node = item['node']
        _check(node is None or (isinstance(node, str) and len(node) <= MAX_NODE_CHARS), 'issue_node')
    if 'width' in item:
        _check(type(item['width']) is int and item['width'] in worker.WIDTHS, 'issue_width')
    return item


def _screenshot(width, value):
    """A PNG exactly as wide as its viewport and at most 12 000 px tall; only the header is read."""
    _check(width in SCREENSHOT_KEYS, 'screenshot_key')
    _check(isinstance(value, str) and len(value) <= (worker.MAX_SCREENSHOT_BYTES + 2) // 3 * 4, 'screenshot_size')
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValidatorError('screenshot_encoding') from error
    _check(len(raw) <= worker.MAX_SCREENSHOT_BYTES and raw.startswith(PNG_SIGNATURE), 'screenshot_png')
    try:
        # Image.open is lazy: it parses the header and applies Pillow's decompression-bomb limit.
        with Image.open(io.BytesIO(raw)) as image:
            kind, (pixels_wide, pixels_high) = image.format, image.size
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise ValidatorError('screenshot_png') from error
    _check(kind == 'PNG' and pixels_wide == int(width) and 0 < pixels_high <= worker.MAX_SCREENSHOT_HEIGHT,
           'screenshot_dimensions')
    return raw


def decode_response(raw, *, document_bytes, google_css, font_sizes):
    """Check one worker reply; return its issues, measured bytes, requested fonts and PNG bytes."""
    _check(len(raw) <= worker.MAX_RESPONSE_BYTES, 'response_too_large')
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise ValidatorError('response_json') from error
    _check(isinstance(data, dict), 'response_shape')
    if data.keys() == {'v', 'error'}:
        code = data['error'] if isinstance(data['error'], str) and data['error'].isidentifier() else 'unknown'
        raise ValidatorError(f'worker_error:{code[:64]}')
    _check(data.keys() == RESPONSE_KEYS and type(data['v']) is int and data['v'] == worker.PROTOCOL, 'response_keys')

    issues = data['issues']
    _check(isinstance(issues, list) and len(issues) <= worker.MAX_ISSUES, 'issues')
    issues = [_issue(item) for item in issues]

    requested = data['fonts_requested']
    _check(isinstance(requested, list) and len(requested) <= worker.MAX_FONTS_REQUESTED, 'fonts_requested')
    _check(all(isinstance(url, str) and len(url) <= worker.MAX_URL_CHARS and worker.is_font_request(url, google_css)
               for url in requested) and len(set(requested)) == len(requested), 'fonts_requested')

    # The worker counts the document and each font it served once, so the figure is exact.
    expected = document_bytes + sum(font_sizes[url] for url in requested if url in font_sizes)
    _check(type(data['page_bytes']) is int and data['page_bytes'] == expected, 'page_bytes')

    _check(isinstance(data['screenshots'], dict), 'screenshots')
    screenshots = {width: _screenshot(width, value) for width, value in data['screenshots'].items()}
    return {'issues': issues, 'page_bytes': data['page_bytes'], 'fonts_requested': requested,
            'screenshots': screenshots}
