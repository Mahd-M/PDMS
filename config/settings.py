"""
Django settings for the Police Department Management System (PDMS).

Every security-relevant setting below is commented with the CJIS
Security Policy area it maps to (v6.0/6.1, 2024-2026). See
docs/CJIS_MAPPING.md for the full control-by-control writeup.
"""
from pathlib import Path

import dj_database_url

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# Never hardcode these in a real deployment -- set them as environment
# variables (or via a secrets manager) and keep this file identical
# across dev/staging/prod.
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-change-me")
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "cases",
    "evidence",
    "audit",
    "personnel",
    "dashboard",
    "records",
    "missing_persons",
    "vehicles",
    "search",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Custom, project-specific hardening -- see config/security_middleware.py
    "config.security_middleware.SecurityHeadersMiddleware",
    "config.security_middleware.SessionIdleTimeoutMiddleware",
    "config.security_middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite here purely so the repo runs out of the box for a demo/pilot.
# Production target is PostgreSQL with Row-Level Security + pgcrypto +
# pgAudit enabled -- see docs/DATABASE.md for the DDL and rationale.

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        env="DATABASE_URL",
    )
}

# Identification & Authentication -- CJIS Policy Area 6
# CJIS requires NIST SP 800-63-aligned password rules and has mandated
# advanced authentication (MFA, AAL2) for all CJI access since Oct 2024.
# Password strength lives here; MFA enforcement lives in accounts/views.py
# and the User model's TOTP fields.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# Account lockout thresholds used by accounts/views.py (CJIS 6: lockout
# after repeated failed attempts).
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 15

# Session security -- CJIS Policy Area 5 (Access Control): automatic
# session timeout so an unattended terminal doesn't stay authenticated.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60 * 30  # 30 minutes, enforced again by SessionIdleTimeoutMiddleware
CSRF_COOKIE_HTTPONLY = False  # must be readable by the template to embed {% csrf_token %}
CSRF_COOKIE_SAMESITE = "Strict"

# In production, behind TLS, set these True (they're env-driven so the
# same settings file works in local dev over plain HTTP).
_USE_TLS = env.bool("DJANGO_USE_TLS", default=False)
SESSION_COOKIE_SECURE = _USE_TLS
CSRF_COOKIE_SECURE = _USE_TLS
SECURE_SSL_REDIRECT = _USE_TLS
SECURE_HSTS_SECONDS = 31536000 if _USE_TLS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _USE_TLS
SECURE_HSTS_PRELOAD = _USE_TLS

# System & Communications Protection -- CJIS Policy Area 10
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# The Content-Security-Policy header that makes "no client JavaScript" a
# provable property of the deployment, not just a coding convention --
# see config/security_middleware.py for the actual header value.

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
