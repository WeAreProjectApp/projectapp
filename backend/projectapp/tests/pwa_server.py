"""Loopback-only build-test server, isolated from .env, databases and production.

Called by playwright.pwa.config.js. No migrations or fixture writes are needed:
browser specs mock authenticated APIs and use the real anonymous Django login.
"""
import argparse
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3197)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend))
    if '.wt' not in backend.parts and not os.environ.get('CI'):
        raise SystemExit('PWA tests require a session worktree or CI checkout')
    # settings_test reads only process environment. Explicitly isolate the
    # server even when the caller normally runs production management commands.
    for key in ('DJANGO_ENV', 'DJANGO_SETTINGS_MODULE', 'REDIS_URL', 'CACHE_REDIS_URL'):
        os.environ.pop(key, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'projectapp.settings_test'
    from django.core.wsgi import get_wsgi_application
    from django.conf import settings
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.db import connections
    from django.http import HttpResponse
    from django.test import override_settings

    if any(conn.settings_dict['ENGINE'] != 'django.db.backends.sqlite3' for conn in connections.all()):
        raise SystemExit('PWA build tests require SQLite')

    def test_application(environ, start_response):
        # A readiness probe that does not boot Nuxt or contact the database.
        if environ.get('PATH_INFO') == '/__pwa_ready__':
            response = HttpResponse('ready')
            start_response('200 OK', list(response.items()))
            return [response.content]
        return application(environ, start_response)

    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass  # Playwright records failures; avoid a line for every Nuxt chunk.

    with override_settings(
        ALLOWED_HOSTS=['127.0.0.1', 'localhost'],
        DEBUG=True,
        STATIC_URL='/static/',
        STATICFILES_DIRS=[settings.BASE_DIR / 'static'],
        # Public login bootstrap writes an anonymous browser binding. Keep this
        # build-only server database-free without replacing the real auth view.
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
    ):
        application = get_wsgi_application()
        with make_server(
            '127.0.0.1', args.port, StaticFilesHandler(test_application),
            server_class=ThreadedServer, handler_class=QuietHandler,
        ) as server:
            server.serve_forever()


if __name__ == '__main__':
    main()
