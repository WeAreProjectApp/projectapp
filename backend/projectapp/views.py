import logging
import mimetypes
import os

from django.conf import settings
from django.http import (
    FileResponse, Http404, HttpResponseRedirect, HttpResponsePermanentRedirect,
)

logger = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(settings.BASE_DIR, 'static', 'frontend')
DEFAULT_LOCALE = 'en-us'

# Known SPA route prefixes that should always resolve to the SPA fallback
# instead of returning 404 when no pre-rendered file exists.
SPA_ROUTE_PREFIXES = ('panel', 'proposal')

VALID_LOCALES = ('en-us', 'es-co')

# Public pages renamed after they were shared and indexed: old slug → new slug.
# /financing became /partnership-program when the module was renamed
# "Programa de Alianza" (2026-09); the explainer video still shows the old URL.
RENAMED_PUBLIC_SLUGS = {'financing': 'partnership-program'}

# Short Spanish aliases for the Waiter product and legal pages listed in the
# Meta app review: unprefixed only, landing on es-co because Spanish is the
# official text. `waiter/...` keeps its sub-path; the rest match exactly.
SHORT_PUBLIC_ALIASES = {
    'privacidad': 'es-co/waiter/privacy',
    'terminos': 'es-co/waiter/terms',
    'eliminacion-de-datos': 'es-co/waiter/data-deletion',
    'contacto': 'es-co/contact',
}

# Códigos ISO-3166 alpha-2 de países hispanohablantes → locale es-co.
SPANISH_COUNTRIES = frozenset({
    'CO', 'MX', 'AR', 'PE', 'CL', 'EC', 'VE', 'BO', 'PY', 'UY',
    'CR', 'PA', 'DO', 'GT', 'HN', 'NI', 'SV', 'CU', 'PR', 'ES', 'GQ',
})


def _resolve_locale(request):
    """Elige el locale para el redirect de la raíz.

    Prioriza la elección manual guardada en la cookie `preferred_locale`; si no
    hay, decide por el país del visitante (header `X-Country` que nginx inyecta
    desde geoip2). País hispanohablante → es-co; cualquier otro → en-us.
    """
    preferred = request.COOKIES.get('preferred_locale')
    if preferred in VALID_LOCALES:
        return preferred
    country = (request.headers.get('X-Country') or '').strip().upper()
    if country in SPANISH_COUNTRIES:
        return 'es-co'
    return DEFAULT_LOCALE


def _renamed_page_redirect(request, clean_path):
    """301 renamed pages, keeping locale, remaining segments and query.

    Public slugs and the exact panel/financing prefix are matched separately.
    Unprefixed paths land on es-co, like the legacy blog redirect.
    """
    segments = clean_path.split('/')
    locale = segments[0] if segments[0] in VALID_LOCALES else None
    rest = segments[1:] if locale else segments
    if rest[:2] == ['panel', 'financing']:
        renamed_path = ['panel', 'partnership-program', *rest[2:]]
    elif rest and rest[0] in RENAMED_PUBLIC_SLUGS:
        renamed_path = [RENAMED_PUBLIC_SLUGS[rest[0]], *rest[1:]]
    else:
        return None
    target = '/'.join([locale or 'es-co', *renamed_path])
    location = f'/{target}'
    query_string = request.META.get('QUERY_STRING', '')
    if query_string:
        location = f'{location}?{query_string}'
    return HttpResponsePermanentRedirect(location)


def _short_alias_redirect(request, clean_path):
    """301 an unprefixed short alias to its es-co page, keeping the query."""
    if clean_path == 'waiter' or clean_path.startswith('waiter/'):
        target = f'es-co/{clean_path}'
    else:
        target = SHORT_PUBLIC_ALIASES.get(clean_path)
    if not target:
        return None
    location = f'/{target}'
    query_string = request.META.get('QUERY_STRING', '')
    if query_string:
        location = f'{location}?{query_string}'
    return HttpResponsePermanentRedirect(location)


def serve_nuxt(request, path=''):
    """
    Serve pre-rendered Nuxt pages and public assets from backend/static/frontend/.
    
    Handles:
    - HTML pages: /en-us/about-us → static/frontend/en-us/about-us/index.html
    - Payload JSON: /en-us/about-us/_payload.json → static/frontend/en-us/about-us/_payload.json
    - Public assets: /img/icons/icon.png → static/frontend/img/icons/icon.png
    - SPA fallback: routes not pre-rendered get 200.html (Nuxt handles client-side)
    """
    clean_path = path.strip('/')

    # Redirect bare root to the locale that fits the visitor (país / cookie).
    if not clean_path:
        response = HttpResponseRedirect(f'/{_resolve_locale(request)}/')
        response['Cache-Control'] = 'no-store'
        return response

    # Legacy unprefixed blog URLs: the i18n router uses strategy 'prefix', so
    # /blog/<slug> was never a real route (old sitemaps and shared links point
    # there). 301 to the es-co variant — posts are Spanish-first content — so
    # crawlers consolidate signals on the canonical URL.
    if clean_path == 'blog' or clean_path.startswith('blog/'):
        return HttpResponsePermanentRedirect(f'/es-co/{clean_path}')

    # Renamed public pages: redirect before the file lookup so a leftover
    # prerendered index.html under the old slug can never answer.
    renamed = _renamed_page_redirect(request, clean_path)
    if renamed:
        return renamed

    alias = _short_alias_redirect(request, clean_path)
    if alias:
        return alias

    # Security: prevent path traversal
    resolved = os.path.realpath(os.path.join(FRONTEND_DIR, clean_path))
    if not resolved.startswith(os.path.realpath(FRONTEND_DIR)):
        raise Http404()

    # 1. Exact file match (e.g. _payload.json, .png, .mp4, .splinecode)
    if os.path.isfile(resolved):
        content_type, _ = mimetypes.guess_type(resolved)
        return FileResponse(open(resolved, 'rb'), content_type=content_type)

    # 2. Directory with index.html (e.g. /en-us/about-us/ → index.html)
    index_file = os.path.join(resolved, 'index.html')
    if os.path.isfile(index_file):
        response = FileResponse(open(index_file, 'rb'), content_type='text/html')
        response['Cache-Control'] = 'no-cache'
        return response

    # 3. SPA fallback for client-side routes not pre-rendered
    fallback = os.path.join(FRONTEND_DIR, '200.html')
    if os.path.isfile(fallback):
        response = FileResponse(open(fallback, 'rb'), content_type='text/html')
        response['Cache-Control'] = 'no-cache'
        return response

    # 4. Root index.html as last resort
    root_index = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.isfile(root_index):
        response = FileResponse(open(root_index, 'rb'), content_type='text/html')
        response['Cache-Control'] = 'no-cache'
        return response

    # Log a warning for known SPA routes that couldn't be served — this
    # indicates 200.html is missing from the Nuxt build output.
    first_segment = clean_path.split('/')[0]
    if first_segment in SPA_ROUTE_PREFIXES:
        logger.warning(
            'SPA fallback missing for route /%s — 200.html not found in %s. '
            'Ensure "nuxt generate" produces 200.html '
            '(nitro.prerender.fallback must be true in nuxt.config.ts).',
            clean_path, FRONTEND_DIR,
        )

    raise Http404('Page not found')
