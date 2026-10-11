"""Google Fonts are downloaded here, on the Django side, so the browser worker needs no network.

The whitelist is the one the browser always had: the manifest's exact Google CSS
URL and font files under https://fonts.gstatic.com/s/, without redirects, 5 s per
request, status 200 and at most 2 MiB per file, 40 files counting the CSS. Font
files are picked by the unicode-range that covers the document's characters;
when Chromium still asks for one that was not sent, ``complete`` returns exactly
the set it asked for and the validation runs once more (validation.py).
"""
import bisect
import time

import requests
import tinycss2

from linktree_sandbox import worker

# Google picks the font format from the User-Agent; a Chrome one gets the woff2
# files the headless browser received when it fetched the CSS itself.
USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/153.0.0.0 Safari/537.36')
TIMEOUT_SECONDS = 5
BUDGET_SECONDS = 30
CHUNK_BYTES = 64 * 1024
# Characters the browser renders without them appearing in the source: list
# markers, counters, quotes and ellipses.
GENERATED = '0123456789 .…‐-“”‘’«»•◦▪'


def _session():
    session = requests.Session()
    session.trust_env = False  # no proxies or netrc from the environment, like the browser's own fetch
    session.headers['User-Agent'] = USER_AGENT
    return session


def _fetch(session, url, deadline):
    """Download one whitelisted file, or None as soon as any rule is broken."""
    if time.monotonic() >= deadline:
        return None
    try:
        with session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                return None
            body = bytearray()
            for chunk in response.iter_content(CHUNK_BYTES):
                body.extend(chunk)
                if len(body) > worker.MAX_FONT_BYTES or time.monotonic() >= deadline:
                    return None
            return bytes(body), response.headers.get('content-type', '')
    except requests.RequestException:
        return None


def _url(token):
    if token.type == 'url':
        return token.value
    if token.type == 'function' and token.lower_name == 'url':
        strings = [argument.value for argument in token.arguments if argument.type == 'string']
        return strings[0] if strings else None
    return None


def font_faces(css):
    """(urls, ranges) for every @font-face rule; without unicode-range a face covers everything."""
    faces = []
    for rule in tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True):
        if rule.type != 'at-rule' or rule.lower_at_keyword != 'font-face' or rule.content is None:
            continue
        urls, ranges = [], [(0, 0x10FFFF)]
        for declaration in tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True):
            if declaration.type != 'declaration':
                continue
            if declaration.lower_name == 'src':
                urls += [url for url in map(_url, declaration.value) if url]
            elif declaration.lower_name == 'unicode-range':
                ranges = [(token.start, token.end) for token in declaration.value if token.type == 'unicode-range']
        faces.append((urls, ranges))
    return faces


def _codepoints(document):
    characters = set(document) | set(GENERATED)
    for character in list(characters):
        for variant in (character.upper(), character.lower(), character.casefold(), character.title()):
            characters.update(variant)
    return sorted(map(ord, characters))


def _covers(ranges, codepoints):
    for start, end in ranges:
        index = bisect.bisect_left(codepoints, start)
        if index < len(codepoints) and codepoints[index] <= end:
            return True
    return False


def candidates(css, document):
    """Google font files, in CSS order, whose unicode-range intersects the document's characters."""
    codepoints, urls = _codepoints(document), []
    for face_urls, ranges in font_faces(css):
        if _covers(ranges, codepoints):
            urls += [url for url in face_urls if worker.is_font_request(url, '') and url not in urls]
    return urls


def prefetch(google_css, document):
    """The CSS plus the candidate font files, as ``{url: (bytes, content_type)}``."""
    if not google_css:
        return {}
    deadline = time.monotonic() + BUDGET_SECONDS
    with _session() as session:
        css = _fetch(session, google_css, deadline)
        if css is None:
            return {}  # Chromium will ask for the CSS and the worker reports today's font error
        fonts, total = {google_css: css}, len(css[0])
        for url in candidates(css[0].decode('utf-8', 'replace'), document):
            if len(fonts) >= worker.MAX_FONT_FILES:
                break
            fetched = _fetch(session, url, deadline)
            if fetched is not None and total + len(fetched[0]) <= worker.MAX_FONTS_BYTES:
                fonts[url] = fetched
                total += len(fetched[0])
    return fonts


def complete(fonts, google_css, requested):
    """Exactly what Chromium asked for when it asked for a file that was not sent; otherwise None."""
    missing = [url for url in requested if url not in fonts]
    if not missing or google_css not in fonts or len(requested) > worker.MAX_FONT_FILES:
        return None
    deadline = time.monotonic() + BUDGET_SECONDS
    retry, total = {google_css: fonts[google_css]}, len(fonts[google_css][0])
    with _session() as session:
        for url in requested:
            if url in retry or not worker.is_font_request(url, ''):
                continue
            fetched = fonts.get(url) or _fetch(session, url, deadline)
            if fetched is not None and total + len(fetched[0]) <= worker.MAX_FONTS_BYTES:
                retry[url] = fetched
                total += len(fetched[0])
    return retry
