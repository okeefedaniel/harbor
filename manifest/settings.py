"""
Manifest — Standalone Document Signing Platform
Django settings for standalone deployment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
DEMO_MODE = os.environ.get('DEMO_MODE', 'False').lower() in ('true', '1', 'yes')
DEMO_ROLES = ['admin', 'signer']

import secrets as _secrets

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = _secrets.token_hex(25)
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set in production')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Railway provides RAILWAY_PUBLIC_DOMAIN automatically
RAILWAY_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')
if RAILWAY_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    ALLOWED_HOSTS.append('.railway.app')

# CSRF trusted origins (required for POST forms behind HTTPS proxy)
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
if RAILWAY_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_DOMAIN}')
CSRF_TRUSTED_ORIGINS = [o for o in CSRF_TRUSTED_ORIGINS if o]  # filter blanks

MANIFEST_SITE_URL = os.environ.get('SITE_URL', 'https://manifest.docklabs.ai')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Keel (DockLabs shared platform)
    'keel.core',
    'keel.security',
    'keel.notifications',
    # Third-party
    'crispy_forms',
    'crispy_bootstrap5',
    # Manifest
    'signatures.apps.SignaturesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'keel.security.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'keel.core.middleware.AuditMiddleware',
    'keel.security.middleware.FailedLoginMonitor',
]

ROOT_URLCONF = 'manifest.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'signatures.context_processors.manifest_context',
                'keel.core.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'manifest.wsgi.application'

# Database — uses DATABASE_URL (provided automatically by Railway Postgres)
import dj_database_url

_db_url = os.environ.get('DATABASE_URL', '').strip().lstrip('= ')
if not _db_url:
    # Railway sometimes stores variable names with trailing whitespace;
    # fall back to scanning env vars if the exact key isn't found.
    for _key, _val in os.environ.items():
        if _key.strip() == 'DATABASE_URL' and _val.strip():
            _db_url = _val.strip().lstrip('= ')
            break
if _db_url and '://' in _db_url:
    # Use parse() with the value we already read, NOT config() which
    # re-reads from os.environ and can get a stale/empty value.
    DATABASES = {
        'default': dj_database_url.parse(_db_url, conn_max_age=600)
    }
else:
    if _db_url:
        import warnings
        warnings.warn(
            f'DATABASE_URL is set but looks invalid (no scheme): '
            f'{_db_url[:20]}...',
            stacklevel=1,
        )
    import warnings
    warnings.warn(
        'DATABASE_URL not found — using SQLite fallback. '
        'Set DATABASE_URL for production use.',
        stacklevel=1,
    )
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_manifest.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles_manifest'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@manifest.docklabs.ai')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'signatures': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Security Settings
# ---------------------------------------------------------------------------

SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

if not DEBUG:
    # HTTPS / SSL settings (Railway handles SSL at the proxy)
    SECURE_SSL_REDIRECT = False
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HTTP Strict Transport Security
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Content Security
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

# Use separate migrations directory for standalone mode
# (avoids the grants app dependency in the default migration)
MIGRATION_MODULES = {
    'signatures': 'manifest.migrations.signatures',
}

# ---------------------------------------------------------------------------
# Keel (DockLabs Shared Platform)
# ---------------------------------------------------------------------------
KEEL_PRODUCT_NAME = 'Manifest'
KEEL_AUDIT_LOG_MODEL = 'signatures.AuditLog'
KEEL_NOTIFICATION_MODEL = 'signatures.Notification'
KEEL_NOTIFICATION_PREFERENCE_MODEL = 'signatures.NotificationPreference'
KEEL_CSP_POLICY = {}  # Start permissive, tighten later
