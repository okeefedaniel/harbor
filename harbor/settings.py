"""
Harbor - State Grants Management Solution
Django settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

import secrets as _secrets

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = _secrets.token_hex(25)
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set in production')

# Demo mode — enables quick-login cards on the demo page without full DEBUG.
# Safe to enable in production because it only allows login as existing seed users.
DEMO_MODE = os.environ.get('DEMO_MODE', 'False').lower() in ('true', '1', 'yes')
DEMO_ROLES = ['system_admin', 'agency_admin', 'program_officer', 'fiscal_officer', 'federal_fund_coordinator', 'reviewer', 'applicant', 'auditor']

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
# Auto-add HTTPS origins for every explicit ALLOWED_HOSTS entry
for _host in ALLOWED_HOSTS:
    _origin = f'https://{_host}'
    if _host and not _host.startswith('.') and _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)
CSRF_TRUSTED_ORIGINS = [o for o in CSRF_TRUSTED_ORIGINS if o]  # filter blanks

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',
    # Keel (DockLabs shared platform)
    'keel.accounts',
    'keel.core',
    'keel.security',
    'keel.notifications',
    'keel.requests',
    'keel.signatures',
    'keel.settings',
    'keel.activity',  # Phase 1A Week 5 / Phase 1C — fifth product peer (Harbor)
    'keel.mentions',  # @-mentions on application comments (keel >= 0.42.0)
    'keel.scheduling',  # observability for scheduled mgmt commands (canary `cron_silent_24h`)
    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',  # OpenAPI 3 schema for /api/v1/ (suite convention; ref: beacon)
    'crispy_forms',
    'crispy_bootstrap5',
    'django_filters',
    # Allauth (SSO / MFA)
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.microsoft',
    'allauth.socialaccount.providers.openid_connect',  # Phase 2b: Keel as IdP
    'allauth.mfa',
    # Project apps
    'core.apps.CoreConfig',
    'portal.apps.PortalConfig',
    'grants.apps.GrantsConfig',
    'applications.apps.ApplicationsConfig',
    'reviews.apps.ReviewsConfig',
    'awards.apps.AwardsConfig',
    'financial.apps.FinancialConfig',
    'reporting.apps.ReportingConfig',
    'closeout.apps.CloseoutConfig',
    'signatures.apps.SignaturesConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'keel.security.middleware.SecurityHeadersMiddleware',
    'keel.security.middleware.AdminIPAllowlistMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'keel.accounts.middleware.AutoOIDCLoginMiddleware',
    'keel.accounts.middleware.ProductAccessMiddleware',
    'keel.accounts.middleware.SessionFreshnessMiddleware',
    'core.middleware.HarborProfileMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'keel.security.middleware.FailedLoginMonitor',
    'keel.core.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'harbor.urls'

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
                'core.context_processors.site_context',
                'signatures.context_processors.manifest_context',
                'keel.core.context_processors.fleet_context',
                'keel.core.context_processors.breadcrumb_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'harbor.wsgi.application'

# Database — DATABASE_URL required (SQLite fallback decommissioned keel 0.24.3)
import dj_database_url

_db_url = os.environ.get('DATABASE_URL', '').strip()
if not _db_url:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        'DATABASE_URL is required. '
        'Run: createdb harbor_dev && export DATABASE_URL=postgres://localhost:5432/harbor_dev'
    )
DATABASES = {
    'default': dj_database_url.parse(_db_url, conn_max_age=600)
}

AUTH_USER_MODEL = 'keel_accounts.KeelUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = 'en'
TIME_ZONE = 'America/New_York'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('en', _('English')),
    ('es', _('Spanish')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Mapbox
MAPBOX_ACCESS_TOKEN = os.environ.get('MAPBOX_ACCESS_TOKEN', '')

# Grants.gov API (Simpler Grants.gov — free tier)
GRANTS_GOV_API_KEY = os.environ.get('GRANTS_GOV_API_KEY', '')

# Anthropic Claude API (AI-powered grant matching)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GRANT_MATCH_MIN_SCORE = 60      # Minimum relevance score to store a match
GRANT_MATCH_NOTIFY_SCORE = 75   # Minimum score to trigger a notification

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Crispy forms
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Login/Logout
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Email — Resend HTTP API for transactional emails (Railway blocks outbound SMTP)
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'keel.notifications.backends.resend_backend.ResendEmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'DockLabs <info@docklabs.ai>')
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

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
        'core': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'grants': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'applications': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'awards': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'financial': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'reporting': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Security Settings
# ---------------------------------------------------------------------------

# Session configuration
SESSION_COOKIE_AGE = 60 * 60  # 1 hour — government compliance requirement
SESSION_SAVE_EVERY_REQUEST = True  # Reset session expiry on each request
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

if not DEBUG:
    # HTTPS / SSL settings (Railway provides HTTPS termination)
    SECURE_SSL_REDIRECT = False  # Railway handles SSL at the proxy
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

    # X-Frame-Options is handled by XFrameOptionsMiddleware (default: DENY)
    X_FRAME_OPTIONS = 'DENY'

# Minimum password length (override default of 8)
AUTH_PASSWORD_VALIDATORS[1]['OPTIONS'] = {'min_length': 10}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '120/minute',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# drf-spectacular — OpenAPI 3 schema served at /api/v1/schema/, /api/v1/docs/, /api/v1/redoc/.
# Per CLAUDE.md "Programmatic API" section: schema is the contract integrators
# read against. Beacon is the reference impl.
SPECTACULAR_SETTINGS = {
    'TITLE': 'Harbor API',
    'DESCRIPTION': 'Programmatic API for Harbor (grant programs, applications, awards, drawdowns, closeout).',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Allowed file upload extensions
ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
    '.txt', '.rtf', '.odt', '.ods', '.ppt', '.pptx',
    '.png', '.jpg', '.jpeg', '.gif', '.tiff',
    '.zip', '.gz',
]

# ---------------------------------------------------------------------------
# Django Allauth — Microsoft Entra ID (Azure AD) SSO + MFA
# ---------------------------------------------------------------------------

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # Username-or-email login (matches the shared LoginForm contract).
    'keel.accounts.backends.UsernameOrEmailBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Account settings
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_ADAPTER = 'keel.core.sso.KeelAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'keel.core.sso.KeelSocialAccountAdapter'

# Where to redirect after social login
SOCIALACCOUNT_LOGIN_ON_GET = True  # Skip the intermediate "Continue?" page

# Microsoft Entra ID (Azure AD) provider configuration
# Set these environment variables in Railway / .env:
#   MICROSOFT_CLIENT_ID     — Application (client) ID from Azure portal
#   MICROSOFT_CLIENT_SECRET — Client secret value
#   MICROSOFT_TENANT_ID     — Directory (tenant) ID (use 'common' for multi-tenant)
_MSFT_TENANT = os.environ.get('MICROSOFT_TENANT_ID', 'common')

SOCIALACCOUNT_PROVIDERS = {
    'microsoft': {
        'APP': {
            'client_id': os.environ.get('MICROSOFT_CLIENT_ID', ''),
            'secret': os.environ.get('MICROSOFT_CLIENT_SECRET', ''),
        },
        'SCOPE': [
            'openid',
            'email',
            'profile',
            'User.Read',
        ],
        'AUTH_PARAMS': {
            'prompt': 'select_account',
        },
        'TENANT': _MSFT_TENANT,
    },
}

# ---------------------------------------------------------------------------
# Keel OIDC (Phase 2b) — Keel is the identity provider for the DockLabs suite
# ---------------------------------------------------------------------------
# When KEEL_OIDC_CLIENT_ID is set, this product federates authentication to
# Keel via standard OAuth2/OIDC. When unset, the product falls back to local
# Django auth (+ optional direct Microsoft SSO), so standalone deployments
# continue to work without any Keel dependency.
KEEL_OIDC_CLIENT_ID = os.environ.get('KEEL_OIDC_CLIENT_ID', '')
KEEL_OIDC_CLIENT_SECRET = os.environ.get('KEEL_OIDC_CLIENT_SECRET', '')
KEEL_OIDC_ISSUER = os.environ.get('KEEL_OIDC_ISSUER', 'https://keel.docklabs.ai')

if KEEL_OIDC_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS['openid_connect'] = {
        'APPS': [
            {
                'provider_id': 'keel',
                'name': 'Sign in with DockLabs',
                'client_id': KEEL_OIDC_CLIENT_ID,
                'secret': KEEL_OIDC_CLIENT_SECRET,
                'settings': {
                    'server_url': f'{KEEL_OIDC_ISSUER}/oauth/.well-known/openid-configuration',
                    'token_auth_method': 'client_secret_post',
                    'oauth_pkce_enabled': True,  # Keel requires PKCE
                    'scope': ['openid', 'email', 'profile', 'product_access', 'organization', 'ai'],
                },
            },
        ],
    }

# MFA configuration
MFA_ADAPTER = 'allauth.mfa.adapter.DefaultMFAAdapter'
MFA_SUPPORTED_TYPES = ['totp', 'webauthn', 'recovery_codes']
MFA_TOTP_ISSUER = 'Harbor'
# Require MFA for agency staff (enforced in adapter)
MFA_PASSKEY_LOGIN_ENABLED = True

# ---------------------------------------------------------------------------
# DocuSign e-Signature
# ---------------------------------------------------------------------------
DOCUSIGN_INTEGRATION_KEY = os.environ.get('DOCUSIGN_INTEGRATION_KEY', '')
DOCUSIGN_ACCOUNT_ID = os.environ.get('DOCUSIGN_ACCOUNT_ID', '')
DOCUSIGN_RSA_PRIVATE_KEY = os.environ.get('DOCUSIGN_RSA_PRIVATE_KEY', '')  # Inline PEM key
DOCUSIGN_RSA_KEY_FILE = os.environ.get('DOCUSIGN_RSA_KEY_FILE', 'docusign_private.pem')
DOCUSIGN_BASE_URL = os.environ.get('DOCUSIGN_BASE_URL', 'https://demo.docusign.net/restapi')
DOCUSIGN_OAUTH_BASE = os.environ.get('DOCUSIGN_OAUTH_BASE', 'https://account-d.docusign.com')
DOCUSIGN_USER_ID = os.environ.get('DOCUSIGN_USER_ID', '')  # DocuSign user GUID
DOCUSIGN_HMAC_KEY = os.environ.get('DOCUSIGN_HMAC_KEY', '')  # HMAC-SHA256 secret for Connect webhook

# ---------------------------------------------------------------------------
# Keel (DockLabs Shared Platform)
# ---------------------------------------------------------------------------
KEEL_PRODUCT_NAME = 'Harbor'
KEEL_PRODUCT_CODE = 'harbor'
KEEL_GATE_ACCESS = True
KEEL_PRODUCT_ICON = 'bi-bank2'
KEEL_PRODUCT_SUBTITLE = 'State Grants Management Solution'
from keel.core.fleet import FLEET as KEEL_FLEET_PRODUCTS  # noqa: E402,F401
KEEL_API_URL = os.environ.get('KEEL_API_URL', 'https://keel.docklabs.ai')
KEEL_API_KEY = os.environ.get('KEEL_API_KEY', '')
HELM_FEED_API_KEY = os.environ.get('HELM_FEED_API_KEY', '')
# keel.ops canary bearer-token for external pollers (GH Actions canary.yml
# pings /api/v1/metrics/ every 15min). Leave unset for dev — the staff-
# session auth path on the view still works.
KEEL_METRICS_TOKEN = os.environ.get('HARBOR_METRICS_TOKEN', '')

# Manifest cross-product signing handoff — the keel.signatures scaffolding
# lives alongside harbor's existing bespoke signatures app. Both are
# expected for the near term (see keel/CLAUDE.md "Known Deviations"); the
# per-product services.py dedup is a separate workstream.
MANIFEST_URL = os.environ.get('MANIFEST_URL', '')
MANIFEST_API_TOKEN = os.environ.get('MANIFEST_API_TOKEN', '')
MANIFEST_WEBHOOK_SECRET = os.environ.get('MANIFEST_WEBHOOK_SECRET', '')

# Beacon cross-product intake — consumed by keel.mentions.beacon when an
# application comment contains an `@beacon:<contact-slug>` token.
# Unset values gracefully disable the cross-product call (picker shows
# zero Beacon contacts; no POST to /api/v1/intake/contact-mentions/).
BEACON_INTAKE_URL = os.environ.get('BEACON_INTAKE_URL', '')
BEACON_INTAKE_API_KEY = os.environ.get('BEACON_INTAKE_API_KEY', '')
KEEL_AUDIT_LOG_MODEL = 'harbor_core.AuditLog'
KEEL_NOTIFICATION_MODEL = 'harbor_core.Notification'
KEEL_NOTIFICATION_PREFERENCE_MODEL = 'harbor_core.NotificationPreference'
KEEL_NOTIFICATION_LOG_MODEL = 'harbor_core.NotificationLog'

# keel.activity — Phase 1A Week 5 / Phase 1C
# Concrete Activity + Watcher live in applications/activity_models.py with
# a denormalized `application` FK for fast detail-page reads. Track A
# promotion rules (ApplicationAssignment / ApplicationComment /
# ApplicationAttachment / ApplicationComplianceItem) register from
# ApplicationsConfig.ready(). Track B verbs (workflow.transitioned,
# signing.*) emit explicitly via record_activity() from harbor's services.
KEEL_ACTIVITY_MODEL = 'applications.Activity'
KEEL_WATCHER_MODEL = 'applications.Watcher'
KEEL_PRODUCT_BASE_URL = os.environ.get('KEEL_PRODUCT_BASE_URL', 'https://harbor.docklabs.ai')
KEEL_FEED_USER_TOKEN_SECRET = os.environ.get('KEEL_FEED_USER_TOKEN_SECRET', '')

KEEL_CSP_POLICY = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data: https:; connect-src 'self' https://keel.docklabs.ai https://demo-keel.docklabs.ai"  # Start permissive, tighten later
KEEL_FILE_SCANNING_ENABLED = not DEBUG
KEEL_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
KEEL_ALLOWED_UPLOAD_EXTENSIONS = [
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.txt', '.rtf',
    '.odt', '.ods', '.ppt', '.pptx', '.png', '.jpg', '.jpeg', '.gif',
    '.tiff', '.zip', '.gz',
]

# --- Admin allowlist + trusted-proxy config (keel.security) ---
# KEEL_ADMIN_ALLOWED_IPS: list of CIDR / IPs allowed to hit /admin/.
#   Empty list = no-op (dev). Set via env on every Railway service in prod.
# KEEL_TRUSTED_PROXY_COUNT: number of trusted proxies between the client and
#   Django. Railway = 1. If 0, X-Forwarded-For is ignored (client spoof-safe).
KEEL_ADMIN_ALLOWED_IPS = [
    ip.strip() for ip in os.environ.get('KEEL_ADMIN_ALLOWED_IPS', '').split(',')
    if ip.strip()
]
KEEL_TRUSTED_PROXY_COUNT = int(os.environ.get('KEEL_TRUSTED_PROXY_COUNT', '1'))
