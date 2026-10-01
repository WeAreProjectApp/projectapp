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
from unittest.mock import patch
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def assert_memory_mailers():
    """Refuse any configured or resolved transport outside process memory."""
    from django.conf import settings
    from django.core.mail import mailers
    from django.core.mail.backends.locmem import EmailBackend

    memory_backend = 'django.core.mail.backends.locmem.EmailBackend'
    # Django 6 makes EMAIL_BACKEND unavailable when MAILERS is explicit.
    config = settings.MAILERS
    if config.get('default', {}).get('BACKEND') != memory_backend or any(
        entry.get('BACKEND') != memory_backend for entry in config.values()
    ) or any(type(mailers[alias]) is not EmailBackend for alias in config):
        raise SystemExit('Delivery browser tests require memory-only mailers')


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
    from accounts.models_delivery_email import DeliveryEvidenceEmail
    from django.core import mail

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
        MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}},
        RECAPTCHA_ENABLED=False,
        # Browser tests exercise the runtime model schema. Dedicated migration
        # tests separately verify the historical purge and preservation rules.
        MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()},
    ):
        assert_memory_mailers()
        databases = setup_databases(verbosity=0, interactive=False)
        try:
            application = get_wsgi_application()
            fixtures = {}
            smtp_failures = set()

            def request_data(environ):
                size = int(environ.get('CONTENT_LENGTH') or 0)
                return json.loads(environ['wsgi.input'].read(min(size, 4096)) or '{}')

            def evidence_probe(key):
                fixture = fixtures.get(key)
                if fixture is None:
                    return JsonResponse({'error': 'Fixture not found'}, status=404)
                emails = []
                for email in DeliveryEvidenceEmail.objects.filter(project_id=fixture['project']['id']):
                    attempts = list(email.attempts.order_by('created_at', 'id'))
                    latest = attempts[-1] if attempts else None
                    emails.append({
                        'id': str(email.pk), 'status': latest.status if latest else 'prepared',
                        'attempt_count': len(attempts), 'subject': email.subject,
                        'to': email.to_recipients,
                        'error_message': latest.error_message if latest else '',
                        'resend_of_id': str(email.resend_of_id) if email.resend_of_id else None,
                    })
                outbox = [
                    message for message in getattr(mail, 'outbox', [])
                    if message.subject.startswith(fixture['project']['name'] + ':')
                    and message.to == [fixture['client']['email']]
                ]
                return JsonResponse({'outbox_count': len(outbox), 'emails': emails})

            def test_application(environ, start_response):
                path = environ.get('PATH_INFO')
                if path == '/__delivery_ready__':
                    response = HttpResponse('ready')
                elif path == '/__delivery_fixture__' and environ.get('REQUEST_METHOD') == 'POST':
                    payload = request_data(environ)
                    key = payload.get('key', 'fixture')
                    if key not in fixtures:
                        fixtures[key] = create_browser_fixture(key, mode=payload.get('mode'))
                        if payload.get('mode') == 'closure-smtp-failure':
                            smtp_failures.add(fixtures[key]['project']['id'])
                    response = JsonResponse(fixtures[key])
                elif path == '/__delivery_fixture_probe__':
                    payload = request_data(environ) if environ.get('REQUEST_METHOD') == 'POST' else {
                        'key': parse_qs(environ.get('QUERY_STRING', '')).get('key', [''])[0],
                    }
                    response = evidence_probe(payload.get('key'))
                else:
                    project_prefix = '/api/accounts/projects/'
                    if path.startswith(project_prefix) and path.endswith('/send/') and environ.get('REQUEST_METHOD') == 'POST':
                        project_id = path[len(project_prefix):].split('/', 1)[0]
                        if project_id.isdigit() and int(project_id) in smtp_failures:
                            smtp_failures.remove(int(project_id))
                            with patch('django.core.mail.message.EmailMessage.send', side_effect=RuntimeError('SMTP de prueba no disponible')):
                                return application(environ, start_response)
                    return application(environ, start_response)
                start_response(f'{response.status_code} {response.reason_phrase}', list(response.items()))
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
