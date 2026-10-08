"""Tests for the serve_nuxt catch-all view.

Verifies that SPA routes like /panel are served correctly via the
200.html fallback, and that missing fallback files produce actionable
log warnings instead of silent 404s.
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from django.test import RequestFactory, override_settings

from projectapp.views import serve_nuxt


@pytest.fixture
def frontend_dir(tmp_path):
    """Create a temporary frontend directory with a 200.html fallback."""
    spa_html = tmp_path / '200.html'
    spa_html.write_text('<html><body>SPA Shell</body></html>')
    return str(tmp_path)


@pytest.fixture
def frontend_dir_with_prerendered(frontend_dir):
    """Frontend dir that also has a pre-rendered /en-us/index.html."""
    locale_dir = os.path.join(frontend_dir, 'en-us')
    os.makedirs(locale_dir, exist_ok=True)
    with open(os.path.join(locale_dir, 'index.html'), 'w') as f:
        f.write('<html><body>EN-US Home</body></html>')
    return frontend_dir


@pytest.fixture
def frontend_dir_no_fallback(tmp_path):
    """Frontend directory without any fallback HTML files."""
    return str(tmp_path)


@pytest.fixture
def rf():
    """Django RequestFactory."""
    return RequestFactory()


class TestServeNuxtPanelRoute:
    """Tests that /panel SPA routes resolve correctly."""

    def test_panel_route_serves_spa_fallback(self, rf, frontend_dir, settings):
        settings.BASE_DIR = os.path.dirname(frontend_dir)
        # Patch FRONTEND_DIR at module level
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/panel')
            response = serve_nuxt(request, path='panel')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert 'SPA Shell' in content
            assert response['Cache-Control'] == 'no-cache'
        finally:
            views_mod.FRONTEND_DIR = original

    def test_panel_subpath_serves_spa_fallback(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/panel/proposals')
            response = serve_nuxt(request, path='panel/proposals')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert 'SPA Shell' in content
        finally:
            views_mod.FRONTEND_DIR = original

    def test_panel_nested_subpath_serves_spa_fallback(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/panel/proposals/42/edit')
            response = serve_nuxt(request, path='panel/proposals/42/edit')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert 'SPA Shell' in content
        finally:
            views_mod.FRONTEND_DIR = original


class TestServeNuxtPrerenderedRoutes:
    """Tests that pre-rendered pages are served directly."""

    def test_prerendered_route_serves_index_html(self, rf, frontend_dir_with_prerendered):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir_with_prerendered
        try:
            request = rf.get('/en-us/')
            response = serve_nuxt(request, path='en-us')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert 'EN-US Home' in content
        finally:
            views_mod.FRONTEND_DIR = original

    def test_exact_file_match_serves_asset(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        asset_path = os.path.join(frontend_dir, 'logo.txt')
        with open(asset_path, 'w') as f:
            f.write('plain asset')
        try:
            request = rf.get('/logo.txt')
            response = serve_nuxt(request, path='logo.txt')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert content == 'plain asset'
        finally:
            views_mod.FRONTEND_DIR = original

    def test_root_index_is_last_resort_when_fallback_missing(self, rf, frontend_dir_no_fallback):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir_no_fallback
        with open(os.path.join(frontend_dir_no_fallback, 'index.html'), 'w') as f:
            f.write('<html><body>Root Index</body></html>')
        try:
            request = rf.get('/marketing/path')
            response = serve_nuxt(request, path='marketing/path')
            content = b''.join(response.streaming_content).decode()
            assert response.status_code == 200
            assert 'Root Index' in content
            assert response['Cache-Control'] == 'no-cache'
        finally:
            views_mod.FRONTEND_DIR = original


class TestServeNuxtMissingFallback:
    """Tests behavior when 200.html is missing."""

    def test_panel_route_returns_404_when_fallback_missing(self, rf, frontend_dir_no_fallback):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir_no_fallback
        try:
            request = rf.get('/panel')
            with pytest.raises(Exception) as exc_info:
                serve_nuxt(request, path='panel')
            assert '404' in str(type(exc_info.value).__name__) or 'Http404' in str(type(exc_info.value))
        finally:
            views_mod.FRONTEND_DIR = original

    def test_panel_route_logs_warning_when_fallback_missing(self, rf, frontend_dir_no_fallback, caplog):
        import logging
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir_no_fallback
        try:
            request = rf.get('/panel')
            with caplog.at_level(logging.WARNING, logger='projectapp.views'):
                with pytest.raises(Exception):
                    serve_nuxt(request, path='panel')
            assert 'SPA fallback missing' in caplog.text
            assert '200.html' in caplog.text
        finally:
            views_mod.FRONTEND_DIR = original

    def test_unknown_route_no_warning_when_fallback_missing(self, rf, frontend_dir_no_fallback, caplog):
        """Non-SPA routes should not produce the SPA-specific warning."""
        import logging
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir_no_fallback
        try:
            request = rf.get('/some-random-path')
            with caplog.at_level(logging.WARNING, logger='projectapp.views'):
                with pytest.raises(Exception):
                    serve_nuxt(request, path='some-random-path')
            assert 'SPA fallback missing' not in caplog.text
        finally:
            views_mod.FRONTEND_DIR = original


class TestServeNuxtLegacyBlogRedirect:
    """Unprefixed /blog URLs 301 to the es-co canonical (i18n strategy 'prefix')."""

    def test_blog_post_redirects_permanently_to_es_co(self, rf):
        request = rf.get('/blog/my-post-slug')
        response = serve_nuxt(request, path='blog/my-post-slug')
        assert response.status_code == 301
        assert response['Location'] == '/es-co/blog/my-post-slug'

    def test_blog_index_redirects_permanently_to_es_co(self, rf):
        request = rf.get('/blog')
        response = serve_nuxt(request, path='blog')
        assert response.status_code == 301
        assert response['Location'] == '/es-co/blog'

    def test_prefixed_blog_path_is_not_redirected(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/es-co/blog/my-post-slug')
            response = serve_nuxt(request, path='es-co/blog/my-post-slug')
            assert response.status_code == 200  # SPA fallback, not a redirect
        finally:
            views_mod.FRONTEND_DIR = original

    def test_blog_prefix_of_longer_word_is_not_redirected(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/blogging-tips')
            response = serve_nuxt(request, path='blogging-tips')
            assert response.status_code == 200  # falls through to SPA fallback
        finally:
            views_mod.FRONTEND_DIR = original


class TestServeNuxtRenamedFinancingRedirect:
    """/financing became /partnership-program (Programa de Alianza): old links 301."""

    @pytest.mark.parametrize(('path', 'location'), [
        ('es-co/financing', '/es-co/partnership-program'),
        ('en-us/financing/', '/en-us/partnership-program'),
        ('es-co/financing/_payload.json', '/es-co/partnership-program/_payload.json'),
        ('financing', '/es-co/partnership-program'),
    ])
    def test_legacy_financing_path_redirects_permanently(self, rf, path, location):
        response = serve_nuxt(rf.get(f'/{path}'), path=path)

        assert response.status_code == 301
        assert response['Location'] == location

    def test_redirect_keeps_the_query_string(self, rf):
        request = rf.get('/es-co/financing', {'utm_source': 'whatsapp'})

        response = serve_nuxt(request, path='es-co/financing')

        assert response['Location'] == '/es-co/partnership-program?utm_source=whatsapp'

    def test_stale_prerendered_financing_page_still_redirects(
        self, rf, frontend_dir, monkeypatch,
    ):
        """Fails if a leftover build file answers the old URL instead of the 301."""
        import projectapp.views as views_mod
        stale_dir = Path(frontend_dir, 'es-co', 'financing')
        stale_dir.mkdir(parents=True)
        (stale_dir / 'index.html').write_text('<html><body>Módulo de financiación</body></html>')
        monkeypatch.setattr(views_mod, 'FRONTEND_DIR', frontend_dir)

        response = serve_nuxt(rf.get('/es-co/financing'), path='es-co/financing')

        assert response.status_code == 301

    @pytest.mark.parametrize('path', [
        'es-co/panel/financing-guide',
        'panel/financing-guide',
        'es-co/financing-guide',
    ])
    def test_similar_paths_are_not_redirected(self, rf, frontend_dir, monkeypatch, path):
        import projectapp.views as views_mod
        monkeypatch.setattr(views_mod, 'FRONTEND_DIR', frontend_dir)

        response = serve_nuxt(rf.get(f'/{path}'), path=path)

        assert response.status_code == 200  # SPA fallback, not a redirect


class TestServeNuxtWaiterShortAliases:
    """Short Spanish URLs of the Waiter legal pages 301 to their es-co route."""

    @pytest.mark.parametrize(('path', 'location'), [
        ('privacidad', '/es-co/waiter/privacy'),
        ('terminos/', '/es-co/waiter/terms'),
        ('eliminacion-de-datos', '/es-co/waiter/data-deletion'),
        ('contacto', '/es-co/contact'),
        ('waiter', '/es-co/waiter'),
        ('waiter/privacy', '/es-co/waiter/privacy'),
    ])
    def test_short_alias_redirects_permanently(self, rf, path, location):
        response = serve_nuxt(rf.get(f'/{path}'), path=path)

        assert response.status_code == 301
        assert response['Location'] == location

    def test_alias_redirect_keeps_the_query_string(self, rf):
        request = rf.get('/privacidad', {'utm_source': 'meta'})

        response = serve_nuxt(request, path='privacidad')

        assert response['Location'] == '/es-co/waiter/privacy?utm_source=meta'

    @pytest.mark.parametrize('path', [
        'es-co/waiter/privacy',
        'en-us/waiter',
        'privacidad-extra',
        'waiters',
    ])
    def test_prefixed_or_similar_paths_are_not_redirected(
        self, rf, frontend_dir, monkeypatch, path,
    ):
        import projectapp.views as views_mod
        monkeypatch.setattr(views_mod, 'FRONTEND_DIR', frontend_dir)

        response = serve_nuxt(rf.get(f'/{path}'), path=path)

        assert response.status_code == 200  # SPA fallback, not a redirect


class TestServeNuxtRootRedirect:
    """Tests root path redirect behavior."""

    def test_root_redirects_to_default_locale(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/')
            response = serve_nuxt(request, path='')
            assert response.status_code == 302
            assert response['Location'] == '/en-us/'
        finally:
            views_mod.FRONTEND_DIR = original

    def test_root_redirects_to_es_co_for_spanish_country(self, rf):
        request = rf.get('/', HTTP_X_COUNTRY='CO')
        response = serve_nuxt(request, path='')
        assert response.status_code == 302
        assert response['Location'] == '/es-co/'

    def test_root_redirects_to_en_us_for_non_spanish_country(self, rf):
        request = rf.get('/', HTTP_X_COUNTRY='US')
        response = serve_nuxt(request, path='')
        assert response.status_code == 302
        assert response['Location'] == '/en-us/'

    def test_root_redirect_is_not_cached(self, rf):
        request = rf.get('/', HTTP_X_COUNTRY='CO')
        response = serve_nuxt(request, path='')
        assert response['Cache-Control'] == 'no-store'

    def test_preferred_locale_cookie_overrides_country(self, rf):
        request = rf.get('/', HTTP_X_COUNTRY='CO')
        request.COOKIES['preferred_locale'] = 'en-us'
        response = serve_nuxt(request, path='')
        assert response.status_code == 302
        assert response['Location'] == '/en-us/'

    def test_invalid_cookie_falls_back_to_country(self, rf):
        request = rf.get('/', HTTP_X_COUNTRY='CO')
        request.COOKIES['preferred_locale'] = 'fr-fr'
        response = serve_nuxt(request, path='')
        assert response.status_code == 302
        assert response['Location'] == '/es-co/'


class TestServeNuxtPathSecurity:
    def test_path_traversal_raises_404(self, rf, frontend_dir):
        import projectapp.views as views_mod
        original = views_mod.FRONTEND_DIR
        views_mod.FRONTEND_DIR = frontend_dir
        try:
            request = rf.get('/../../etc/passwd')
            with pytest.raises(Exception) as exc_info:
                serve_nuxt(request, path='../../etc/passwd')
            assert 'Http404' in str(type(exc_info.value))
        finally:
            views_mod.FRONTEND_DIR = original
