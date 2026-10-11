"""Browser checks on a synthetic origin, run by an isolated worker.

This side reads the candidate, downloads its Google Fonts, sends everything to
the worker (linktree_sandbox/worker.py) through the configured transport and
trusts nothing that comes back until contract.py has checked it. Only then are
the captures stored and the report assembled exactly as before.
"""
import base64
import json

from django.conf import settings
from django.core.files.base import ContentFile

from content.storage import get_private_storage
from linktree_sandbox import worker
from . import fonts as google_fonts
from .contract import ValidatorError, decode_response
from .render import asset_url, content_security_policy, font_url, snapshot_document
from .transport import exchange

WIDTHS = worker.WIDTHS
DISABLED_ISSUE = {'severity': 'error', 'code': 'validator_disabled',
                  'message': 'La validación visual está desactivada temporalmente. Consulta al administrador.'}
PAGE_WEIGHT_LIMIT = 1.5 * 1024 * 1024
PAGE_WEIGHT_ISSUE = {'severity': 'warning', 'code': 'page_weight', 'message': 'La página supera 1,5 MB.'}


def _b64(raw):
    return base64.b64encode(raw).decode('ascii')


def _resources(version):
    storage = get_private_storage()
    resources = {}
    for key, asset in version.assets.items():
        for density, path in asset['paths'].items():
            with storage.open(path, 'rb') as stream:
                resources[asset_url(version, key, int(density))] = {'mime': asset['mime'], 'b64': _b64(stream.read())}
    return resources


def _exchange(version, document, google_css, resources, fonts):
    payload = json.dumps({
        'v': worker.PROTOCOL, 'document': document, 'csp': content_security_policy(), 'widths': list(WIDTHS),
        'resources': resources,
        'fonts': {url: {'mime': mime, 'b64': _b64(raw)} for url, (raw, mime) in fonts.items()},
        'google_css': google_css, 'motion_declared': bool(version.template.manifest['motion']),
        'pwa_enabled': bool(version.profile.get('pwa_enabled')),
    }, ensure_ascii=False, separators=(',', ':')).encode()
    if len(payload) > worker.MAX_REQUEST_BYTES:
        raise ValidatorError('request_too_large')
    return decode_response(exchange(payload), document_bytes=len(document.encode()), google_css=google_css,
                           font_sizes={url: len(raw) for url, (raw, _) in fonts.items()})


def validate_in_browser(version):
    if not settings.LINKTREE_BROWSER_VALIDATION:
        # Emergency switch: the candidate fails closed without starting Chromium.
        return {'issues': [dict(DISABLED_ISSUE)]}, {}
    document = snapshot_document(version)
    google_css = font_url(version.template.manifest['fonts'])
    resources = _resources(version)
    fonts = google_fonts.prefetch(google_css, document)
    result = _exchange(version, document, google_css, resources, fonts)
    retry = google_fonts.complete(fonts, google_css, result['fonts_requested'])
    if retry is not None:
        # Chromium asked for a font file that was not sent: run once more with exactly its requests.
        result = _exchange(version, document, google_css, resources, retry)
    page_bytes = result['page_bytes'] + sum(asset['size'] for asset in version.assets.values())
    notices = list(version.template.warnings) + result['issues']
    if page_bytes > PAGE_WEIGHT_LIMIT:
        notices.append(dict(PAGE_WEIGHT_ISSUE))
    # Deduplicate repeated text issues, preserving the measured viewport.
    unique = {str(sorted(item.items())): item for item in notices}
    storage = get_private_storage()
    screenshots = {width: storage.save(f'linktree-templates/screenshots/{version.id}/{width}.png', ContentFile(raw))
                   for width, raw in result['screenshots'].items()}
    return {'issues': list(unique.values())[:worker.MAX_ISSUES], 'page_bytes': page_bytes,
            'widths': list(WIDTHS)}, screenshots
