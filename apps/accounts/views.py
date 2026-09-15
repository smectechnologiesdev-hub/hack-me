"""Registration / login / logout views.

``PortalLoginView`` is the ONE password login endpoint (``/login/``) used by
BOTH the browser sign-in form and the brute-force script.  It is CSRF-exempt so
a basic script needs no token, and it answers with a redirect for browsers or
plain JSON for scripts.

The OTP views add a second, separate exercise: "Sign in with OTP".  Requesting a
code mints a hidden 4-digit number for a **username** (stored server-side, never
returned); verifying exchanges the correct code for a login.  The code is keyed
by username — not by the session — so a plain, stateless script can request a
code and then brute-force ``{username, otp}`` without carrying any cookie.
"""

import json
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView

from .forms import StudentRegistrationForm, StyledAuthenticationForm
from .models import OtpChallenge

# How long a minted OTP stays valid, in seconds.  Generous on purpose: a
# single-threaded script may walk all 10 000 codes over the network before it
# lands the right one, and we don't want the code to expire mid-exercise.
OTP_TTL_SECONDS = getattr(settings, "OTP_TTL_SECONDS", 1800)


def _assign_target(user) -> None:
    """Assign a spare Vaultline Heist target to a freshly-registered student.

    Row-locked so two simultaneous registrations can't grab the same target.
    If no spare exists, the student is left unassigned (an instructor provisions
    more with ``manage.py provision_challenge``).
    """
    from django.db import transaction

    from apps.challenge.models import VaultClient

    try:
        with transaction.atomic():
            spare = (
                VaultClient.objects.select_for_update()
                .filter(assigned_to__isnull=True)
                .order_by("id")
                .first()
            )
            if spare is not None:
                spare.assigned_to = user
                spare.save(update_fields=["assigned_to"])
    except Exception:
        # Never let assignment break registration.
        pass


class RegisterView(CreateView):
    """Self-service registration; logs the user straight in on success."""

    form_class = StudentRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("dashboard:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        self.request.session["just_accessed"] = True
        _assign_target(self.object)
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


def _request_data(request) -> dict:
    """Return the POST payload as a dict, accepting form-encoded OR JSON bodies."""
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return request.POST


@method_decorator(csrf_exempt, name="dispatch")
class PortalLoginView(View):
    """The single password login endpoint — browser form AND brute-force target.

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
        data = _request_data(request)
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


# --------------------------------------------------------------------------- #
#  OTP sign-in ("Sign in with OTP")                                           #
# --------------------------------------------------------------------------- #

def _generate_otp() -> str:
    """A cryptographically-random 4-digit code, zero-padded (``"0000"``–``"9999"``)."""
    return f"{secrets.randbelow(10000):04d}"


def _otp_target(username: str):
    """Return the user OTP login is allowed for, or ``None``.

    A 4-digit code is trivially brute-forced, so OTP login must never expose a
    staff/superuser account.
    """
    User = get_user_model()
    user = User.objects.filter(username=username, is_active=True).first()
    if user and not (user.is_staff or user.is_superuser):
        return user
    return None


class OtpLoginPageView(View):
    """Browser page for OTP sign-in.

    Stage is driven by the ``u`` query param (the username a code was requested
    for) rather than the session, so nothing here depends on a cookie.
    """

    template_name = "accounts/otp_login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        username = (request.GET.get("u") or "").strip()
        stage = "verify" if username else "request"
        return render(
            request, self.template_name, {"otp_stage": stage, "otp_username": username}
        )


@method_decorator(csrf_exempt, name="dispatch")
class OtpRequestView(View):
    """Step 1: mint a hidden 4-digit OTP for a username.

    The code is stored server-side (one per username) and is **never** included
    in any response.  We answer identically whether or not the username exists,
    so the endpoint does not leak which accounts are real.
    """

    def post(self, request):
        data = _request_data(request)
        username = (data.get("username") or "").strip()

        user = _otp_target(username)
        if user is not None:
            OtpChallenge.objects.update_or_create(
                username=user.username, defaults={"code": _generate_otp()}
            )

        message = "A 4-digit code has been generated. Enter it to sign in."
        if _wants_json(request):
            return JsonResponse({"success": True, "message": message})
        return redirect(f"{reverse('accounts:otp_login')}?{urlencode({'u': username})}")


@method_decorator(csrf_exempt, name="dispatch")
class OtpVerifyView(View):
    """Step 2: exchange the correct OTP for ``username`` for a login.

    Stateless: the caller sends ``{username, otp}``; no session cookie needed.
    There is intentionally no attempt cap — guessing the code is the exercise —
    but the code still expires after ``OTP_TTL_SECONDS`` and is single-use.
    """

    def post(self, request):
        data = _request_data(request)
        username = (data.get("username") or "").strip()
        code = (data.get("otp") or data.get("code") or "").strip()

        challenge = (
            OtpChallenge.objects.filter(username=username).first() if username else None
        )
        if challenge and self._code_matches(code, challenge):
            user = _otp_target(username)
            if user is not None:
                challenge.delete()  # consume: a code works only once
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                request.session["just_accessed"] = True
                if _wants_json(request):
                    return JsonResponse(
                        {"success": True, "message": "Authentication successful"}
                    )
                return redirect("dashboard:home")

        # Failure
        if _wants_json(request):
            return JsonResponse(
                {"success": False, "message": "Invalid or expired code"}, status=401
            )
        return render(
            request,
            "accounts/otp_login.html",
            {
                "otp_stage": "verify",
                "otp_username": username,
                "otp_error": "Invalid or expired code.",
            },
        )

    @staticmethod
    def _code_matches(code: str, challenge: OtpChallenge) -> bool:
        if not (code and challenge.code):
            return False
        age = (timezone.now() - challenge.issued_at).total_seconds()
        if age > OTP_TTL_SECONDS:
            return False
        # Length-check first so compare_digest doesn't raise on mismatched sizes.
        return len(code) == len(challenge.code) and secrets.compare_digest(
            code, challenge.code
        )


class LabLogoutView(LogoutView):
    """Logout (POST only, per Django's CSRF-safe default)."""
