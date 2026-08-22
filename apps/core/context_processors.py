"""Template context processors exposing safe, global flags to every page."""

from django.conf import settings


def site_flags(request):
    """Expose a handful of harmless, display-only settings to templates."""
    return {
        # Fictional premium private-bank brand used across the UI.
        "SITE_NAME": "Vaultline",
        "SITE_TAGLINE": "Private banking, secured.",
        "LAB_MAX_ATTEMPTS_DEFAULT": settings.LAB_MAX_ATTEMPTS,
        "LAB_DURATION_MINUTES_DEFAULT": settings.LAB_DURATION_MINUTES,
    }
