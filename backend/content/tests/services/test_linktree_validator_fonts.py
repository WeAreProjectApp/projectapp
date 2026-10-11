"""Google Fonts are fetched on the Django side with the browser's old whitelist."""
import base64
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from content.services.linktree_templates import fonts as google_fonts
from content.services.linktree_templates.validation import validate_in_browser
from linktree_sandbox import worker

CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter&display=swap'
LATIN = 'https://fonts.gstatic.com/s/inter/v1/latin.woff2'
CYRILLIC = 'https://fonts.gstatic.com/s/inter/v1/cyrillic.woff2'
FOREIGN = 'https://cdn.example.com/s/inter.woff2'
CSS = (
    f"@font-face{{font-family:'Inter';src:url({CYRILLIC}) format('woff2');unicode-range:U+0400-045F}}"
    f"@font-face{{font-family:'Inter';src:url({LATIN}) format('woff2');unicode-range:U+0000-00FF,U+2000-206F}}"
    f"@font-face{{font-family:'Inter';src:url({FOREIGN}) format('woff2')}}"
)


class FakeResponse:
    def __init__(self, status, body, content_type):
        self.status_code, self.body = status, body
        self.headers = {'content-type': content_type}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def iter_content(self, size):
        return (self.body[start:start + size] for start in range(0, len(self.body), size))


class FakeSession:
    """Answers from ``routes`` and records each request with the session's settings."""

    def __init__(self, routes, calls):
        self.routes, self.calls = routes, calls
        self.headers, self.trust_env = {}, True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **options):
        self.calls.append({'url': url, 'options': options, 'trust_env': self.trust_env,
                           'agent': self.headers.get('User-Agent', '')})
        return FakeResponse(*self.routes.get(url, (404, b'', 'text/plain')))


@pytest.fixture
def web(monkeypatch):
    """Route every font download to an in-memory map instead of the network."""
    routes, calls = {CSS_URL: (200, CSS.encode(), 'text/css')}, []
    monkeypatch.setattr(google_fonts.requests, 'Session', lambda: FakeSession(routes, calls))
    return routes, calls


def test_prefetch_downloads_only_whitelisted_files_the_text_uses(web):
    """Fails if Django downloads a font outside the old whitelist or a subset the text never renders."""
    routes, calls = web
    routes.update({LATIN: (200, b'latin', 'font/woff2'), CYRILLIC: (200, b'cyrillic', 'font/woff2')})

    fonts = google_fonts.prefetch(CSS_URL, '<main>Hola, ¿cómo estás?</main>')

    assert list(fonts) == [CSS_URL, LATIN]
    assert [call['url'] for call in calls] == [CSS_URL, LATIN]
    assert all(call['options'] == {'timeout': 5, 'allow_redirects': False, 'stream': True} for call in calls)
    assert all(call['trust_env'] is False and 'Chrome/' in call['agent'] for call in calls)


@pytest.mark.parametrize('answer', [(302, b'', 'text/html'), (404, b'', 'text/plain'),
                                    (200, b'x' * (2 * 1024 * 1024 + 1), 'font/woff2')],
                         ids=('redirect', 'not_found', 'over_two_mib'))
def test_prefetch_leaves_out_a_file_that_breaks_a_rule(web, answer):
    """Fails if a redirected, failed or oversized font file still reaches the worker."""
    routes, _ = web
    routes[LATIN] = answer

    assert list(google_fonts.prefetch(CSS_URL, '<main>Hola</main>')) == [CSS_URL]


def test_prefetch_stops_at_forty_files_counting_the_css(web):
    """Fails if Django sends the browser more font files than it was ever allowed to load."""
    routes, calls = web
    urls = [f'https://fonts.gstatic.com/s/inter/v1/{n}.woff2' for n in range(45)]
    routes[CSS_URL] = (200, ''.join(f'@font-face{{src:url({url});unicode-range:U+0000-00FF}}' for url in urls).encode(),
                       'text/css')
    routes.update({url: (200, b'font', 'font/woff2') for url in urls})

    fonts = google_fonts.prefetch(CSS_URL, '<main>Hola</main>')

    assert len(fonts) == worker.MAX_FONT_FILES
    assert urls[39] not in [call['url'] for call in calls]


