"""Loopback delivery browser tests with real JWT APIs and a disposable database.

This module is never imported by runtime settings or URLs. Storage and database
isolation are checked before fixtures are written. No deployed .env is loaded.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3202)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[2]
    if '.wt' not in backend.parts and not os.environ.get('CI'):
        raise SystemExit('Delivery browser tests require a session worktree or CI')
    sys.path.insert(0, str(backend))
    for key in ('DJANGO_ENV', 'DJANGO_SETTINGS_MODULE', 'REDIS_URL', 'CACHE_REDIS_URL'):
        os.environ.pop(key, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'projectapp.settings_test'

    import django
    django.setup()
    from django.conf import settings
    from django.apps import apps
    from django.core.wsgi import get_wsgi_application
    from django.http import HttpResponse, JsonResponse
    from django.test import override_settings
    from django.test.utils import setup_databases, teardown_databases
    from projectapp.tests.isolation import collect_storage_locations, settings_refusals, storage_refusals
    from accounts.tests.delivery_browser_fixtures import create_browser_fixture

    reasons = settings_refusals(settings, os.environ) + storage_refusals(
        settings.TEST_FILE_ROOT, settings.BASE_DIR, collect_storage_locations(),
    )
    if reasons:
        raise SystemExit('\n'.join(reasons))

    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass

    with override_settings(
        ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'], DEBUG=True,
        CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:3203'],
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RECAPTCHA_ENABLED=False,
        # Browser tests exercise the runtime model schema. Dedicated migration
        # tests separately verify the historical purge and preservation rules.
        MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()},
    ):
        databases = setup_databases(verbosity=0, interactive=False)
        try:
            application = get_wsgi_application()
            fixtures = {}

            def test_application(environ, start_response):
                path = environ.get('PATH_INFO')
                if path == '/__delivery_ready__':
                    response = HttpResponse('ready')
                elif path == '/__delivery_fixture__' and environ.get('REQUEST_METHOD') == 'POST':
                    size = int(environ.get('CONTENT_LENGTH') or 0)
                    payload = json.loads(environ['wsgi.input'].read(min(size, 4096)) or '{}')
                    key = payload.get('key', 'fixture')
                    if key not in fixtures:
                        fixtures[key] = create_browser_fixture(key)
                    response = JsonResponse(fixtures[key])
                else:
                    return application(environ, start_response)
                start_response(f'{response.status_code} OK', list(response.items()))
                return [response.content]

            with make_server(
                '127.0.0.1', args.port, test_application,
                server_class=ThreadedServer, handler_class=QuietHandler,
            ) as server:
                server.serve_forever()
        finally:
            teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()
