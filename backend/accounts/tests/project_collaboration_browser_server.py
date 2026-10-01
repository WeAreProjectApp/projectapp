"""Serve real P4 APIs locally with SQLite and disposable storage, never .env."""
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def main():
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
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from django.http import HttpResponse, JsonResponse
    from django.test import override_settings
    from django.test.utils import setup_databases, teardown_databases
    from projectapp.tests.isolation import collect_storage_locations, settings_refusals, storage_refusals
    from accounts.tests.project_collaboration_browser_fixtures import create_browser_fixture
    reasons = settings_refusals(settings, os.environ) + storage_refusals(
        settings.TEST_FILE_ROOT, settings.BASE_DIR, collect_storage_locations())
    if reasons:
        raise SystemExit('\n'.join(reasons))

    class Server(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class Quiet(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass

    with override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'], DEBUG=True,
                           CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:3213'], RECAPTCHA_ENABLED=False,
                           PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                           EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                           MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()}):
        database = setup_databases(verbosity=0, interactive=False)
        try:
            application = get_wsgi_application()
            fixtures = {}

            def test_application(environ, start_response):
                path = environ.get('PATH_INFO')
                if path == '/__p4_ready__':
                    response = HttpResponse('ready')
                elif path == '/__p4_fixture__' and environ.get('REQUEST_METHOD') == 'POST':
                    size = min(int(environ.get('CONTENT_LENGTH') or 0), 4096)
                    payload = json.loads(environ['wsgi.input'].read(size) or '{}')
                    key = payload['key']
                    if key not in fixtures:
                        fixtures[key] = create_browser_fixture(key, payload.get('grants', []))
                    response = JsonResponse(fixtures[key])
                else:
                    return application(environ, start_response)
                start_response(f'{response.status_code} OK', list(response.items()))
                return [response.content]

            with make_server('127.0.0.1', 3212, test_application, server_class=Server, handler_class=Quiet) as server:
                server.serve_forever()
        finally:
            teardown_databases(database, verbosity=0)


if __name__ == '__main__':
    main()
