"""Browser checks on a synthetic origin; only known assets and Google Fonts load."""
import io
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from playwright.sync_api import sync_playwright

from content.storage import get_private_storage
from .fixed_overlays import fixed_overlay_issues
from .render import asset_url, content_security_policy, font_url, snapshot_document

logger = logging.getLogger(__name__)
WIDTHS = (320, 375, 430)
DISABLED_ISSUE = {'severity': 'error', 'code': 'validator_disabled',
                  'message': 'La validación visual está desactivada temporalmente. Consulta al administrador.'}
DEFAULT_PATH = '/usr/local/bin:/usr/bin:/bin'


def launch_options(home):
    """Chromium sees a throwaway HOME and nothing else from this process; V8 runs without JIT."""
    options = {
        'headless': True, 'timeout': 15000, 'args': ['--js-flags=--jitless'],
        'env': {'HOME': home, 'PATH': os.environ.get('PATH', DEFAULT_PATH),
                'LANG': os.environ.get('LANG', 'C.UTF-8')},
    }
    if settings.LINKTREE_CHROMIUM_EXECUTABLE:
        options['executable_path'] = settings.LINKTREE_CHROMIUM_EXECUTABLE
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


def validate_in_browser(version):
    if not settings.LINKTREE_BROWSER_VALIDATION:
        # Emergency switch: the candidate fails closed without starting Chromium.
        return {'issues': [dict(DISABLED_ISSUE)]}, {}
    storage = get_private_storage()
    document = snapshot_document(version)
    resources = {}
    for key, asset in version.assets.items():
        for density, path in asset['paths'].items():
            with storage.open(path, 'rb') as stream:
                resources[asset_url(version, key, int(density))] = (stream.read(), asset['mime'])
    page_bytes = len(document.encode()) + sum(asset['size'] for asset in version.assets.values())
    google_css = font_url(version.template.manifest['fonts'])
    failures = set()
    notices = list(version.template.warnings)
    screenshots = {}
    font_cache = {}
    source = (Path(__file__).parent / 'audit.js').read_text()
    with tempfile.TemporaryDirectory(prefix='linktree-chromium-') as home, sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options(home))
        try:
            context = browser.new_context(service_workers='block', device_scale_factor=1, reduced_motion='no-preference')
            context.set_default_timeout(8000)
            def route_request(route):
                nonlocal page_bytes
                request_url = route.request.url
                url = urlsplit(request_url)
                if request_url == 'https://template.invalid/':
                    return route.fulfill(body=document, content_type='text/html', headers={'Content-Security-Policy': content_security_policy()})
                if url.netloc == 'template.invalid' and url.path in resources:
                    raw, mime = resources[url.path]
                    return route.fulfill(body=raw, content_type=mime)
                if request_url == google_css or (url.scheme == 'https' and url.netloc == 'fonts.gstatic.com' and url.path.startswith('/s/')):
                    if request_url in font_cache:
                        raw, mime = font_cache[request_url]
                    else:
                        try:
                            if len(font_cache) >= 40:
                                raise ValueError('Too many font files')
                            response = route.fetch(timeout=5000, max_redirects=0)
                            raw = response.body(); mime = response.headers.get('content-type', '')
                            if response.status != 200 or len(raw) > 2 * 1024 * 1024:
                                raise ValueError('Font unavailable')
                            font_cache[request_url] = (raw, mime); page_bytes += len(raw)
                        except Exception:
                            failures.add('No se pudieron cargar las fuentes de Google; vuelve a validar.')
                            return route.abort()
                    return route.fulfill(body=raw, content_type=mime, headers={'Access-Control-Allow-Origin': '*'})
                failures.add('La plantilla intentó cargar un recurso no autorizado.')
                return route.abort()
            context.route('**/*', route_request)
            for width in WIDTHS:
                page = context.new_page()
                page.set_viewport_size({'width': width, 'height': 900})
                page.goto('https://template.invalid/', wait_until='load', timeout=20000)
                page.evaluate('() => document.fonts.ready')
                page.evaluate('() => Promise.all([...document.images].map(i => i.decode().catch(() => null)))')
                if version.profile.get('pwa_enabled'):
                    page.locator('[data-action="install-pwa"]').evaluate_all('(elements) => elements.forEach(el => { el.hidden = false; })')
                notices.extend({**entry, 'width': width} for entry in fixed_overlay_issues(page))
                audit = page.evaluate(source)
                notices.extend({**entry, 'width': width} for entry in audit['issues'])
                if audit['animated'] and not version.template.manifest['motion']:
                    notices.append({'severity': 'error', 'code': 'motion_undeclared', 'message': 'Declara motion: true para utilizar animaciones.', 'width': width})
                if page.locator('body').evaluate('(el) => el.scrollHeight') <= 12000:
                    raw = page.screenshot(full_page=True, animations='disabled', timeout=8000)
                    screenshots[str(width)] = storage.save(f'linktree-templates/screenshots/{version.id}/{width}.png', ContentFile(raw))
                    page.add_style_tag(content='*{text-decoration-color:transparent!important}[data-contrast-glyph]{color:transparent!important;-webkit-text-fill-color:transparent!important;text-shadow:none!important}')
                    background = page.screenshot(full_page=True, animations='disabled', timeout=8000)
                    notices.extend(contrast_issues(audit['texts'], background, width))
                page.emulate_media(reduced_motion='reduce')
                if page.evaluate('() => document.getAnimations().some(a => a.playState === "running")'):
                    notices.append({'severity': 'error', 'code': 'reduced_motion', 'message': 'La preferencia de movimiento reducido no detiene todas las animaciones.', 'width': width})
                page.close()
            context.close()
        finally:
            browser.close()
    notices.extend({'severity': 'error', 'code': 'resource_load', 'message': message} for message in sorted(failures))
    if page_bytes > 1.5 * 1024 * 1024:
        notices.append({'severity': 'warning', 'code': 'page_weight', 'message': 'La página supera 1,5 MB.'})
    # Deduplicate repeated text issues, preserving the measured viewport.
    unique = {str(sorted(item.items())): item for item in notices}
    return {'issues': list(unique.values())[:150], 'page_bytes': page_bytes, 'widths': list(WIDTHS)}, screenshots
