"""
Django base settings for projectapp.

This file contains shared configuration for all environments.
Do NOT use this file directly — import it via settings_dev.py or settings_prod.py.

Environment-specific overrides:
  - settings_dev.py  : SQLite, DEBUG=True, console email
  - settings_prod.py : MySQL, DEBUG=False, SMTP email
"""

import os
from pathlib import Path

from decouple import Csv, config
from huey import RedisHuey

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


DJANGO_ENV = config('DJANGO_ENV', default='development')
IS_PRODUCTION = DJANGO_ENV == 'production'

# Positive capability checked by every fake/demo management command.  It is
# enabled only by settings_dev; production cannot opt in through environment
# naming or DEBUG alone.
FAKE_DATA_ALLOWED = False


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('DJANGO_SECRET_KEY', default='change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'content',
    'accounts',
    'monitoring',
    'secure_links',
    'corsheaders',
    # Third-party (operations)
    'dbbackup',
    'huey.contrib.djhuey',
]

ENABLE_SILK = config('ENABLE_SILK', default=False, cast=bool)
if ENABLE_SILK:
    INSTALLED_APPS.append('silk')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'content.services.entity_history.EntityHistoryMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if ENABLE_SILK:
    MIDDLEWARE.insert(1, 'silk.middleware.SilkyMiddleware')

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = config(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    default='http://127.0.0.1:5173,http://localhost:5173',
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    default='http://127.0.0.1:5173,http://localhost:5173',
    cast=Csv(),
)

ROOT_URLCONF = 'projectapp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'content' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'projectapp.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': config('DJANGO_DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DJANGO_DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
PRIVATE_MEDIA_ROOT = config(
    'PRIVATE_MEDIA_ROOT',
    default=str(BASE_DIR / 'private_media'),
)

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    # Signed contracts must never inherit MEDIA_URL. They are streamed only by
    # authenticated views after an explicit permission check.
    'private': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {
            'location': PRIVATE_MEDIA_ROOT,
            'base_url': None,
        },
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
    'dbbackup': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {
            'location': config('BACKUP_STORAGE_PATH', default='/var/backups/projectapp'),
        },
    },
}

# ==============================================================================
# FRONTEND BASE URL — used for building public proposal links in emails
# ==============================================================================

FRONTEND_BASE_URL = config('FRONTEND_BASE_URL', default='http://localhost:3000')

# Default locale segment for building locale-prefixed frontend URLs from the
# backend (i18n strategy is "prefix", so the segment is always required).
FRONTEND_DEFAULT_LOCALE = config('FRONTEND_DEFAULT_LOCALE', default='en-us')

# Frontend prerender rebuild (blog SEO). The static build bakes blog posts
# into HTML, so publishing content triggers a rebuild (content/tasks.py).
# Disabled by default in dev so local publishes don't spawn npm builds.
FRONTEND_REBUILD_ENABLED = config('FRONTEND_REBUILD_ENABLED', default=not DEBUG, cast=bool)
FRONTEND_BUILD_COMMAND = config('FRONTEND_BUILD_COMMAND', default='npm run build:django')
# API origin the build fetches slugs/content from. In production gunicorn
# listens on a unix socket, so the public domain is the reachable origin.
PRERENDER_API_ORIGIN = config('PRERENDER_API_ORIGIN', default='http://127.0.0.1:8000')

# When True, accepting a proposal without a linked deliverable creates a platform client
# (if missing) + project + deliverable from proposal.client_email / client_name.
AUTO_PROVISION_CLIENT_FROM_PROPOSAL = config(
    'AUTO_PROVISION_CLIENT_FROM_PROPOSAL', default=False, cast=bool,
)

# ==============================================================================
# EMAIL — override in settings_dev.py
# ==============================================================================

