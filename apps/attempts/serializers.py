"""Serialisation helpers for attempts (REST API + WebSocket events)."""

from django.conf import settings
from rest_framework import serializers

from .models import Attempt


def _display_password(attempt: Attempt) -> str:
    """Masked-or-full candidate password, per the educational display policy.

    Full values are only ever emitted for the student's own lab and only when
    the operator has explicitly opted in via SHOW_FULL_CANDIDATE_PASSWORDS.
    They are always clearly labelled as training data in the UI.
    """
    if settings.SHOW_FULL_CANDIDATE_PASSWORDS:
        return attempt.password_attempted
    return Attempt.mask_password(attempt.password_attempted)


class AttemptSerializer(serializers.ModelSerializer):
    """Read-only representation of an attempt for a student's own lab."""

    password = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = [
            "attempt_number",
            "username_attempted",
            "password",
            "success",
            "result",
            "created_at",
        ]
        read_only_fields = fields

    def get_password(self, obj: Attempt) -> str:
        return _display_password(obj)

    def get_result(self, obj: Attempt) -> str:
        return "SUCCESS" if obj.success else "FAILED"


def build_attempt_event(lab, attempt: Attempt) -> dict:
    """Build the JSON payload broadcast over WebSockets for a new attempt.

    Mirrors the event shape documented in the project spec.
    """
    return {
        "type": "attempt",
        "attempt_number": attempt.attempt_number,
        "username": attempt.username_attempted,
        "password": _display_password(attempt),
        "success": attempt.success,
        "result": "SUCCESS" if attempt.success else "FAILED",
        "timestamp": attempt.created_at.isoformat(),
        # Live lab counters so the dashboard header can update in place.
        "lab_status": lab.status,
        "attempt_count": lab.attempt_count,
        "max_attempts": lab.max_attempts,
        # On success, reveal the found password so the owner's landing page can
        # celebrate it (the student submitted it themselves — nothing leaked).
        "cracked_password": attempt.password_attempted if attempt.success else None,
    }
