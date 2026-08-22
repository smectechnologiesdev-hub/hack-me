"""
Attempt processing service — the concurrency-safe heart of the training lab.

``process_login_attempt`` is called by the training authentication endpoint for
every candidate password.  It must be safe under concurrent requests: a student
running a multi-threaded script must NOT be able to slip past ``max_attempts``
by firing many requests at once.

Concurrency strategy
--------------------
We open a DB transaction and take a ``SELECT ... FOR UPDATE`` row lock on the
lab.  All checks (expiry, active, attempt limit) and the counter increment
happen while that lock is held, so simultaneous requests are serialised on the
lab row and each one sees a consistent, up-to-date counter.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.labs.models import Lab

from .models import Attempt


# Machine-readable outcome codes the API view maps to HTTP responses.
class Outcome:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    LIMIT_REACHED = "LIMIT_REACHED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"
    ALREADY_COMPLETED = "ALREADY_COMPLETED"


@dataclass
class LoginResult:
    """Structured result returned to the API view."""

    outcome: str
    message: str
    lab: Lab
    attempt: Attempt | None = None
    attempt_number: int | None = None

    @property
    def success(self) -> bool:
        return self.outcome == Outcome.SUCCESS

    @property
    def is_terminal_block(self) -> bool:
        """True for states where no further attempts are possible."""
        return self.outcome in {
            Outcome.LIMIT_REACHED,
            Outcome.EXPIRED,
            Outcome.DISABLED,
            Outcome.ALREADY_COMPLETED,
        }


def _client_ip(request) -> str | None:
    """Best-effort client IP, honouring a single proxy hop (Nginx)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def process_login_attempt(
    *, lab_token: str, username: str, password: str, request=None, public_mode: bool = False
) -> LoginResult:
    """Validate a candidate credential against a lab and log the attempt.

    Returns a :class:`LoginResult`.  Raises ``Lab.DoesNotExist`` if the token is
    unknown (the caller turns that into a 404).

    ``public_mode`` is used by the shared, tokenless ``/api/login/`` target: it
    skips the lifecycle gates (expiry / attempt cap / completion) so the account
    stays perpetually attackable by every student, and requires the submitted
    username to match the target account exactly.
    """
    ip = _client_ip(request) if request is not None else None
    user_agent = (
        request.META.get("HTTP_USER_AGENT", "")[:512] if request is not None else ""
    )

    with transaction.atomic():
        # Row-lock the lab so concurrent attempts are serialised here.
        lab = Lab.objects.select_for_update().get(lab_token=lab_token)

        # Instructor kill-switch always applies.
        if not lab.is_active:
            return LoginResult(Outcome.DISABLED, "This account is unavailable.", lab)

        # Lifecycle gates apply to token-scoped labs only.  The shared public
        # target (public_mode) has no expiry/cap/completion — it stays open.
        if not public_mode:
            if lab.status == Lab.Status.COMPLETED:
                return LoginResult(Outcome.ALREADY_COMPLETED, "Lab already completed.", lab)
            if timezone.now() >= lab.expires_at:
                if lab.status != Lab.Status.EXPIRED:
                    lab.status = Lab.Status.EXPIRED
                    lab.save(update_fields=["status"])
                return LoginResult(Outcome.EXPIRED, "This lab has expired.", lab)
            if lab.attempt_count >= lab.max_attempts:
                if lab.status != Lab.Status.LOCKED:
                    lab.status = Lab.Status.LOCKED
                    lab.save(update_fields=["status"])
                return LoginResult(
                    Outcome.LIMIT_REACHED, "Lab attempt limit reached.", lab
                )

        # --- Record the attempt --------------------------------------------
        attempt_number = lab.attempt_count + 1
        # Plain comparison against the stored *hash* of the target password.
        # There is intentionally no password rate-limiting — brute forcing is
        # the exercise.  In public_mode the username must also match the target
        # account exactly (you must know whose account you're breaking into).
        if public_mode:
            success = username == lab.username and lab.check_target_password(password)
        else:
            success = bool(username) and lab.check_target_password(password)

        attempt = Attempt.objects.create(
            lab=lab,
            username_attempted=username[:150],
            password_attempted=password[:256],
            success=success,
            attempt_number=attempt_number,
            ip_address=ip,
            user_agent=user_agent,
        )

        lab.attempt_count = attempt_number
        update_fields = ["attempt_count"]

        if success and not public_mode:
            lab.status = Lab.Status.COMPLETED
            lab.completed_at = timezone.now()
            update_fields += ["status", "completed_at"]
        elif not public_mode and lab.attempt_count >= lab.max_attempts:
            # This attempt used the final slot -> lock the lab.
            lab.status = Lab.Status.LOCKED
            update_fields += ["status"]
        elif lab.status == Lab.Status.CREATED:
            lab.status = Lab.Status.ACTIVE
            update_fields += ["status"]

        lab.save(update_fields=update_fields)

        # Broadcast AFTER the transaction commits so the dashboard never sees an
        # attempt that later rolled back.
        transaction.on_commit(lambda: _broadcast_attempt(lab, attempt))

    outcome = Outcome.SUCCESS if success else Outcome.FAILED
    message = "Authentication successful" if success else "Invalid credentials"
    return LoginResult(
        outcome=outcome,
        message=message,
        lab=lab,
        attempt=attempt,
        attempt_number=attempt_number,
    )


def _broadcast_attempt(lab: Lab, attempt: Attempt) -> None:
    """Push a new-attempt event to the lab's private WebSocket group."""
    # Imported lazily to avoid import cycles and to keep this module importable
    # in contexts without Channels configured (e.g. some unit tests).
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    from .serializers import build_attempt_event

    channel_layer = get_channel_layer()
    if channel_layer is None:  # pragma: no cover - defensive
        return

    group_name = lab_group_name(lab.lab_token)
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "lab.attempt",  # -> LabConsumer.lab_attempt
            "event": build_attempt_event(lab, attempt),
        },
    )


def lab_group_name(lab_token: str) -> str:
    """Return the Channels group name for a lab (one private group per lab)."""
    return f"lab_{lab_token}"
