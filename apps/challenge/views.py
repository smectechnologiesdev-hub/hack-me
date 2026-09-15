"""
Vaultline Heist views.

Two audiences hit these:

* A student's **standalone script** POSTs candidate passwords to the portal
  login (``/portal/login/``) — content-negotiated to return plain JSON.
* A **browser** cracks/injects the login to explore the victim's account, walk
  the chain (data export -> rotate password -> open vault -> download loot), and
  watch the scoreboard.

Milestone attribution is by **target**, not by session: whoever compromises
client ``X`` advances the student ``X`` is assigned to.  The final flag can only
be *submitted* by that assigned student (they must be signed in as themselves),
so nobody can farm someone else's flag.
"""

import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .crypto import encrypt
from .models import VaultClient
from .services import (
    client_ip,
    portal_authenticate,
    rate_ok,
    record_milestone,
    scoreboard_rows,
)

PORTAL_SESSION_KEY = "portal_client_id"


# --------------------------------------------------------------------------- #
#  Small request helpers (accept form-encoded OR JSON; detect script clients)  #
# --------------------------------------------------------------------------- #
def _wants_json(request) -> bool:
    if request.content_type == "application/json":
        return True
    return "text/html" not in request.headers.get("Accept", "")


def _request_data(request) -> dict:
    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or b"{}")
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return request.POST


def _portal_client(request) -> VaultClient | None:
    """The victim client the browser is currently 'signed in' to, if any."""
    cid = request.session.get(PORTAL_SESSION_KEY)
    if not cid:
        return None
    return VaultClient.objects.filter(id=cid).first()


def _require_portal(request):
    """Return the portal client, or an HttpResponse redirect to the portal login."""
    client = _portal_client(request)
    if client is None:
        return None, redirect("challenge:portal_login")
    return client, None


# --------------------------------------------------------------------------- #
#  Stage 1 — the vulnerable client portal login                                #
# --------------------------------------------------------------------------- #
@method_decorator(csrf_exempt, name="dispatch")
class PortalLoginView(View):
    """GET renders the portal sign-in; POST is the brute-force / SQLi target."""

    template_name = "challenge/portal_login.html"

    def get(self, request):
        if _portal_client(request) is not None:
            return redirect("challenge:portal_home")
        return render(request, self.template_name, {})

    def post(self, request):
        ip = client_ip(request)
        if not rate_ok(ip):
            body = {"success": False, "message": "Too many attempts. Slow down."}
            if _wants_json(request):
                return JsonResponse(body, status=429)
            return render(request, self.template_name, {"error": body["message"]}, status=429)

        data = _request_data(request)
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        client = portal_authenticate(username, password)

        if client is not None:
            # First compromise of this target advances the assigned student.
            record_milestone(client, "cracked_login_at")
            if _wants_json(request):
                return JsonResponse(
                    {"success": True, "message": "Authentication successful"}
                )
            request.session[PORTAL_SESSION_KEY] = client.id
            return redirect("challenge:portal_home")

        if _wants_json(request):
            return JsonResponse(
                {"success": False, "message": "Invalid credentials"}, status=401
            )
        return render(
            request, self.template_name, {"error": "Invalid credentials."}, status=401
        )


class PortalLogoutView(View):
    """Drop the portal session (does not touch the participant's own login)."""

    def get(self, request):
        request.session.pop(PORTAL_SESSION_KEY, None)
        return redirect("challenge:portal_login")


# --------------------------------------------------------------------------- #
#  Stage 2 — the victim's account (locked vault + profile)                     #
# --------------------------------------------------------------------------- #
class PortalHomeView(View):
    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp
        return render(request, "challenge/portal_home.html", {"client": client})


