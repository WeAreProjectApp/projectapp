"""Explicit disposable fake-data configuration; never reads backend/.env.

FAKE_DATA_ROOT is mandatory. Prepare its private key files first using the
recipe in docs/FAKE_DATA_COVERAGE.md. This module creates neither keys nor data.
"""
import os
from pathlib import Path

import decouple
from django.core.exceptions import ImproperlyConfigured

if os.environ.get('DJANGO_ENV') == 'production':
    raise ImproperlyConfigured('Fake-data settings refuse DJANGO_ENV=production.')

_root = os.environ.get('FAKE_DATA_ROOT', '')
if not _root or not Path(_root).is_absolute():
    raise ImproperlyConfigured('FAKE_DATA_ROOT must be an explicit absolute disposable directory.')
FAKE_DATA_ROOT = Path(_root).resolve()
if FAKE_DATA_ROOT.is_relative_to(Path(__file__).resolve().parents[2]):
    raise ImproperlyConfigured('FAKE_DATA_ROOT must be outside the source checkout.')

decouple.config = decouple.Config(decouple.RepositoryEmpty())

from .settings import *  # noqa: E402,F401,F403

DJANGO_ENV = 'development'
IS_PRODUCTION = False
FAKE_DATA_ALLOWED = True
DEBUG = True
SECRET_KEY = (FAKE_DATA_ROOT / 'private/django-key').read_text().strip()
os.environ.pop('PROJECT_ACCESS_CIPHER_KEY', None)
os.environ['PROJECT_ACCESS_CIPHER_KEY_FILE'] = str(FAKE_DATA_ROOT / 'private/access-key')

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(FAKE_DATA_ROOT / 'db.sqlite3')}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
from huey import MemoryHuey  # noqa: E402
HUEY = MemoryHuey(name='fake-data-isolated', immediate=True)
MEDIA_ROOT = str(FAKE_DATA_ROOT / 'media')
PRIVATE_MEDIA_ROOT = str(FAKE_DATA_ROOT / 'private-media')
STATIC_ROOT = str(FAKE_DATA_ROOT / 'static')
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage', 'OPTIONS': {'location': MEDIA_ROOT}},
    'private': {'BACKEND': 'django.core.files.storage.FileSystemStorage',
                'OPTIONS': {'location': PRIVATE_MEDIA_ROOT, 'base_url': None}},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    'dbbackup': {'BACKEND': 'django.core.files.storage.FileSystemStorage',
                 'OPTIONS': {'location': str(FAKE_DATA_ROOT / 'backups')}},
}
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.filebased.EmailBackend',
                        'OPTIONS': {'file_path': str(FAKE_DATA_ROOT / 'mail')}}}
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
FRONTEND_BASE_URL = 'http://localhost'
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
WOMPI_PUBLIC_KEY = ''
WOMPI_PRIVATE_KEY = ''
WOMPI_EVENTS_SECRET = ''
WOMPI_INTEGRITY_SECRET = ''
WOMPI_API_URL = 'http://127.0.0.1:9/unavailable-in-fake-data'
CALLMEBOT_API_KEY = ''
