"""
Django settings for SolarGuard project.
SEPM College Project Prototype - AI-Powered Solar Panel Fault Detection & Degradation Prediction
Production-ready configuration for Oracle Cloud Always Free Ampere A1 (Ubuntu ARM64)
and local development (Windows / Linux / macOS).
"""

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Automatically load local .env or systemd env file if present
_candidate_envs = [
    BASE_DIR / '.env',
    Path('/etc/solarguard/solarguard.env'),
]
for _env_file in _candidate_envs:
    if _env_file.is_file():
        try:
            with open(_env_file, 'r', encoding='utf-8') as _ef:
                for _line in _ef:
                    _line = _line.strip()
                    if _line and not _line.startswith('#') and '=' in _line:
                        _k, _v = _line.split('=', 1)
                        _k = _k.strip()
                        _v = _v.strip().strip('"').strip("'")
                        os.environ.setdefault(_k, _v)
        except Exception:
            pass

# Optional production packages with graceful fallbacks
try:
    import dj_database_url
    _HAS_DJ_DATABASE_URL = True
except ImportError:
    _HAS_DJ_DATABASE_URL = False

try:
    import whitenoise
    _HAS_WHITENOISE = True
except ImportError:
    _HAS_WHITENOISE = False

# -----------------------------------------------------------------------------
# Core Security Settings
# -----------------------------------------------------------------------------
CLOUDFLARE_DEMO_MODE = os.environ.get('CLOUDFLARE_DEMO_MODE', 'False').lower() in ('true', '1', 'yes')

if CLOUDFLARE_DEMO_MODE:
    DEBUG = False
else:
    DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-solarguard-sepm-prototype-key-2026-demo'
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY environment variable is required in production when DEBUG=False.")

# ALLOWED_HOSTS configuration (Support *.trycloudflare.com securely without wildcard '*')
allowed_hosts_env = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]
    if DEBUG and 'testserver' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('testserver')
elif CLOUDFLARE_DEMO_MODE:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '.trycloudflare.com']
elif DEBUG:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver', '*']
else:
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

if CLOUDFLARE_DEMO_MODE and '.trycloudflare.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.trycloudflare.com')

# CSRF Trusted Origins (Required for POST requests on public IPs & custom domains)
csrf_origins_env = os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(',') if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = []
    # Auto-generate CSRF origins from ALLOWED_HOSTS
    for _host in ALLOWED_HOSTS:
        if _host and _host not in ('*', 'localhost', '127.0.0.1'):
            if _host.startswith('.'):
                CSRF_TRUSTED_ORIGINS.append(f"https://*{_host}")
            else:
                CSRF_TRUSTED_ORIGINS.append(f"http://{_host}")
                CSRF_TRUSTED_ORIGINS.append(f"https://{_host}")

if CLOUDFLARE_DEMO_MODE:
    for _cf_origin in ('https://*.trycloudflare.com', 'http://127.0.0.1:8000', 'http://localhost:8000'):
        if _cf_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(_cf_origin)

# Django Admin Exposure Control (Disabled by default in public demo mode to prevent brute-force attacks)
ENABLE_ADMIN = os.environ.get(
    'SOLARGUARD_ENABLE_ADMIN',
    'False' if CLOUDFLARE_DEMO_MODE else 'True'
).lower() in ('true', '1', 'yes')

# -----------------------------------------------------------------------------
# Application definition
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
]

if _HAS_WHITENOISE and not DEBUG:
    INSTALLED_APPS.append('whitenoise.runserver_nostatic')

INSTALLED_APPS.extend([
    'django.contrib.staticfiles',
    # Local Apps
    'core',
])

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
]

if _HAS_WHITENOISE:
    MIDDLEWARE.append('whitenoise.middleware.WhiteNoiseMiddleware')

MIDDLEWARE.extend([
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
])

ROOT_URLCONF = 'solarguard_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'core.context_processors.global_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'solarguard_project.wsgi.application'

# -----------------------------------------------------------------------------
# Database Configuration
# College Demo: SQLite stored on persistent VM storage with 20s lock timeout.
# Optional PostgreSQL supported via DATABASE_URL.
# -----------------------------------------------------------------------------
sqlite_path = Path(os.environ.get('SOLARGUARD_DB_PATH', str(BASE_DIR / 'db.sqlite3')))
db_url = os.environ.get('DATABASE_URL')

if db_url and _HAS_DJ_DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=db_url,
            conn_max_age=int(os.environ.get('DJANGO_DB_CONN_MAX_AGE', '600')),
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_path,
            'OPTIONS': {
                'timeout': 20,
            },
        }
    }

# -----------------------------------------------------------------------------
# Password validation
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 4,
        }
    },
]

# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# Static files (CSS, JavaScript, Images) with WhiteNoise Storage
# -----------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

if _HAS_WHITENOISE and not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

