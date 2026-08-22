"""
Lab lifecycle service layer.

Business logic for creating and maintaining labs lives here (not in views) so
it can be reused by the API, the admin actions and the tests, and so views
stay thin.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Lab, Wordlist


class LabError(Exception):
    """Base class for lab service errors."""


class NoWordlistAvailable(LabError):
    """Raised when no active wordlist exists to build a lab from."""


def _pick_wordlist(difficulty: str | None = None) -> Wordlist:
    """Choose an active wordlist, optionally filtered by difficulty."""
    qs = Wordlist.objects.filter(is_active=True)
    if difficulty:
        qs = qs.filter(difficulty=difficulty)
    wordlist = qs.order_by("?").first()
    if wordlist is None:
        raise NoWordlistAvailable(
            "No active wordlist is available. An instructor must create one."
        )
    return wordlist


def _pick_target_password(wordlist: Wordlist) -> str:
    """Select the correct password for a lab from its wordlist.

    Uses ``secrets.choice`` (CSPRNG) so the target cannot be predicted from
    ordering.  The plaintext returned here is immediately hashed by the caller
    and never persisted in the clear.
    """
    passwords = [p for p in (wordlist.passwords or []) if isinstance(p, str) and p]
    if not passwords:
        raise LabError(f"Wordlist '{wordlist.name}' contains no usable passwords.")
    return secrets.choice(passwords)


def ensure_victim_user(username: str, raw_password: str):
    """Make the target account a REAL, loginable user.

    So that cracking ``m.kessler`` / ``hello123`` actually lets you sign in at
    ``/login/`` as that account — the payoff of the exercise.  Never clobbers a
    staff/superuser account (protects your admin login).
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=username, defaults={"role": User.Role.STUDENT}
    )
    if user.is_staff or user.is_superuser:
        # Don't reset an admin's password if a target happens to share the name.
        return user
    user.is_staff = False
    user.is_superuser = False
    user.set_password(raw_password)
    user.save()
    return user


@transaction.atomic
def create_lab_for_student(student, *, difficulty: str | None = None) -> Lab:
    """Create and persist a fresh, isolated lab for ``student``.

    The lab is created in the ACTIVE state, ready to accept attempts.  The
    target password is chosen server-side and stored only as a hash.
    """
    wordlist = _pick_wordlist(difficulty)
    target_password = _pick_target_password(wordlist)

    now = timezone.now()
    lab = Lab(
        student=student,
        wordlist=wordlist,
        status=Lab.Status.ACTIVE,
        max_attempts=settings.LAB_MAX_ATTEMPTS,
        expires_at=now + timedelta(minutes=settings.LAB_DURATION_MINUTES),
    )
    lab.set_target_password(target_password)
    # lab_token and username default to their secure generators.
    lab.save()
    # Make the target a real account so the cracked credentials actually log in.
    ensure_victim_user(lab.username, target_password)
    return lab


def refresh_lab_status(lab: Lab) -> Lab:
    """Lazily transition a lab to EXPIRED/LOCKED when appropriate.

    Called on read paths so the displayed status is always current even without
    a background scheduler.  Persists only when the status actually changes.
    """
    if lab.status in {Lab.Status.COMPLETED, Lab.Status.EXPIRED, Lab.Status.LOCKED}:
        return lab

    new_status = None
    if lab.is_expired:
        new_status = Lab.Status.EXPIRED
    elif lab.attempt_count >= lab.max_attempts:
        new_status = Lab.Status.LOCKED

    if new_status and new_status != lab.status:
        lab.status = new_status
        lab.save(update_fields=["status"])
    return lab


@transaction.atomic
def reset_lab(lab: Lab) -> Lab:
    """Instructor action: wipe attempts and re-arm a lab with a fresh target."""
    lab.attempts.all().delete()
    wordlist = lab.wordlist if lab.wordlist.is_active else _pick_wordlist()
    target_password = _pick_target_password(wordlist)

    now = timezone.now()
    lab.wordlist = wordlist
    lab.set_target_password(target_password)
    lab.attempt_count = 0
    lab.status = Lab.Status.ACTIVE
    lab.is_active = True
    lab.completed_at = None
    lab.expires_at = now + timedelta(minutes=settings.LAB_DURATION_MINUTES)
    lab.save()
    return lab


# ---------------------------------------------------------------------------
# Primary (global) target — the single account behind the tokenless
# /api/login/ endpoint that every student attacks.
# ---------------------------------------------------------------------------
def get_primary_lab():
    """Return the current global target lab, or None if none is set."""
    return Lab.objects.filter(is_primary=True).select_related("wordlist").first()


@transaction.atomic
def set_primary_lab(lab: Lab) -> Lab:
    """Make ``lab`` the one-and-only primary target."""
    Lab.objects.filter(is_primary=True).exclude(pk=lab.pk).update(is_primary=False)
    if not lab.is_primary:
        lab.is_primary = True
        lab.save(update_fields=["is_primary"])
    return lab


def get_or_create_primary_lab() -> Lab:
    """Return the global target, creating a default one on first use."""
    lab = get_primary_lab()
    if lab is not None:
        return lab
    from django.contrib.auth import get_user_model

    User = get_user_model()
    host, created = User.objects.get_or_create(username="lab_host")
    if created:
        host.set_unusable_password()
        host.save()
    lab = create_lab_for_student(host)
    return set_primary_lab(lab)
