"""Loopback ticket browser fixture server, confined to settings_test storage/SQLite."""
import argparse
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from threading import Lock
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

MEMORY_MAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def memory_mailers(settings):
    """Replace every configured alias; never retain SMTP options or credentials."""
    aliases = {'default', *getattr(settings, 'MAILERS', {})}
    return {alias: {'BACKEND': MEMORY_MAIL_BACKEND} for alias in aliases}


def assert_memory_mailers():
    """Fail closed before database setup or fixture code can send anything."""
    from django.conf import settings
    from django.core import mail
    from django.core.mail.backends.locmem import EmailBackend
    aliases = getattr(settings, 'MAILERS', {})
    if not isinstance(aliases, dict) or 'default' not in aliases or any(
        not isinstance(config, dict) or config.get('BACKEND') != MEMORY_MAIL_BACKEND or config.get('OPTIONS')
        for config in aliases.values()
    ):
        raise SystemExit('Issue browser fixtures require memory-only MAILERS for every alias.')
    if any(type(mail.mailers[alias]) is not EmailBackend for alias in aliases):
        raise SystemExit('The effective issue browser mail backend must be locmem.')


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

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass

    with override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
                           CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:4213'],
                           MAILERS=memory_mailers(settings),
                           RECAPTCHA_ENABLED=False,
                           MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()}):
        assert_memory_mailers()
        print('Issue browser mail sink: all aliases use locmem.', flush=True)
        databases = setup_databases(verbosity=0, interactive=False)
        try:
            from accounts.models import DeliveryPublication, Project
            from accounts.tests.delivery_browser_fixtures import create_browser_fixture
            from django.contrib.auth import get_user_model
            application = get_wsgi_application()
            application_lock = Lock()
            fixtures = {}

            def test_application(environ, start_response):
                with application_lock:
                    path = environ.get('PATH_INFO')
                    if path == '/__issues_ready__':
                        response = HttpResponse('ready')
                    elif path == '/__issues_mailbox__':
                        from django.core import mail
                        assert_memory_mailers()
                        response = JsonResponse({'backend': 'locmem', 'aliases': sorted(settings.MAILERS),
                                                 'count': len(getattr(mail, 'outbox', []))})
                    elif path == '/__issues_fixture__' and environ.get('REQUEST_METHOD') == 'POST':
                        assert_memory_mailers()
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

            # Shared in-memory SQLite cannot wait on concurrent table locks.
            # Serialize this disposable harness; production locks remain in
            # the domain services, not in this fixture-only server.
            with make_server('127.0.0.1', args.port, test_application,
                             server_class=ThreadedWSGIServer, handler_class=QuietHandler) as server:
                server.serve_forever()
        finally:
            teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()
