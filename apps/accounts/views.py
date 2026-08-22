"""Registration / login / logout views.

``PortalLoginView`` is the ONE login endpoint (``/login/``) used by BOTH the
browser sign-in form and the brute-force script.  It is CSRF-exempt so a basic
script needs no token, and it answers with a redirect for browsers or plain
JSON for scripts.
"""

import json

from django.contrib.auth import authenticate, login
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView

from .forms import StudentRegistrationForm, StyledAuthenticationForm


class RegisterView(CreateView):
    """Self-service registration; logs the user straight in on success."""

    form_class = StudentRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        self.request.session["just_accessed"] = True
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return super().dispatch(request, *args, **kwargs)


def _wants_json(request) -> bool:
    """True for API/script clients, False for browser navigations.

    Browsers send ``text/html`` in their Accept header; the ``requests``
    library (and curl) default to ``*/*``.
    """
    if request.content_type == "application/json":
        return True
    return "text/html" not in request.headers.get("Accept", "")


@method_decorator(csrf_exempt, name="dispatch")
class PortalLoginView(View):
    """The single login endpoint — browser form AND brute-force target.

    * ``GET``  -> render the Vaultline sign-in page.
    * ``POST`` -> authenticate ``username`` + ``password`` (form-encoded or
      JSON).  Browsers are redirected to the dashboard on success and re-shown
      the form on failure; scripts get ``{"success": true|false}``.
    """

    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(
            request, self.template_name, {"form": StyledAuthenticationForm(request)}
        )

    def post(self, request):
        # Accept either a posted form (browser) or a JSON body (script).
        if request.content_type == "application/json":
            try:
                data = json.loads(request.body or b"{}")
            except ValueError:
                data = {}
        else:
            data = request.POST

        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            request.session["just_accessed"] = True
            if _wants_json(request):
                return JsonResponse(
                    {"success": True, "message": "Authentication successful"}
                )
            return redirect("dashboard:home")

        # Failure
        if _wants_json(request):
            return JsonResponse(
                {"success": False, "message": "Invalid credentials"}, status=401
            )
        form = StyledAuthenticationForm(request, data=data)
        form.is_valid()  # populate the "invalid credentials" error for display
        return render(request, self.template_name, {"form": form})


class LabLogoutView(LogoutView):
    """Logout (POST only, per Django's CSRF-safe default)."""
