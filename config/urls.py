"""
Root URL configuration.

Browser (HTML) routes live under each app's ``urls.py``; the JSON API lives
under ``/api/``.  The single, tokenless attack surface is at ``/api/login/``.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.labs.api_views import (
    PublicLoginView,
    PublicTargetView,
    PublicWordlistView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # HTML / template routes
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("labs/", include("apps.labs.urls_html")),
    path("instructor/", include(("apps.dashboard.urls_instructor", "instructor"))),

    # Tokenless public API — the "normal" attack surface (one global target).
    path("api/login/", PublicLoginView.as_view(), name="public-login"),
    path("api/target/", PublicTargetView.as_view(), name="public-target"),
    path("api/wordlist.txt", PublicWordlistView.as_view(), name="public-wordlist"),

    # Token-scoped lab API (kept for the per-student/self-serve flow)
    path("api/labs/", include("apps.labs.urls_api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
