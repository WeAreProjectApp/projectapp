"""Serve real P4 APIs locally with SQLite and disposable storage, never .env."""

import argparse
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

LOCMEM_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


def certify_mail_isolation():
    """Refuse unsafe aliases before constructing backends or creating fixtures."""
    from django.conf import settings
    from django.core.mail import mailers
    from django.core.mail.backends.locmem import EmailBackend

    configured = getattr(settings, 'MAILERS', None)
    if not isinstance(configured, dict) or 'default' not in configured:
        raise SystemExit('P4 isolation requires MAILERS with a default alias')
    for config in configured.values():
        if not isinstance(config, dict) or config.get('BACKEND') != LOCMEM_BACKEND:
            raise SystemExit(
                'P4 isolation requires an explicit locmem backend '
                'for every MAILERS alias'
            )
    try:
        if set(mailers) != set(configured):
            raise SystemExit('P4 isolation requires matching effective MAILERS aliases')
        connections = {alias: mailers[alias] for alias in configured}
        connections['default'] = mailers.default
    except Exception:
        raise SystemExit(
            'P4 isolation could not certify the effective mailers'
        ) from None
    if any(type(connection) is not EmailBackend for connection in connections.values()):
        raise SystemExit(
            'P4 isolation requires the effective locmem backend for every alias'
        )
    return {alias: LOCMEM_BACKEND for alias in connections}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--check-isolation',
        action='store_true',
        help='Certify isolation without preparing a database, fixtures or HTTP server',
    )
    args = parser.parse_args(argv)
    backend = Path(__file__).resolve().parents[2]
    if '.wt' not in backend.parts and not os.environ.get('CI'):
        raise SystemExit('P4 browser validation requires a session worktree or CI')
    sys.path.insert(0, str(backend))
    for key in ('DJANGO_ENV', 'DJANGO_SETTINGS_MODULE', 'REDIS_URL', 'CACHE_REDIS_URL'):
        os.environ.pop(key, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'projectapp.settings_test'
    from cryptography.fernet import Fernet

    os.environ['PROJECT_ACCESS_CIPHER_KEY'] = Fernet.generate_key().decode('ascii')
    import django
    from django.conf import settings
    from django.test import override_settings

    if settings.SETTINGS_MODULE != 'projectapp.settings_test':
        raise SystemExit('P4 isolation requires projectapp.settings_test')

    with override_settings(
        SETTINGS_MODULE='projectapp.settings_test',
        ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
        DEBUG=True,
        CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:3213'],
        RECAPTCHA_ENABLED=False,
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        MAILERS={'default': {'BACKEND': LOCMEM_BACKEND}},
    ):
        # Protect app initialization as well as database setup and fixture imports.
        certify_mail_isolation()
        django.setup()
        from django.apps import apps
        from django.core.wsgi import get_wsgi_application
        from django.http import HttpResponse, JsonResponse
        from django.test.utils import setup_databases, teardown_databases
        from projectapp.tests.isolation import (
            collect_storage_locations,
            settings_refusals,
            storage_refusals,
        )

        reasons = settings_refusals(settings, os.environ) + storage_refusals(
            settings.TEST_FILE_ROOT, settings.BASE_DIR, collect_storage_locations()
        )
        if reasons:
            raise SystemExit('\n'.join(reasons))
        certificate = certify_mail_isolation()
        if args.check_isolation:
            print(
                json.dumps(
                    {
                        'settings_module': settings.SETTINGS_MODULE,
                        'database_engine': settings.DATABASES['default']['ENGINE'],
                        'mailers': certificate,
                    }
                )
            )
            return

        from accounts.tests.project_collaboration_browser_fixtures import (
            create_browser_fixture,
        )

        class Server(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        class Quiet(WSGIRequestHandler):
            def log_message(self, format, *args):
                pass

        with override_settings(
            MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()}
        ):
            certify_mail_isolation()
            database = setup_databases(verbosity=0, interactive=False)
            try:
                application = get_wsgi_application()
                fixtures = {}

                def test_application(environ, start_response):
                    path = environ.get('PATH_INFO')
                    if path == '/__p4_ready__':
                        response = HttpResponse('ready')
                    elif (
                        path == '/__p4_fixture__'
                        and environ.get('REQUEST_METHOD') == 'POST'
                    ):
                        certify_mail_isolation()
                        size = min(int(environ.get('CONTENT_LENGTH') or 0), 4096)
                        payload = json.loads(environ['wsgi.input'].read(size) or '{}')
                        key = payload['key']
                        if key not in fixtures:
                            fixtures[key] = create_browser_fixture(
                                key, payload.get('grants', [])
                            )
                        response = JsonResponse(fixtures[key])
                    else:
                        return application(environ, start_response)
                    start_response(f'{response.status_code} OK', list(response.items()))
                    return [response.content]

                with make_server(
                    '127.0.0.1',
                    3212,
                    test_application,
                    server_class=Server,
                    handler_class=Quiet,
                ) as server:
                    server.serve_forever()
            finally:
                teardown_databases(database, verbosity=0)


if __name__ == '__main__':
    main()
