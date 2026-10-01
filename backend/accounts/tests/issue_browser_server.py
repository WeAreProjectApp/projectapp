"""Loopback ticket browser fixture server, confined to settings_test storage/SQLite."""
import argparse
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4212)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[2]
    if '.wt' not in backend.parts and not os.environ.get('CI'):
        raise SystemExit('Browser tests require a session worktree or CI.')
    sys.path.insert(0, str(backend))
    for key in ('DJANGO_ENV', 'DJANGO_SETTINGS_MODULE', 'REDIS_URL', 'CACHE_REDIS_URL'):
        os.environ.pop(key, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'projectapp.settings_test'
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    from django.http import HttpResponse, JsonResponse
    from django.test import override_settings
    from django.test.utils import setup_databases, teardown_databases
    from projectapp.tests.isolation import collect_storage_locations, settings_refusals, storage_refusals
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

    with override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
                           CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:4213'],
                           EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                           RECAPTCHA_ENABLED=False,
                           MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()}):
        databases = setup_databases(verbosity=0, interactive=False)
        try:
            from accounts.models import DeliveryPublication, Project
            from accounts.tests.delivery_browser_fixtures import create_browser_fixture
            from django.contrib.auth import get_user_model
            application = get_wsgi_application()
            fixtures = {}

            def test_application(environ, start_response):
                path = environ.get('PATH_INFO')
                if path == '/__issues_ready__':
                    response = HttpResponse('ready')
                elif path == '/__issues_fixture__' and environ.get('REQUEST_METHOD') == 'POST':
                    size = min(int(environ.get('CONTENT_LENGTH') or 0), 4096)
                    key = json.loads(environ['wsgi.input'].read(size) or '{}').get('key', 'issues')
                    if key not in fixtures:
                        data = create_browser_fixture(key)
                        client = get_user_model().objects.get(email=data['client']['email'])
                        general = Project.objects.create(name=f'General {key}', client=client)
                        data['general_project'] = {'id': general.pk, 'name': general.name}
                        data['publication_id'] = DeliveryPublication.objects.get(stage_id=data['stage_id']).pk
                        fixtures[key] = data
                    response = JsonResponse(fixtures[key])
                else:
                    return application(environ, start_response)
                start_response(f'{response.status_code} OK', list(response.items()))
                return [response.content]

            with make_server('127.0.0.1', args.port, test_application,
                             server_class=ThreadedServer, handler_class=QuietHandler) as server:
                server.serve_forever()
        finally:
            teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()