class VaultView(View):
    """The Open Vault panel. The id/password inputs are gated server-side on a
    real password rotation (``password_rotated``)."""

    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp
        return render(
            request,
            "challenge/vault.html",
            {"client": client, "unlocked": client.opened_vault_at is not None},
        )

    def post(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp

        # Server-side gate: no vault access until the password has been rotated.
        if not client.password_rotated:
            return render(
                request,
                "challenge/vault.html",
                {"client": client, "error": "Vault is locked. Rotate your account password first."},
                status=403,
            )

        data = _request_data(request)
        vault_id = (data.get("vault_id") or "").strip()
        vault_password = (data.get("vault_password") or "").strip()

        if vault_id == client.vault_id and vault_password == client.vault_password:
            record_milestone(client, "opened_vault_at")
            return render(request, "challenge/vault.html", {"client": client, "unlocked": True})

        return render(
            request,
            "challenge/vault.html",
            {"client": client, "error": "Incorrect vault id or vault password."},
            status=401,
        )


class VaultLootView(View):
    """Download the vault loot (contains the flag). Requires an opened vault."""

    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp
        if client.opened_vault_at is None:
            return redirect("challenge:vault")

        contents = (
            "VAULTLINE PRIVATE — SEALED CLIENT RECORDS\n"
            "=========================================\n\n"
            f"Client:   {client.display_name or client.username}\n"
            f"Vault ID: {client.vault_id}\n\n"
            "Recovered documents: wire_authorisations.pdf, offshore_ledger.xlsx\n\n"
            f"FLAG: {client.flag}\n\n"
            "Submit this flag on the scoreboard to log your capture.\n"
        )
        resp = HttpResponse(contents, content_type="text/plain")
        resp["Content-Disposition"] = 'attachment; filename="vault_records.txt"'
        return resp


# --------------------------------------------------------------------------- #
#  Stage 3 — the over-sharing data export (the leak)                           #
# --------------------------------------------------------------------------- #
class ProfileView(View):
    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp
        return render(request, "challenge/profile.html", {"client": client})


class DataExportView(View):
    """Profile -> Data -> 'Download my data'. A GDPR-style export that
    over-shares: it leaks two recovery keys and the matching encrypted blobs.

    Both blobs are AES-256-CBC (encode-decode.com compatible), generated on the
    fly at download time — no ciphertext is stored."""

    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp

        record_milestone(client, "downloaded_data_at")

        export = {
            "display_name": client.display_name,
            "account_key": client.account_key,
            "account_blob": encrypt(
                {"username": client.username, "password": client.password},
                client.account_key,
            ),
            "vault_key": client.vault_key,
            "vault_blob": encrypt(
                {"vault_id": client.vault_id, "vault_password": client.vault_password},
                client.vault_key,
            ),
            "_note": (
                "Automated data export. account_blob and vault_blob are each AES-256 "
                "encrypted. To read one, paste its blob as the text and its matching key "
                "(account_key / vault_key) as the secret into an 'aes256' decrypt tool "
                "(e.g. encode-decode.com), or open tools/vaultline_decrypt.html."
            ),
        }
        resp = JsonResponse(export, json_dumps_params={"indent": 2})
        resp["Content-Disposition"] = 'attachment; filename="vaultline_data_export.json"'
        return resp


# --------------------------------------------------------------------------- #
#  Stage 4 — rotate the account password (unlocks the vault input)             #
# --------------------------------------------------------------------------- #
class RotatePasswordView(View):
    def get(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp
        return render(request, "challenge/rotate_password.html", {"client": client})

    def post(self, request):
        client, redirect_resp = _require_portal(request)
        if redirect_resp:
            return redirect_resp

        data = _request_data(request)
        new_password = data.get("new_password") or ""
        confirm = data.get("confirm_password") or ""

        if len(new_password) < 4:
            error = "Choose a new password of at least 4 characters."
        elif new_password != confirm:
            error = "Passwords do not match."
        else:
            error = None

        if error:
            return render(
                request, "challenge/rotate_password.html",
                {"client": client, "error": error}, status=400,
            )

        client.rotated_password = new_password
        client.password_rotated = True
        client.save(update_fields=["rotated_password", "password_rotated"])
        record_milestone(client, "rotated_password_at")
        return redirect(f"{reverse('challenge:vault')}?rotated=1")


# --------------------------------------------------------------------------- #
#  Scoreboard + flag submission                                                #
# --------------------------------------------------------------------------- #
class ScoreboardView(View):
    def get(self, request):
        return render(request, "challenge/scoreboard.html", {"rows": scoreboard_rows()})


class ScoreboardDataView(View):
    """JSON feed the scoreboard page polls for live-ish updates."""

    def get(self, request):
        return JsonResponse({"rows": scoreboard_rows()}, json_dumps_params={"default": str})


class FlagSubmitView(View):
    """A participant (signed in as themselves) submits the final flag.

    Only their **own** assigned target's flag is accepted, so a leaked flag is
    worthless to anyone else.
    """

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")

        target = VaultClient.objects.filter(assigned_to=request.user).first()
        submitted = (request.POST.get("flag") or "").strip()

        if target is None:
            msg = ("error", "You have no assigned target yet — ask your instructor.")
        elif submitted == target.flag:
            record_milestone(target, "captured_flag_at")
            msg = ("success", "🎉 Flag accepted — you're on the board!")
        else:
            msg = ("error", "That flag is not correct for your target.")

        request.session["flag_result"] = msg
        return redirect("dashboard:home")
