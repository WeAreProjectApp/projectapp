import os

from django.conf import settings
from django.http import HttpResponseNotFound, JsonResponse
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from content.admin import admin_site
from django.conf.urls.static import static

from .views import serve_nuxt
from .pwa import serve_pwa_file
from content.views.blog import serve_sitemap_xml
from content.views.qr_cards import qr_card_redirect
from content.views.linktree import linktree_short_redirect
from content.views.linktree_template import localized_linktree


def health_check(request):
    # 'project'/'environment' let external probes verify WHO answered: a shared
    # codebase means the project name alone cannot tell prod from staging
    # (measured: /qa pilot #3). DJANGO_ENV is read through settings because
    # python-decouple resolves it from backend/.env, which os.getenv cannot see.
    return JsonResponse({
        "status": "ok",
        "project": "projectapp",
        "environment": getattr(settings, "DJANGO_ENV", os.getenv("DJANGO_ENV", "development")),
    })


def oauth_discovery_not_found(request, *args, **kwargs):
    """
    MCP clients (claude.ai custom connectors) probe these OAuth discovery
    endpoints; the SPA catch-all used to answer 200 HTML, which reads as
    "OAuth-protected server" and derails the connector setup. A real 404
    signals a no-auth (capability URL) server.
    """
    return HttpResponseNotFound()


urlpatterns = [
    re_path(r'^(?P<locale>en-us|es-co)/lk/(?P<handle>@?[a-zA-Z0-9_.-]+)/?$', localized_linktree, name='localized-linktree'),
    path('manifest.webmanifest', serve_pwa_file, {'filename': 'manifest.webmanifest'}, name='pwa-manifest'),
    path('sw.js', serve_pwa_file, {'filename': 'sw.js'}, name='pwa-worker'),
    path('api/monitoring/', include('monitoring.urls')),
    path('api/secure-links/', include('secure_links.urls')),
    path('api/health/', health_check, name='health-check'),
    # /admin without the trailing slash would fall through to the SPA
    # catch-all and 404 — APPEND_SLASH never kicks in because the URL
    # technically resolves. Redirect it explicitly.
    path('admin', RedirectView.as_view(url='/admin/', permanent=False)),
    path('admin/', admin_site.urls),
    path('api/', include('content.urls')),
    path('api/accounts/', include('accounts.urls')),
    path('sitemap.xml', serve_sitemap_xml, name='sitemap-xml'),
    path('t/<uuid:card_id>/', qr_card_redirect, name='qr-card-redirect'),
    # Clean shareable linktree URL without locale prefix: /lk/@handle
    re_path(
        r'^lk/(?P<handle>@?[a-zA-Z0-9_.-]+)/?$',
        linktree_short_redirect,
        name='linktree-short-redirect',
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if getattr(settings, 'ENABLE_SILK', False):
    urlpatterns += [path('silk/', include('silk.urls', namespace='silk'))]

# OAuth/OpenID discovery probes must 404 (no-auth MCP server), not fall
# through to the SPA catch-all which answers 200 HTML.
urlpatterns += [
    re_path(
        r'^\.well-known/(oauth-authorization-server|oauth-protected-resource|openid-configuration)(/.*)?$',
        oauth_discovery_not_found,
        name='oauth-discovery-not-found',
    ),
]

# Catch-all: serve pre-rendered Nuxt pages and public assets.
# This must be LAST so admin, api, and media URLs take priority.
urlpatterns += [
    re_path(r'^(?P<path>.*)$', serve_nuxt, name='nuxt-page'),
]
