"""Public, unauthenticated pages: the marketing/home page and health check."""

from django.http import JsonResponse
from django.views.generic import TemplateView


class HomeView(TemplateView):
    """Landing page with the hero and the authorised-training-environment notice."""

    template_name = "core/home.html"


def healthcheck(request):
    """Lightweight liveness probe for load balancers / uptime monitors."""
    return JsonResponse({"status": "ok"})