_default_mailer_backend = config(
    'DJANGO_EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
_default_mailer_options = {}
if _default_mailer_backend == 'django.core.mail.backends.smtp.EmailBackend':
    _default_mailer_options = {
        'host': config('EMAIL_HOST', default='smtpout.secureserver.net'),
        'port': config('EMAIL_PORT', default=465, cast=int),
        'use_ssl': config('EMAIL_USE_SSL', default=True, cast=bool),
        'username': config('EMAIL_HOST_USER', default=''),
        'password': config('EMAIL_HOST_PASSWORD', default=''),
    }

MAILERS = {
    'default': {
        'BACKEND': _default_mailer_backend,
        'OPTIONS': _default_mailer_options,
    },
}
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='team@projectapp.co')
NOTIFICATION_EMAIL = config('NOTIFICATION_EMAIL', default='dev.gustavo.perezp@gmail.com')
# Hosting payment outcomes (approved / failed) go to the accounting module's
# administrable recipient list (content.NotificationRecipient), not to a fixed
# inbox — see accounts/services/payment_notifications.py.

# Firmantes disponibles para los correos al cliente. La key se almacena en
# BusinessProposal.email_signed_by; el template resuelve nombre + rol desde aquí.
EMAIL_SIGNATURES = {
    'gustavo': {'name': 'Gustavo Pérez', 'role': 'CEO · ProjectApp.'},
    'carlos':  {'name': 'Carlos Blanco', 'role': 'CTO · ProjectApp.'},
    'vanessa': {'name': 'Vanessa Rodríguez', 'role': 'Asistente Comercial · ProjectApp.'},
}
EMAIL_DEFAULT_SIGNER = 'vanessa'

# ==============================================================================
# WHATSAPP — CallMeBot API
# ==============================================================================

WHATSAPP_PHONE = config('WHATSAPP_PHONE', default='')
CALLMEBOT_API_KEY = config('CALLMEBOT_API_KEY', default='')

# ==============================================================================
# WOMPI — Payment Gateway
# ==============================================================================

WOMPI_PUBLIC_KEY = config('WOMPI_PUBLIC_KEY', default='')
WOMPI_PRIVATE_KEY = config('WOMPI_PRIVATE_KEY', default='')
WOMPI_EVENTS_SECRET = config('WOMPI_EVENTS_SECRET', default='')
WOMPI_INTEGRITY_SECRET = config('WOMPI_INTEGRITY_SECRET', default='')
WOMPI_API_URL = config('WOMPI_API_URL', default='https://sandbox.wompi.co/v1')

# ==============================================================================
# reCAPTCHA v2
# ==============================================================================

RECAPTCHA_SECRET_KEY = config('RECAPTCHA_SECRET_KEY', default='')
RECAPTCHA_SITE_KEY = config('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_ALLOWED_HOSTNAMES = config('RECAPTCHA_ALLOWED_HOSTNAMES', default='', cast=Csv())
RECAPTCHA_ENABLED = config('RECAPTCHA_ENABLED', default=True, cast=bool)

# ==============================================================================
# LINKEDIN — OAuth 2.0 (blog post sharing)
# ==============================================================================

LINKEDIN_CLIENT_ID = config('LINKEDIN_CLIENT_ID', default='')
LINKEDIN_CLIENT_SECRET = config('LINKEDIN_CLIENT_SECRET', default='')
LINKEDIN_REDIRECT_URI = config(
    'LINKEDIN_REDIRECT_URI',
    default='https://projectapp.co/auth/linkedin/callback',
)
LINKEDIN_ENCRYPTION_KEY = config('LINKEDIN_ENCRYPTION_KEY', default='')

# ==============================================================================
# CACHE — Redis (db 1; Huey uses db 5)
# ==============================================================================

_CACHE_REDIS_URL = config('CACHE_REDIS_URL', default='')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': _CACHE_REDIS_URL,
    } if _CACHE_REDIS_URL else {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
}

# ==============================================================================
# HUEY — task queue
# ==============================================================================

HUEY = RedisHuey(
    name='projectapp',
    url=config('REDIS_URL', default='redis://localhost:6379/5'),
    immediate=not IS_PRODUCTION,
)

# ==============================================================================
# BACKUPS — django-dbbackup
# ==============================================================================
# Storage is configured via STORAGES['dbbackup'] above (new-style API).

