"""Linktree template browser checks, isolated from Django.

One JSON request in, one JSON response out. The same code answers in-process
(``serve``) and behind a systemd socket unit (``python -E -s worker.py`` with
stdin/stdout bound to the accepted connection). It imports only the standard
library, Playwright and Pillow, and it never reads Django settings, the
project's ``.env`` or the network: the document, the template's images and the
Google Fonts files arrive in the request, and every other browser request is
aborted. The contract is documented in docs/LINKTREE_HTML_TEMPLATES.md.
"""
import base64
import binascii
import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

PROTOCOL = 1
WIDTHS = (320, 375, 430)
DOCUMENT_URL = 'https://template.invalid/'
GOOGLE_CSS_PREFIX = 'https://fonts.googleapis.com/css2?'
MAX_SCREENSHOT_HEIGHT = 12000

# Contract limits, pinned by tests. Byte sizes count decoded content unless the
# name says request/response; docs/LINKTREE_HTML_TEMPLATES.md derives them.
MAX_REQUEST_BYTES = 96 * 1024 * 1024
MAX_RESPONSE_BYTES = 81 * 1024 * 1024
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_CSP_BYTES = 4096
MAX_URL_CHARS = 2048
MAX_RESOURCES = 384
MAX_RESOURCE_BYTES = 6 * 1024 * 1024
MAX_RESOURCES_BYTES = 48 * 1024 * 1024
MAX_FONT_FILES = 40  # the Google CSS counts, as it always did
MAX_FONT_BYTES = 2 * 1024 * 1024
MAX_FONTS_BYTES = 16 * 1024 * 1024
MAX_FONTS_REQUESTED = 64
MAX_SCREENSHOT_BYTES = 20 * 1024 * 1024
MAX_ISSUES = 150

REQUEST_KEYS = frozenset({'v', 'document', 'csp', 'widths', 'resources', 'fonts', 'google_css',
                          'motion_declared', 'pwa_enabled'})
ENTRY_KEYS = frozenset({'mime', 'b64'})
RESOURCE_MIMES = frozenset({'image/webp', 'image/svg+xml', 'image/png', 'image/jpeg', 'image/gif', 'image/avif'})
FONT_FAILURE = 'No se pudieron cargar las fuentes de Google; vuelve a validar.'
UNAUTHORIZED = 'La plantilla intentó cargar un recurso no autorizado.'
GLYPH_STYLE = ('*{text-decoration-color:transparent!important}[data-contrast-glyph]{color:transparent!important;'
               '-webkit-text-fill-color:transparent!important;text-shadow:none!important}')
DEFAULT_PATH = '/usr/local/bin:/usr/bin:/bin'
AUDIT_SCRIPT = Path(__file__).with_name('audit.js')


