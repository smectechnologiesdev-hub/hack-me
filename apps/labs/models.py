"""
Lab domain models: ``Wordlist`` and ``Lab``.

Security notes for readers/students:

* ``Lab.lab_token`` is a cryptographically-random, URL-safe string.  It is the
  ONLY handle a student uses to address their lab, and it is unguessable.
* ``Lab.target_password_hash`` stores the correct password using Django's
  password hasher (PBKDF2 by default).  The plaintext target is never stored
  and is never exposed through any template, API or WebSocket.
* A student can only ever reach a lab they own (enforced in the views/queries),
  and they cannot change ``lab_token`` to reach someone else's lab.
"""

import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


def generate_lab_token() -> str:
    """Return a 32-char, URL-safe, cryptographically-secure lab token."""
    # token_urlsafe(24) -> ~32 chars of base64url; ample entropy, unguessable.
    return secrets.token_urlsafe(24)


# Fictional client-name parts, used to make the target account feel like a
# real private-banking login (e.g. "m.kessler") rather than an obvious test id.
_FIRST_INITIALS = list("jmasrkltenphdcbg")
_LAST_NAMES = [
    "reynolds", "kessler", "harper", "donovan", "mercer", "vaughn", "sloane",
    "ellison", "brooks", "navarro", "whitlock", "ashford", "lockhart", "sterling",
    "beckett", "hollis", "marlowe", "cavanagh", "rutledge", "delacroix",
]


def generate_lab_username() -> str:
    """Return a bank-style client username like ``m.kessler``."""
    return f"{secrets.choice(_FIRST_INITIALS)}.{secrets.choice(_LAST_NAMES)}"


class Wordlist(models.Model):
    """A server-controlled, predefined set of candidate passwords.

    Students never upload or edit wordlists; instructors manage them via the
    admin.  Each lab is assigned exactly one wordlist and the target password
    is always drawn from that list.
    """

    class Difficulty(models.TextChoices):
        EASY = "EASY", "Easy"
        MEDIUM = "MEDIUM", "Medium"
        HARD = "HARD", "Hard"

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, default=Difficulty.EASY
    )
    # A simple JSON list of strings, e.g. ["password", "123456", ...].
    passwords = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["difficulty", "name"]
        indexes = [models.Index(fields=["is_active", "difficulty"])]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.name} ({self.get_difficulty_display()})"

    @property
    def size(self) -> int:
        return len(self.passwords or [])

    def clean(self):
        """Validate that the JSON payload is a non-empty list of strings."""
        from django.core.exceptions import ValidationError

        if not isinstance(self.passwords, list) or not self.passwords:
            raise ValidationError({"passwords": "Provide a non-empty list of passwords."})
        if not all(isinstance(p, str) and p for p in self.passwords):
            raise ValidationError({"passwords": "Every password must be a non-empty string."})


class Lab(models.Model):
    """An isolated brute-force training session belonging to one student."""

    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired"
        LOCKED = "LOCKED", "Locked"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="labs",
    )
    lab_token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_lab_token,
        editable=False,
        db_index=True,
    )
    username = models.CharField(max_length=64, default=generate_lab_username)

    # The correct password, stored ONLY as a Django password hash.
    target_password_hash = models.CharField(max_length=256, editable=False)

    wordlist = models.ForeignKey(
        Wordlist, on_delete=models.PROTECT, related_name="labs"
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED
    )

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    max_attempts = models.PositiveIntegerField(default=settings.LAB_MAX_ATTEMPTS)
    attempt_count = models.PositiveIntegerField(default=0)

    # Instructors can disable a lab; the login endpoint honours this.
    is_active = models.BooleanField(default=True)

    # The single global target behind the tokenless /api/login/ endpoint.
    # Exactly one lab is primary at a time (enforced in the service layer).
    is_primary = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["status", "expires_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attempt_count__lte=models.F("max_attempts")),
                name="attempt_count_within_max",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"Lab {self.lab_token[:8]}… for {self.student}"

    # ------------------------------------------------------------------
    # Target password handling (never exposes plaintext)
    # ------------------------------------------------------------------
    def set_target_password(self, raw_password: str) -> None:
        """Hash and store the target password chosen from the wordlist."""
        self.target_password_hash = make_password(raw_password)

    def check_target_password(self, candidate: str) -> bool:
        """Constant-time-ish comparison of a candidate against the target hash."""
        return check_password(candidate, self.target_password_hash)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def attempts_remaining(self) -> int:
        return max(self.max_attempts - self.attempt_count, 0)

    @property
    def is_open(self) -> bool:
        """True only if the lab can still accept attempts right now."""
        return (
            self.is_active
            and self.status in {self.Status.CREATED, self.Status.ACTIVE}
            and not self.is_expired
            and self.attempt_count < self.max_attempts
        )
