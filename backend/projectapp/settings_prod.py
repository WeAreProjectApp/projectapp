"""
Production settings for projectapp.

Overrides: DEBUG=False, MySQL database, SMTP email, security hardening.
Usage: DJANGO_SETTINGS_MODULE=projectapp.settings_prod
"""

from decouple import config as _config

from .settings import *  # noqa: F401, F403

# ==============================================================================
# CORE — production overrides
# ==============================================================================

DEBUG = False  # Hardcoded, never from environment
RECAPTCHA_ENABLED = True  # Deployed logins cannot bypass CAPTCHA, even with missing keys.
FAKE_DATA_ALLOWED = False  # Hard stop for destructive demo-data commands.

# Frontend prerender regeneration — explicit prod values (the base-settings
# defaults derive from DEBUG at import time, before the hardcoded override above).
FRONTEND_REBUILD_ENABLED = _config('FRONTEND_REBUILD_ENABLED', default=True, cast=bool)
# Hardcoded, never from environment: the Huey worker runs sandboxed with the
# project tree read-only, so an in-process build can only fail (EROFS). Content
# changes write backend/logs/frontend-rebuild-request.json and the ops toolkit
# regenerates the build.
FRONTEND_REBUILD_MODE = 'request'
PRERENDER_API_ORIGIN = _config('PRERENDER_API_ORIGIN', default='https://projectapp.co')

# Required in production
if not _config('DJANGO_SECRET_KEY', default=''):
    raise ValueError("DJANGO_SECRET_KEY is required in production")
if not _config('DJANGO_ALLOWED_HOSTS', default=''):
    raise ValueError("DJANGO_ALLOWED_HOSTS is required in production")

# ==============================================================================
# SECURITY
# ==============================================================================

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ==============================================================================
# DATABASE — MySQL
# ==============================================================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': _config('DB_NAME'),
        'USER': _config('DB_USER'),
        'PASSWORD': _config('DB_PASSWORD'),
        'HOST': _config('DB_HOST', default='localhost'),
        'PORT': _config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

# ==============================================================================
# LOGGING — production overrides
# ==============================================================================

LOGGING['handlers']['backup_file']['level'] = 'WARNING'  # noqa: F405
LOGGING['loggers']['django']['level'] = 'WARNING'  # noqa: F405