# -----------------------------------------------------------------------------
# Media files (Uploaded solar panel images) & Persistent VM Storage
# -----------------------------------------------------------------------------
MEDIA_URL = '/media/'
# Persistent directory on VM for inspection photos and reports
MEDIA_ROOT = Path(os.environ.get('SOLARGUARD_MEDIA_ROOT', str(BASE_DIR / 'media')))

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication redirects
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# -----------------------------------------------------------------------------
# SolarGuard ML Model Settings (Real MobileNetV2 CNN v3.0)
# -----------------------------------------------------------------------------
ML_MODELS_DIR = BASE_DIR / 'ml_models'

# Active Model Version Selection: 'v3' (default), 'v3.1', 'v2', or 'v1'
SOLARGUARD_MODEL_VERSION = os.environ.get('SOLARGUARD_MODEL_VERSION', 'v3').lower().strip()

MODEL_CATALOG = {
    'v1': {
        'model_file': 'solarguard_model.keras',
        'metadata_file': 'model_metadata.json',
        'version': '1.0',
        'description': 'Version 1 (Initial MobileNetV2 baseline)',
    },
    'v2': {
        'model_file': 'solarguard_model_v2.keras',
        'metadata_file': 'model_metadata_v2.json',
        'version': '2.0',
        'description': 'Version 2 (MobileNetV2 420-test)',
    },
    'v3': {
        'model_file': 'solarguard_model_v3.keras',
        'metadata_file': 'model_metadata_v3.json',
        'version': '3.0',
        'description': 'Version 3 (MobileNetV2 Argmax 485-test)',
    },
    'v3.1': {
        'model_file': 'solarguard_model_v3_1.keras',
        'metadata_file': 'model_metadata_v3_1.json',
        'version': '3.1',
        'description': 'Version 3.1 (MobileNetV2 Class-Weighted)',
    },
}

_raw_ver = SOLARGUARD_MODEL_VERSION
if _raw_ver in ('3.1', 'v3.1', '3_1', 'v3_1', 'version3.1'):
    _ver_key = 'v3.1'
elif _raw_ver in ('3', 'v3', '3.0', 'version3', 'v3.0'):
    _ver_key = 'v3'
elif _raw_ver in ('2', 'v2', '2.0', 'version2', 'v2.0'):
    _ver_key = 'v2'
elif _raw_ver in ('1', 'v1', '1.0', 'version1', 'v1.0'):
    _ver_key = 'v1'
else:
    _ver_key = 'v3'

_active_spec = MODEL_CATALOG[_ver_key]

CNN_MODEL_PATH = Path(
    os.environ.get('SOLARGUARD_CNN_MODEL_PATH', str(ML_MODELS_DIR / _active_spec['model_file']))
)
CNN_METADATA_PATH = Path(
    os.environ.get('SOLARGUARD_CNN_METADATA_PATH', str(ML_MODELS_DIR / _active_spec['metadata_file']))
)

# Robust fallback to 'Trained model Colab' if files are accessed from Colab directory
if not CNN_MODEL_PATH.exists():
    _colab_model = BASE_DIR / 'Trained model Colab' / _active_spec['model_file']
    if _colab_model.exists():
        CNN_MODEL_PATH = _colab_model

if not CNN_METADATA_PATH.exists():
    _colab_meta = BASE_DIR / 'Trained model Colab' / _active_spec['metadata_file']
    if _colab_meta.exists():
        CNN_METADATA_PATH = _colab_meta

USE_REAL_CNN = os.environ.get('SOLARGUARD_USE_REAL_CNN', 'True').lower() in ('true', '1', 'yes')
SOLARGUARD_USE_DEV_MOCK = os.environ.get('SOLARGUARD_USE_DEV_MOCK', 'False').lower() in ('true', '1', 'yes')
CNN_CONFIDENCE_THRESHOLD = float(os.environ.get('SOLARGUARD_CONFIDENCE_THRESHOLD', '60.0'))
CNN_MARGIN_THRESHOLD = float(os.environ.get('SOLARGUARD_MARGIN_THRESHOLD', '15.0'))

# -----------------------------------------------------------------------------
# Security & Session Hardening
# -----------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 86400  # 24-hour session lifetime
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = 'DENY'

# Production Reverse Proxy & SSL Security Headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # SSL Redirection and Cookies (Enable via environment when domain/SSL is active)
    SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 'yes')

    # Automatically align cookie security with SSL status or Cloudflare demo mode
    _default_cookie_secure = 'True' if (SECURE_SSL_REDIRECT or CLOUDFLARE_DEMO_MODE) else 'False'
    SESSION_COOKIE_SECURE = os.environ.get('DJANGO_SESSION_COOKIE_SECURE', _default_cookie_secure).lower() in ('true', '1', 'yes')
    CSRF_COOKIE_SECURE = os.environ.get('DJANGO_CSRF_COOKIE_SECURE', _default_cookie_secure).lower() in ('true', '1', 'yes')

    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '31536000'))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

# -----------------------------------------------------------------------------
# Razorpay Payment Gateway (Test Mode / Sandbox)
# -----------------------------------------------------------------------------
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '').strip()
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '').strip()
RAZORPAY_CURRENCY = 'INR'
RAZORPAY_CONFIGURED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
