"""Settings for the pytest suite (backend/pytest.ini).

pytest has to see the same configuration wherever it runs (CI, a laptop, a
session worktree), and none of it may reach production:

* decouple reads only the process environment, never backend/.env. Session
  worktrees symlink the deployed .env (DJANGO_ENV=production and the
  production Redis URLs); read through decouple, it took Huey out of immediate
  mode and put the test cache on the production Redis.
* Every file storage writes under a per-run temp directory. It is set here,
  before django.setup(), because some storages are bound at import time: a
  FileField evaluates a callable storage once, and django-dbbackup copies
  STORAGES['dbbackup'] when it is imported.

backend/conftest.py refuses to start a session that breaks either guarantee.
"""

import atexit
import shutil
import tempfile
from pathlib import Path

import decouple

# Has to run before the base module executes `from decouple import config`.
decouple.config = decouple.Config(decouple.RepositoryEmpty())

from .settings import *  # noqa: E402, F401, F403

RECAPTCHA_ENABLED = False  # Individual CAPTCHA tests explicitly enable it.

# Bind the effective Django 6 transport before setup and model/task imports.
# EMAIL_BACKEND alone cannot replace an explicitly configured MAILERS backend.
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}

TEST_FILE_ROOT = Path(tempfile.mkdtemp(prefix='projectapp-pytest-'))
atexit.register(shutil.rmtree, TEST_FILE_ROOT, ignore_errors=True)

# The SQLite test database lives in memory. Django still opens the configured
# NAME around its setup, which used to leave an empty backend/db.sqlite3.
DATABASES = {
    'default': {**DATABASES['default'], 'NAME': str(TEST_FILE_ROOT / 'db.sqlite3')},  # noqa: F405
}

MEDIA_ROOT = str(TEST_FILE_ROOT / 'media')
PRIVATE_MEDIA_ROOT = str(TEST_FILE_ROOT / 'private_media')
STORAGES = {
    **STORAGES,  # noqa: F405
    'private': {
        **STORAGES['private'],  # noqa: F405
        'OPTIONS': {**STORAGES['private']['OPTIONS'], 'location': PRIVATE_MEDIA_ROOT},  # noqa: F405
    },
    'dbbackup': {
        **STORAGES['dbbackup'],  # noqa: F405
        'OPTIONS': {'location': str(TEST_FILE_ROOT / 'dbbackup')},
    },
}
