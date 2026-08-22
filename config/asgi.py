"""
ASGI entry point.

Routes HTTP traffic to the standard Django application and WebSocket traffic
to the Channels stack.  Used by Daphne / Uvicorn in both development
(``runserver`` via the ``daphne`` app) and production.
"""

import os

from dotenv import load_dotenv

# Load .env before Django settings are imported.
load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.asgi import get_asgi_application

# Initialise Django (populates the app registry) BEFORE importing anything that
# touches models — Channels routing imports consumers which import models.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.attempts.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # WebSocket connections are authenticated via the Django session
        # (AuthMiddlewareStack) and origin-checked against ALLOWED_HOSTS.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