def test_second_pass_carries_exactly_the_fonts_chromium_requested(web):
    """Fails if a font Chromium asked for is never fetched, leaving a false font error."""
    routes, _ = web
    routes[CYRILLIC] = (200, b'cyrillic', 'font/woff2')
    fonts = {CSS_URL: (CSS.encode(), 'text/css'), LATIN: (b'latin', 'font/woff2')}

    retry = google_fonts.complete(fonts, CSS_URL, [CSS_URL, CYRILLIC, FOREIGN])

    assert list(retry) == [CSS_URL, CYRILLIC]


def test_no_second_pass_without_a_missing_font_or_without_the_css(web):
    """Fails if validation repeats Chromium when nothing was missing or the CSS itself never arrived."""
    fonts = {CSS_URL: (CSS.encode(), 'text/css'), LATIN: (b'latin', 'font/woff2')}

    assert google_fonts.complete(fonts, CSS_URL, [CSS_URL, LATIN]) is None
    assert google_fonts.complete({}, CSS_URL, [CSS_URL]) is None


def test_validation_reruns_once_with_the_font_the_guess_missed(web, monkeypatch, settings):
    """Fails if a font outside the unicode-range guess ends as a false resource_load error."""
    routes, _ = web
    routes.update({LATIN: (200, b'latin', 'font/woff2'), CYRILLIC: (200, b'cyrillic', 'font/woff2')})
    sent = []

    def serve(payload, executable_path=None):
        request = json.loads(payload)
        sent.append(list(request['fonts']))
        served = sum(len(base64.b64decode(request['fonts'][url]['b64']))
                     for url in (CSS_URL, CYRILLIC) if url in request['fonts'])
        issues = [] if CYRILLIC in request['fonts'] else [
            {'severity': 'error', 'code': 'resource_load', 'message': worker.FONT_FAILURE}]
        return json.dumps({'v': 1, 'issues': issues, 'page_bytes': len(request['document'].encode()) + served,
                           'fonts_requested': [CSS_URL, CYRILLIC], 'screenshots': {}}).encode()

    monkeypatch.setattr(worker, 'serve', serve)
    template = SimpleNamespace(warnings=[], manifest={'fonts': ['Inter'], 'motion': False})
    candidate = SimpleNamespace(id=uuid4(), template=template, profile={}, assets={}, document='<main>Hola</main>')

    report, _ = validate_in_browser(candidate)

    assert sent == [[CSS_URL, LATIN], [CSS_URL, CYRILLIC]]
    assert report['issues'] == []


class FakeRoute:
    def __init__(self, url):
        self.request = SimpleNamespace(url=url)
        self.outcome = None

    def fulfill(self, **options):
        self.outcome = 'fulfill'

    def abort(self):
        self.outcome = 'abort'


def route(router, url):
    """Send one browser request through the worker's router and return how it ended."""
    pending = FakeRoute(url)
    router(pending)
    return pending.outcome


def test_router_serves_fonts_once_from_the_map_and_aborts_the_rest():
    """Fails if the worker reaches the network, double-counts a font or hides today's font error."""
    request = worker.parse_request(json.dumps({
        'v': 1, 'document': '<main>Hola</main>', 'csp': "default-src 'none'", 'widths': [320], 'resources': {},
        'fonts': {LATIN: {'mime': 'font/woff2', 'b64': base64.b64encode(b'latin').decode()}},
        'google_css': CSS_URL, 'motion_declared': False, 'pwa_enabled': False,
    }).encode())
    state = {'failures': set(), 'requested': [], 'served': set(), 'page_bytes': 0}
    router = worker.make_router(request, state)

    outcomes = [route(router, LATIN), route(router, LATIN), route(router, CYRILLIC), route(router, FOREIGN)]

    assert outcomes == ['fulfill', 'fulfill', 'abort', 'abort']
    assert state['page_bytes'] == len(b'latin')
    assert state['requested'] == [LATIN, CYRILLIC]
    assert state['failures'] == {worker.FONT_FAILURE, worker.UNAUTHORIZED}
