"""
Vaultline Heist — challenge data model.

A ``VaultClient`` is a per-student **target** account in the deliberately
vulnerable "client portal".  Each student is assigned exactly one; cracking
someone else's earns nothing, because the final flag only credits the student
the target was assigned to.

The whole kill chain and its milestones live on this one row:

    crack login  ->  download data export  ->  rotate password  ->  open vault
    ->  capture flag

Security note: ``password`` and the vault credentials are stored in the clear
**on purpose** — this is the target of the exercise.  The portal login checks
``password`` with a raw, injectable SQL query (see ``services.portal_authenticate``).
Nothing here is a real credential.
"""

import secrets

from django.conf import settings
from django.db import models


def generate_flag() -> str:
    """A unique capture flag, e.g. ``HM{3f9a...}``."""
    return f"HM{{{secrets.token_hex(8)}}}"


class VaultClient(models.Model):
    """One per-student target account in the vulnerable Vaultline portal."""

    # -- Portal login (the attack surface) ---------------------------------
    username = models.CharField(max_length=64, unique=True)
    # Cleartext by design: the legacy portal verifies it with raw injectable
    # SQL. This is the intentionally-vulnerable target, not a real credential.
    password = models.CharField(max_length=128)
    display_name = models.CharField(max_length=120, blank=True)

    # -- The vault (the objective) -----------------------------------------
    vault_id = models.CharField(max_length=32)
    vault_password = models.CharField(max_length=64)
    flag = models.CharField(max_length=64, unique=True, default=generate_flag)

    # -- Data-export crypto: two independent AES-256 secrets ----------------
    # The export encrypts {username, password} under ``account_key`` and
    # {vault_id, vault_password} under ``vault_key`` (AES-256-CBC, encode-decode.com
    # compatible; blobs generated on the fly at export time — no ciphertext stored).
    account_key = models.CharField(max_length=64, blank=True)  # AES-256 secret
    vault_key = models.CharField(max_length=64, blank=True)    # AES-256 secret

    # -- Chain gate: the vault input unlocks only after a real rotation -----
    password_rotated = models.BooleanField(default=False)
    rotated_password = models.CharField(max_length=128, blank=True)

    # -- Assignment + per-student progress ---------------------------------
    assigned_to = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vault_target",
    )
    cracked_login_at = models.DateTimeField(null=True, blank=True)
    downloaded_data_at = models.DateTimeField(null=True, blank=True)
    rotated_password_at = models.DateTimeField(null=True, blank=True)
    opened_vault_at = models.DateTimeField(null=True, blank=True)
    captured_flag_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["username"]
        indexes = [
            models.Index(fields=["assigned_to"]),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"VaultClient<{self.username}>"

    # -- Scoring -----------------------------------------------------------
    # Milestone -> points.  Total for a full solve = 1000.
    POINTS = {
        "cracked_login_at": 100,
        "downloaded_data_at": 150,
        "rotated_password_at": 100,
        "opened_vault_at": 250,
        "captured_flag_at": 400,
    }
    # Human labels for the scoreboard / progress UI, in chain order.
    STAGES = [
        ("cracked_login_at", "Broke in"),
        ("downloaded_data_at", "Found the data export"),
        ("rotated_password_at", "Rotated the password"),
        ("opened_vault_at", "Opened the vault"),
        ("captured_flag_at", "Captured the flag"),
    ]

    @property
    def points(self) -> int:
        return sum(pts for field, pts in self.POINTS.items() if getattr(self, field))

    @property
    def stages_done(self) -> int:
        return sum(1 for field in self.POINTS if getattr(self, field))

    @property
    def is_solved(self) -> bool:
        return self.captured_flag_at is not None

    @property
    def progress(self) -> list[dict]:
        """Ordered stage list for the mission UI: label + whether it's done."""
        return [
            {"label": label, "done": getattr(self, field) is not None, "at": getattr(self, field)}
            for field, label in self.STAGES
        ]