class RequestError(ValueError):
    """The request is outside the contract; Chromium never starts."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def launch_options(home, executable_path=None):
    """Chromium sees a throwaway HOME and nothing else from this process; V8 runs without JIT."""
    options = {
        'headless': True, 'timeout': 15000, 'args': ['--js-flags=--jitless'],
        'env': {'HOME': home, 'PATH': os.environ.get('PATH', DEFAULT_PATH),
                'LANG': os.environ.get('LANG', 'C.UTF-8')},
    }
    if executable_path:
        options['executable_path'] = executable_path
    return options


def luminance(rgb):
    channels = [c / 255 for c in rgb]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast_issues(texts, background, width):
    image = Image.open(io.BytesIO(background)).convert('RGB')
    issues = []
    for text in texts:
        color = text['color']
        alpha = (color[3] if len(color) > 3 else 1) * text['opacity']
        minimum = 21.0
        for rect in text['rects']:
            # Sample the whole text rectangle, including gradients and textures.
            left, top = max(0, int(rect['x'])), max(0, int(rect['y']))
            right, bottom = min(image.width, int(rect['x'] + rect['width'])), min(image.height, int(rect['y'] + rect['height']))
            for y in range(top, bottom, max(1, (bottom - top) // 6)):
                for x in range(left, right, max(1, (right - left) // 30)):
                    bg = image.getpixel((x, y))
                    fg = [color[i] * alpha + bg[i] * (1 - alpha) for i in range(3)]
                    a, b = sorted((luminance(bg), luminance(fg)))
                    minimum = min(minimum, (b + 0.05) / (a + 0.05))
        if minimum + 0.01 < text['threshold']:
            issues.append({'severity': 'error', 'code': 'contrast', 'file': 'template.html',
                           'node': text['node'], 'line': text.get('line', 1), 'width': width,
                           'message': f'Contraste {minimum:.2f}:1; se requiere {text["threshold"]}:1.'})
    return issues


def _measure(session, viewport):
    """Measure Chrome layout boxes, including roots and generated pseudo-elements."""
    snapshot = session.send('DOMSnapshot.captureSnapshot', {
        'computedStyles': ['position', 'visibility'], 'includeDOMRects': True,
    })
    strings = snapshot['strings']
    document = snapshot['documents'][0]
    nodes, layout = document['nodes'], document['layout']
    pseudos = set(nodes.get('pseudoType', {}).get('index', []))
    issues, fixed = {}, False
    for index, node in enumerate(layout['nodeIndex']):
        style = [strings[value] for value in layout['styles'][index]]
        if style != ['fixed', 'visible']:
            continue
        fixed = True
        x, y, width, height = layout['bounds'][index]
        x -= document['scrollOffsetX']
        y -= document['scrollOffsetY']
        area = (max(0, min(viewport['width'], x + width) - max(0, x))
                * max(0, min(viewport['height'], y + height) - max(0, y)))
        if area <= viewport['width'] * viewport['height'] * 0.2:
            continue
        owner = nodes['parentIndex'][node] if node in pseudos else node
        attributes = [strings[value] for value in nodes['attributes'][owner]]
        attributes = dict(zip(attributes[::2], attributes[1::2]))
        issues[owner] = {
            'severity': 'error', 'code': 'fixed_overlay', 'file': 'template.html',
            'line': int(attributes.get('data-template-line', 1)),
            'node': attributes.get('data-template-node'),
            'message': 'Un elemento fijo cubre más del 20 % de la pantalla.',
        }
    return list(issues.values()), fixed


def fixed_overlay_issues(page):
    """Use rendered geometry both now and at animation keyframes/midpoints."""
    session = page.context.new_cdp_session(page)
    animations = None
    try:
        issues, fixed = _measure(session, page.viewport_size)
        if issues or not fixed:
            return issues
        animations = page.evaluate_handle('''() => document.getAnimations().map(animation => ({
            animation, time: animation.currentTime, state: animation.playState
        }))''')
        samples = animations.evaluate('''entries => entries.flatMap(({animation}, index) => {
            const timing = animation.effect.getTiming();
            if (!Number.isFinite(Number(timing.duration))) return [];
            const offsets = animation.effect.getKeyframes().map(frame => frame.computedOffset);
            const samples = [...offsets, ...offsets.slice(1).map((value, i) => (value + offsets[i]) / 2)];
            return samples.map(offset => ({index, time: Number(timing.delay) + Number(timing.duration) * Math.min(.99999, offset)}));
        })''')
        # Bound synchronous validation work; never silently skip unchecked motion.
        if len(samples) > 120:
            return [{'severity': 'error', 'code': 'complexity', 'file': 'template.css',
                     'line': 1, 'message': 'Reduce los fotogramas de animación para validar los elementos fijos.'}]
        animations.evaluate('entries => entries.forEach(({animation}) => animation.pause())')
        for sample in samples:
            animations.evaluate('''(entries, sample) => {
                entries.forEach(({animation, time}) => { animation.currentTime = time; });
                entries[sample.index].animation.currentTime = sample.time;
            }''', sample)
            measured, _ = _measure(session, page.viewport_size)
            if measured:
                return measured
        return []
    finally:
        if animations is not None:
            try:
                animations.evaluate('''entries => entries.forEach(({animation, time, state}) => {
                    animation.currentTime = time;
                    if (state === 'running') animation.play();
                    else if (state === 'idle') animation.cancel();
                    else if (state === 'finished') animation.finish();
                    else animation.pause();
                })''')
            finally:
                animations.dispose()
        session.detach()


def is_font_request(url, google_css):
    """The same whitelist as always: the manifest's exact Google CSS and Google's font files."""
    if google_css and url == google_css:
        return True
    parts = urlsplit(url)
    return parts.scheme == 'https' and parts.netloc == 'fonts.gstatic.com' and parts.path.startswith('/s/')


def make_router(request, state):
    """Serve only what the request carries; abort everything else (no route.fetch, no network)."""
    document, csp, google_css = request['document'], request['csp'], request['google_css']
    resources, fonts = request['resources'], request['fonts']

    def route_request(route):
        request_url = route.request.url
        url = urlsplit(request_url)
        if request_url == DOCUMENT_URL:
            return route.fulfill(body=document, content_type='text/html', headers={'Content-Security-Policy': csp})
        if url.netloc == 'template.invalid' and url.path in resources:
            raw, mime = resources[url.path]
            return route.fulfill(body=raw, content_type=mime)
        if is_font_request(request_url, google_css):
            if request_url not in state['requested']:
                state['requested'].append(request_url)
            if request_url not in fonts:
                state['failures'].add(FONT_FAILURE)
                return route.abort()
            raw, mime = fonts[request_url]
            if request_url not in state['served']:
                state['served'].add(request_url)
                state['page_bytes'] += len(raw)
            return route.fulfill(body=raw, content_type=mime, headers={'Access-Control-Allow-Origin': '*'})
        state['failures'].add(UNAUTHORIZED)
        return route.abort()

    return route_request


def _require(condition, code='invalid_request'):
    if not condition:
        raise RequestError(code)


def _text(value, limit):
    """A string whose UTF-8 encoding fits ``limit`` bytes."""
    _require(isinstance(value, str))
    try:
        size = len(value.encode())
    except UnicodeEncodeError as error:
        raise RequestError('invalid_request') from error
    _require(size <= limit, 'request_too_large')
    return value


def _decode(entry, limit, mimes=None):
    """Strict base64 checked against ``limit`` before and after decoding."""
    _require(isinstance(entry, dict) and entry.keys() == ENTRY_KEYS)
    mime, value = entry['mime'], entry['b64']
    _require(isinstance(mime, str) and (mime in mimes if mimes else len(mime) <= 128 and mime.isprintable()))
    _require(isinstance(value, str))
    _require(len(value) <= (limit + 2) // 3 * 4, 'request_too_large')
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise RequestError('invalid_request') from error
    _require(len(raw) <= limit, 'request_too_large')
    return raw, mime


def parse_request(raw):
    """Decode and check one request; anything outside the contract raises RequestError."""
    _require(len(raw) <= MAX_REQUEST_BYTES, 'request_too_large')
    try:
        data = json.loads(raw)
    except ValueError as error:
        raise RequestError('invalid_json') from error
    _require(isinstance(data, dict) and data.keys() == REQUEST_KEYS)
    _require(type(data['v']) is int and data['v'] == PROTOCOL)
    _require(type(data['motion_declared']) is bool and type(data['pwa_enabled']) is bool)
    widths = data['widths']
    _require(isinstance(widths, list) and 0 < len(widths) == len(set(map(repr, widths)))
             and all(type(width) is int and width in WIDTHS for width in widths))
    google_css = data['google_css']
    _require(isinstance(google_css, str) and len(google_css) <= MAX_URL_CHARS
             and (google_css == '' or google_css.startswith(GOOGLE_CSS_PREFIX)))

    resources, total = {}, 0
    _require(isinstance(data['resources'], dict), 'invalid_request')
    _require(len(data['resources']) <= MAX_RESOURCES, 'request_too_large')
    for path, entry in data['resources'].items():
        _require(path.startswith('/') and len(path) <= MAX_URL_CHARS)
        resources[path] = _decode(entry, MAX_RESOURCE_BYTES, RESOURCE_MIMES)
        total += len(resources[path][0])
        _require(total <= MAX_RESOURCES_BYTES, 'request_too_large')

    fonts, total = {}, 0
    _require(isinstance(data['fonts'], dict), 'invalid_request')
    _require(len(data['fonts']) <= MAX_FONT_FILES, 'request_too_large')
    for url, entry in data['fonts'].items():
        _require(len(url) <= MAX_URL_CHARS and is_font_request(url, google_css))
        fonts[url] = _decode(entry, MAX_FONT_BYTES)
        total += len(fonts[url][0])
        _require(total <= MAX_FONTS_BYTES, 'request_too_large')

    return {'document': _text(data['document'], MAX_DOCUMENT_BYTES), 'csp': _text(data['csp'], MAX_CSP_BYTES),
            'widths': widths, 'resources': resources, 'fonts': fonts, 'google_css': google_css,
            'motion_declared': data['motion_declared'], 'pwa_enabled': data['pwa_enabled']}


def run(request, executable_path=None):
    """Render the candidate at each width with the checks the validator always ran."""
    source = AUDIT_SCRIPT.read_text()
    state = {'failures': set(), 'requested': [], 'served': set(), 'page_bytes': len(request['document'].encode())}
    notices, screenshots = [], {}
    with tempfile.TemporaryDirectory(prefix='linktree-chromium-') as home, sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options(home, executable_path))
        try:
            context = browser.new_context(service_workers='block', device_scale_factor=1, reduced_motion='no-preference')
            context.set_default_timeout(8000)
            context.route('**/*', make_router(request, state))
            for width in request['widths']:
                page = context.new_page()
                page.set_viewport_size({'width': width, 'height': 900})
                page.goto(DOCUMENT_URL, wait_until='load', timeout=20000)
                page.evaluate('() => document.fonts.ready')
                page.evaluate('() => Promise.all([...document.images].map(i => i.decode().catch(() => null)))')
                if request['pwa_enabled']:
                    page.locator('[data-action="install-pwa"]').evaluate_all('(elements) => elements.forEach(el => { el.hidden = false; })')
                notices.extend({**entry, 'width': width} for entry in fixed_overlay_issues(page))
                audit = page.evaluate(source)
                notices.extend({**entry, 'width': width} for entry in audit['issues'])
                if audit['animated'] and not request['motion_declared']:
                    notices.append({'severity': 'error', 'code': 'motion_undeclared', 'message': 'Declara motion: true para utilizar animaciones.', 'width': width})
                if page.locator('body').evaluate('(el) => el.scrollHeight') <= MAX_SCREENSHOT_HEIGHT:
                    # The kept capture is cropped to the viewport so its size is predictable;
                    # contrast still samples the full page, as it always did.
                    screenshots[str(width)] = page.screenshot(
                        full_page=True, animations='disabled', timeout=8000,
                        clip={'x': 0, 'y': 0, 'width': width, 'height': MAX_SCREENSHOT_HEIGHT})
                    page.add_style_tag(content=GLYPH_STYLE)
                    background = page.screenshot(full_page=True, animations='disabled', timeout=8000)
                    notices.extend(contrast_issues(audit['texts'], background, width))
                page.emulate_media(reduced_motion='reduce')
                if page.evaluate('() => document.getAnimations().some(a => a.playState === "running")'):
                    notices.append({'severity': 'error', 'code': 'reduced_motion', 'message': 'La preferencia de movimiento reducido no detiene todas las animaciones.', 'width': width})
                page.close()
            context.close()
        finally:
            browser.close()
    notices.extend({'severity': 'error', 'code': 'resource_load', 'message': message} for message in sorted(state['failures']))
    # Deduplicate repeated text issues, preserving the measured viewport.
    unique = {str(sorted(item.items())): item for item in notices}
    return {'v': PROTOCOL, 'issues': list(unique.values())[:MAX_ISSUES], 'page_bytes': state['page_bytes'],
            'fonts_requested': state['requested'][:MAX_FONTS_REQUESTED], 'screenshots': screenshots}


def _encode(payload):
    return json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def serve(raw, executable_path=None):
    """Answer one request; never raises, so every transport gets a well-formed reply."""
    try:
        request = parse_request(raw)
    except RequestError as error:
        logger.warning('Rejected Linktree validator request: %s', error.code)
        return _encode({'v': PROTOCOL, 'error': error.code})
    try:
        result = run(request, executable_path)
        result['screenshots'] = {width: base64.b64encode(png).decode('ascii')
                                 for width, png in result['screenshots'].items()}
        reply = _encode(result)
    except Exception:
        logger.exception('Linktree browser validation failed')
        return _encode({'v': PROTOCOL, 'error': 'browser_failed'})
    if len(reply) > MAX_RESPONSE_BYTES:
        return _encode({'v': PROTOCOL, 'error': 'response_too_large'})
    return reply


def main(stdin=None, stdout=None):
    """Socket-unit entry point: one request on stdin, one reply on stdout."""
    source = stdin if stdin is not None else sys.stdin.buffer
    sink = stdout if stdout is not None else sys.stdout.buffer
    reply = serve(source.read(MAX_REQUEST_BYTES + 1), os.environ.get('LINKTREE_CHROMIUM_EXECUTABLE') or None)
    sink.write(reply)
    sink.flush()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(levelname)s %(name)s: %(message)s')
    main()
