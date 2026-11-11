"""Loopback browser-test server with a temporary database and fake Google HTTP.

Never imported by runtime settings or URLs. Real Django forms, views, CSRF,
sessions and JWT issuance run here; only the external provider is replaced.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from socketserver import ThreadingMixIn
from unittest.mock import patch
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=3198)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[2]
    if '.wt' not in backend.parts and not os.environ.get('CI'):
        raise SystemExit('CAPTCHA browser tests require a session worktree or CI')
    sys.path.insert(0, str(backend))
    for key in ('DJANGO_ENV', 'DJANGO_SETTINGS_MODULE', 'REDIS_URL', 'CACHE_REDIS_URL'):
        os.environ.pop(key, None)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'projectapp.settings_test'

    import django
    django.setup()
    import requests
    from django.apps import apps
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.core.wsgi import get_wsgi_application
    from django.db import transaction
    from django.http import HttpResponse
    from django.test import override_settings
    from django.test.utils import setup_databases, teardown_databases
    from accounts.models import UserProfile
    from projectapp.tests.isolation import collect_storage_locations, settings_refusals, storage_refusals

    reasons = settings_refusals(settings, os.environ) + storage_refusals(
        settings.TEST_FILE_ROOT, settings.BASE_DIR, collect_storage_locations(),
    )
    if reasons:
        raise SystemExit('\n'.join(reasons))

    consumed = set()

    def google_verify(url, *, data, timeout):
        if url != 'https://www.google.com/recaptcha/api/siteverify':
            raise AssertionError('Unexpected outbound request in CAPTCHA tests')
        token = data['response']
        if token.startswith('unavailable-'):
            raise requests.Timeout('Simulated Google outage')
        valid = token.startswith('valid-') and token not in consumed
        consumed.add(token)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps({'success': valid, 'hostname': '127.0.0.1'}).encode()
        return response

    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, format, *args):
            pass

    with override_settings(
        ALLOWED_HOSTS=['localhost', '127.0.0.1'], DEBUG=True,
        CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:3199'],
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RECAPTCHA_ENABLED=True, RECAPTCHA_SITE_KEY='browser-test-site-key',
        RECAPTCHA_SECRET_KEY='browser-test-secret', RECAPTCHA_ALLOWED_HOSTNAMES=['127.0.0.1'],
        # Browser tests exercise the current runtime schema. Migration history
        # is covered separately and makes this isolated fixture too slow to start.
        MIGRATION_MODULES={config.label: None for config in apps.get_app_configs()},
    ):
        databases = setup_databases(verbosity=0, interactive=False)
        try:
            with transaction.atomic():
                user = get_user_model().objects.create_user(
                    username='browser-captcha@example.com', email='browser-captcha@example.com',
                    password='Browser-test-password-1', is_staff=True,
                )
                UserProfile.objects.create(
                    user=user, role=UserProfile.ROLE_CLIENT, is_onboarded=True, profile_completed=True,
                )
            application = get_wsgi_application()

            def test_application(environ, start_response):
                if environ.get('PATH_INFO') == '/__captcha_ready__':
                    response = HttpResponse('ready')
                    start_response('200 OK', list(response.items()))
                    return [response.content]
                return application(environ, start_response)

            with patch('projectapp.recaptcha.requests.post', side_effect=google_verify):
                with make_server(
                    '127.0.0.1', args.port, StaticFilesHandler(test_application),
                    server_class=ThreadedServer, handler_class=QuietHandler,
                ) as server:
                    server.serve_forever()
        finally:
            teardown_databases(databases, verbosity=0)


if __name__ == '__main__':
    main()
