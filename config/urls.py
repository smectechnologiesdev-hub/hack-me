"""
Root URL configuration.

There is ONE login endpoint that matters: ``/login/`` (``apps.accounts``).  It
serves BOTH the browser sign-in form and the brute-force script.

The ``/labs/`` and ``/api/labs/`` routes are legacy (the older per-lab token
flow) and are not part of the simple login-crack experience.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # HTML / template routes
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("instructor/", include(("apps.dashboard.urls_instructor", "instructor"))),

    # Legacy token-based lab flow (kept for compatibility; not used by the UI).
    path("labs/", include("apps.labs.urls_html")),
    path("api/labs/", include("apps.labs.urls_api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
