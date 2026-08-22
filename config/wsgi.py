"""
WSGI entry point (used by Gunicorn when WebSockets are handled separately).

For a single-server deployment prefer the ASGI entry point so HTTP and
WebSocket traffic share one process.  This file exists for compatibility and
for pure-HTTP deployments.
"""

import os

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
