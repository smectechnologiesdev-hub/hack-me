"""
Challenge service layer: the vulnerable portal auth, milestone tracking,
throttling, and scoreboard data.
"""

import hashlib
import time

from django.core.cache import cache
from django.db import connection
from django.utils import timezone

from .models import VaultClient


# ---------------------------------------------------------------------------
# The deliberately-vulnerable portal authentication
# ---------------------------------------------------------------------------
def portal_authenticate(username: str, password: str) -> VaultClient | None:
    """Verify portal credentials with a **raw, injectable** SQL query.

    This is the CTF target.  The query is intentionally built by string
    interpolation, so it is vulnerable to:

    * **Brute-force** — submit candidate passwords until one matches (the
      target passwords come from a real wordlist, e.g. rockyou).
    * **SQL injection auth-bypass** — e.g. a username of ``victim' --`` comments
      out the password check and returns that client regardless of password.

    It is an **auth-bypass oracle only**: it reflects NO row data back to the
    caller (only success/failure), so it cannot be turned into a UNION-based
    data-dump.  That keeps injection to the intended "get in" lesson.

    Returns the matched :class:`VaultClient`, or ``None``.
    """
    table = VaultClient._meta.db_table
    # NOTE: intentionally vulnerable. Do NOT parameterise — the injection is the
    # exercise. Contained to this one throwaway target table.
    sql = (
        f"SELECT id FROM {table} "  # noqa: S608 - intentionally injectable target
        f"WHERE username = '{username}' AND password = '{password}'"
    )
    with connection.cursor() as cursor:
        try:
            cursor.execute(sql)
            row = cursor.fetchone()
        except Exception:
            # A broken injection payload just fails to authenticate.
            return None
    if not row:
        return None
    # Only ever treat the first column as a real client id. A UNION-based
    # payload that smuggles a string here authenticates nobody (and cannot
    # crash the view) — keeping this an auth-bypass oracle, not a data leak.
    try:
        client_id = int(row[0])
    except (TypeError, ValueError):
        return None
    return VaultClient.objects.filter(id=client_id).first()


def sha1_hex(value: str) -> str:
    """A fast one-way hash, leaked in the data export (crackable offline)."""
    return hashlib.sha1(value.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Milestone tracking (drives points + the live scoreboard)
# ---------------------------------------------------------------------------
def record_milestone(client: VaultClient, field: str) -> None:
    """Stamp a milestone the first time it happens, then refresh the scoreboard."""
    if getattr(client, field) is None:
        setattr(client, field, timezone.now())
        client.save(update_fields=[field])
        broadcast_scoreboard()


# ---------------------------------------------------------------------------
# Lightweight per-IP throttle (protects the shared box; the portal login is a
# plain Django view, so DRF's throttling does not apply to it).
# ---------------------------------------------------------------------------
def rate_ok(ip: str, scope: str = "portal_login", limit: int = 1200, window: int = 60) -> bool:
    """Fixed-window per-IP limiter.  Generous enough for a rockyou run; finite
    enough that one IP cannot flood the server.  Returns False when over limit.
    """
    bucket = int(time.time() // window)
    key = f"rl:{scope}:{ip}:{bucket}"
    try:
        count = cache.get(key, 0) + 1
        cache.set(key, count, window)
    except Exception:
        # If the cache is unavailable, fail open rather than lock everyone out.
        return True
    return count <= limit


def client_ip(request) -> str:
    """Best-effort client IP (honours a single Nginx proxy hop)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------
def scoreboard_rows() -> list[dict]:
    """Ranked rows for assigned participants: most points first, earliest solve wins ties."""
    rows = []
    qs = VaultClient.objects.filter(assigned_to__isnull=False).select_related("assigned_to")
    for c in qs:
        rows.append(
            {
                "handle": c.assigned_to.get_username(),
                "points": c.points,
                "stages_done": c.stages_done,
                "total_stages": len(c.POINTS),
                "solved": c.is_solved,
                "solved_at": c.captured_flag_at,
                "stage_flags": {field: getattr(c, field) is not None for field in c.POINTS},
            }
        )
    # Most points first; among ties, an earlier solve beats a later/none.
    rows.sort(key=lambda r: (-r["points"], r["solved_at"] is None, r["solved_at"] or ""))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def broadcast_scoreboard() -> None:
    """Push a 'scoreboard changed' nudge to any live viewers over the Channels layer.

    Best-effort: if Channels isn't configured (e.g. some unit tests), this is a
    no-op and the scoreboard page still works via its polling fallback.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is None:
            return
        async_to_sync(layer.group_send)(
            "scoreboard", {"type": "scoreboard.update"}
        )
    except Exception:
        return