DBBACKUP_FILENAME_TEMPLATE = '{datetime}.sql'
DBBACKUP_MEDIA_FILENAME_TEMPLATE = '{datetime}.tar'
DBBACKUP_CLEANUP_KEEP = 4

# Backups: permite desactivar la tarea programada en staging via .env
BACKUPS_ENABLED = config('BACKUPS_ENABLED', default=True, cast=bool)
# Slow queries report: solo tiene sentido con tráfico real (desactivar en staging)
ENABLE_SLOW_QUERIES_REPORT = config('ENABLE_SLOW_QUERIES_REPORT', default=True, cast=bool)
DBBACKUP_CLEANUP_KEEP_MEDIA = 4

# ==============================================================================
# SILK — query profiling (enabled via ENABLE_SILK env flag)
# ==============================================================================

if ENABLE_SILK:
    from .monitoring_export import should_profile

    SILKY_PYTHON_PROFILER = False
    SILKY_PYTHON_PROFILER_BINARY = False
    SILKY_META = False
    SILKY_ANALYZE_QUERIES = False
    MONITORING_SILK_SAMPLE_PERCENT = max(0, min(100, config('MONITORING_SILK_SAMPLE_PERCENT', default=5, cast=int)))
    SILKY_INTERCEPT_FUNC = should_profile

    SILKY_AUTHENTICATION = True
    SILKY_AUTHORISATION = True

    def silk_permissions(user):
        return user.is_staff

    SILKY_PERMISSIONS = silk_permissions

    SILKY_MAX_RECORDED_REQUESTS = 1000
    SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10

    SILKY_IGNORE_PATHS = [
        '/admin/',
        '/static/',
        '/media/',
        '/silk/',
    ]

    SILKY_MAX_REQUEST_BODY_SIZE = 0
    SILKY_MAX_RESPONSE_BODY_SIZE = 0
    SILKY_SENSITIVE_KEYS = {'username', 'api', 'token', 'key', 'secret', 'password', 'signature', 'cookie', 'authorization'}

# ==============================================================================
# DRF + JWT
# ==============================================================================

from datetime import timedelta  # noqa: E402

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'mcp': '60/min',
    },
}

# Origins allowed to call the MCP endpoints (besides our own host).
# claude.ai's MCP client sends Origin: https://claude.ai on its requests.
MCP_ALLOWED_ORIGINS = [
    'https://claude.ai',
]

# Superuser that MCP writes are attributed to (accounting created_by, task
# comment author). The endpoint authenticates by token, not by user, so tools
# that need an actor resolve one here. Empty ⇒ first active superuser.
# See content/mcp/actor.py.
MCP_ACTOR_USERNAME = os.environ.get('MCP_ACTOR_USERNAME', '')

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

SLOW_QUERY_THRESHOLD_MS = config('SLOW_QUERY_THRESHOLD_MS', default=500, cast=int)
N_PLUS_ONE_THRESHOLD = config('N_PLUS_ONE_THRESHOLD', default=10, cast=int)

# ==============================================================================
# LOGGING
# ==============================================================================

LOG_LEVEL = config('DJANGO_LOG_LEVEL', default='INFO')

_LOGS_DIR = BASE_DIR / 'logs'
_LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'backup_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'backups.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'blog_publish_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'blog_publish.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'mcp_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'mcp.log',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': True,
        },
        'backups': {
            'handlers': ['backup_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'content.views.blog': {
            'handlers': ['blog_publish_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # Publish pipeline logic moved here from content.views.blog — keep
        # its [LinkedIn]/scheduling logs flowing into blog_publish.log.
        'content.services.blog_service': {
            'handlers': ['blog_publish_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # MCP endpoint + tool execution audit trail (all 8 connectors).
        # Package-level logger: covers content.mcp.protocol and every
        # content.mcp.*_tools module without listing them one by one.
        'content.views.mcp_blog': {
            'handlers': ['mcp_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'content.mcp': {
            'handlers': ['mcp_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'content.services.linkedin_service': {
            'handlers': ['blog_publish_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'content.tasks': {
            'handlers': ['blog_publish_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
