"""
Development settings.

Loaded by default (see ``manage.py``).  Prioritises developer convenience:
DEBUG on, permissive hosts, no HTTPS enforcement.  NEVER use in production.
"""

from .base import *  # noqa: F401,F403
from .env_utils import env_bool

# Force DEBUG on locally unless explicitly disabled.
DEBUG = env_bool("DEBUG", default=True)

# Local development hosts.
ALLOWED_HOSTS = ALLOWED_HOSTS or ["127.0.0.1", "localhost"]  # noqa: F405

# Show emails in the console instead of sending them.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Relax the manifest static storage in dev so missing hashed files don't 500.
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
}
