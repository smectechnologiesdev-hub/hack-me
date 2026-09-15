"""
Base Django settings shared by every environment.

Environment-specific modules (``dev.py`` / ``prod.py``) import everything from
here and override only what differs.  All secrets and environment-dependent
values are read from environment variables (loaded from ``.env`` by
``manage.py`` / the ASGI/WSGI entry points).
"""

from pathlib import Path

import dj_database_url

from .env_utils import env_bool, env_csv, env_int, env_str

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# BASE_DIR = <repo root> (three parents up from this file:
# config/settings/base.py -> config/settings -> config -> <root>)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Security-critical core settings (env driven)
# ---------------------------------------------------------------------------
SECRET_KEY = env_str("SECRET_KEY", default="unsafe-dev-key-change-me")
DEBUG = env_bool("DEBUG", default=False)
ALLOWED_HOSTS = env_csv("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env_csv("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    # Daphne must appear before staticfiles so its runserver command is used.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.labs",
    "apps.attempts",
    "apps.dashboard",
    "apps.challenge",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves static files efficiently in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# DATABASE_URL drives the connection.  When empty we fall back to a local
# SQLite file so the project runs out of the box with zero configuration.
DATABASE_URL = env_str("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL, conn_max_age=600, conn_health_checks=True
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            # Wait (rather than immediately erroring) when the database is
            # briefly locked by a concurrent writer.  This lets the
            # select_for_update-based attempt processing behave sensibly under
            # concurrent requests even on SQLite; PostgreSQL handles this
            # natively via true row-level locks.
            "OPTIONS": {
                "timeout": 30,
                # Begin every transaction with BEGIN IMMEDIATE so a writer
                # takes the write lock up front instead of trying to upgrade a
                # read lock mid-transaction (which SQLite refuses to wait on and
                # reports as an immediate "database is locked").  With this, the
                # busy-timeout above actually serialises concurrent writers.
                "transaction_mode": "IMMEDIATE",
                # WAL lets readers proceed while a writer holds the lock.
                "init_command": "PRAGMA journal_mode=WAL;",
            },
            # Use a real on-disk file for the test database too.  Django's
            # default in-memory test DB uses SQLite's shared-cache mode, which
            # raises SQLITE_LOCKED (not waitable) under write contention; a
            # file-based DB raises the waitable SQLITE_BUSY instead, so the
            # busy-timeout above lets the concurrency tests serialise correctly.
            "TEST": {"NAME": BASE_DIR / "test_db.sqlite3"},
        }
    }

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "core:home"

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Infrastructure-level throttling.  This protects the *server* from abuse.
    # It is deliberately generous so that legitimate brute-force *training*
    # against a student's own isolated lab still works, while preventing a
    # single account from overwhelming the whole platform.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # The training login endpoint: high ceiling so brute-forcing is the
        # point, but still finite to protect shared infrastructure.
        "lab_login": "600/min",
        # General API browsing (start lab, read attempts, etc.).
        "lab_api": "120/min",
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# ---------------------------------------------------------------------------
# Channels (real-time WebSockets)
# ---------------------------------------------------------------------------
REDIS_URL = env_str("REDIS_URL", default="")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    # In-memory layer: single-process only, suitable for local development.
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# ---------------------------------------------------------------------------
# Request size guard (infrastructure protection)
# ---------------------------------------------------------------------------
# Reject oversized request bodies early.  The training endpoint only ever
# needs a tiny JSON payload, so a small ceiling is safe.
DATA_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024  # 512 KB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 100
FILE_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024

# ---------------------------------------------------------------------------
# Lab domain configuration (safe, server-controlled defaults)
# ---------------------------------------------------------------------------
LAB_MAX_ATTEMPTS = env_int("LAB_MAX_ATTEMPTS", default=100)
LAB_DURATION_MINUTES = env_int("LAB_DURATION_MINUTES", default=60)
SHOW_FULL_CANDIDATE_PASSWORDS = env_bool(
    "SHOW_FULL_CANDIDATE_PASSWORDS", default=False
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
