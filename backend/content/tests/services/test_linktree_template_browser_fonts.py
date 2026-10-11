"""Google Fonts through the isolated worker; these tests run real headless Chromium."""
from types import SimpleNamespace
from uuid import uuid4

from content.services.linktree_templates import fonts as google_fonts
from content.services.linktree_templates.render import render_document
from content.services.linktree_templates.validation import validate_in_browser
from linktree_sandbox.worker import FONT_FAILURE

CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter&display=swap'
LATIN = 'https://fonts.gstatic.com/s/inter/v1/latin.woff2'


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
    """Answers font downloads from ``routes``; anything else is a 404."""

    def __init__(self, routes):
        self.routes, self.headers, self.trust_env = routes, {}, True

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url, **options):
        return FakeResponse(*self.routes.get(url, (404, b'', 'text/plain')))


def version():
    """A rendered candidate that declares the Inter Google font."""
    template = SimpleNamespace(
        html='<main><h1>{{name}}</h1>{{#links}}<a data-link href="{{url}}">{{label}}</a>{{/links}}</main>',
        css=("body{margin:0;background:#fff;color:#111;font-family:'Inter',sans-serif}main{padding:16px}"
             'a{display:flex;align-items:center;min-height:48px;color:#111;background:#fff}'),
        warnings=[], manifest={'fonts': ['Inter'], 'motion': False, 'max_width': 480},
    )
    profile = {'name': 'Font test', 'contact': {'email': '', 'tel': ''}, 'buttons': [{
        'label': 'Visit site', 'url': 'https://example.com', 'key': '1', 'tier': 'primary', 'icon': 'globe',
        'kind': 'web',
    }]}
    row = SimpleNamespace(id=uuid4(), template=template, profile=profile, assets={})
    row.document = render_document(row)
    return row


def test_unreachable_google_css_still_reports_the_known_font_error(monkeypatch, settings):
    """Fails if a Google Fonts outage stops producing the resource_load error authors already know."""
    monkeypatch.setattr(google_fonts.requests, 'Session', lambda: FakeSession({}))

    report, screenshots = validate_in_browser(version())

    assert {'severity': 'error', 'code': 'resource_load', 'message': FONT_FAILURE} in report['issues']
    assert set(screenshots) == {'320', '375', '430'}


def test_font_delivered_by_django_counts_once_toward_page_weight(monkeypatch, settings):
    """Fails if fonts sent by Django stop counting toward page weight as the browser's downloads did."""
    css = f"@font-face{{font-family:'Inter';src:url({LATIN}) format('woff2');unicode-range:U+0000-00FF}}".encode()
    font = b'synthetic-font-bytes'
    routes = {CSS_URL: (200, css, 'text/css'), LATIN: (200, font, 'font/woff2')}
    monkeypatch.setattr(google_fonts.requests, 'Session', lambda: FakeSession(routes))
    row = version()

    report, _ = validate_in_browser(row)

    assert not any(issue['code'] == 'resource_load' for issue in report['issues'])
    assert report['page_bytes'] == len(row.document.encode()) + len(css) + len(font)
