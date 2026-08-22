"""
Production settings for AWS Lightsail (Nginx -> Daphne/ASGI -> Django).

Everything security-sensitive is enforced here and driven by environment
variables.  ``DEBUG`` is hard-forced off regardless of the environment value.
"""

from .base import *  # noqa: F401,F403
from .env_utils import env_bool

# ---------------------------------------------------------------------------
# Hard security posture
# ---------------------------------------------------------------------------
DEBUG = False  # Never enable debug in production.

# ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS / SECRET_KEY come from the environment
# (see base.py).  Fail loudly if the secret key was left at the dev default.
if SECRET_KEY == "unsafe-dev-key-change-me":  # noqa: F405
    raise RuntimeError(
        "SECRET_KEY must be set to a strong random value in production."
    )

# ---------------------------------------------------------------------------
# HTTPS / secure cookies / headers
# ---------------------------------------------------------------------------
# HTTPS redirect is ON by default; may be disabled (e.g. for a plain-HTTP
# local compose run) via SECURE_SSL_REDIRECT=False.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
# Nginx terminates TLS and forwards this header so Django knows the original
# request was HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # Needs JS access for the fetch()-based API calls.
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# HSTS: tell browsers to stick to HTTPS.  Start conservative; raise the age
# once you're confident the TLS setup is stable.
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Require a real broker in production
# ---------------------------------------------------------------------------
if not REDIS_URL:  # noqa: F405
    raise RuntimeError(
        "REDIS_URL must be configured in production so Django Channels can "
        "share WebSocket state across worker processes."
    )
