"""
Serializers for the lab API.

None of these ever expose the target password (only its hash exists, and even
that is excluded here).  The lab URL and username ARE exposed to the owning
student because they need them to run their script.
"""

from django.urls import reverse
from rest_framework import serializers

from .models import Lab, Wordlist


class WordlistSerializer(serializers.ModelSerializer):
    """The wordlist assigned to a lab (safe to show the owning student)."""

    size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Wordlist
        fields = ["name", "description", "difficulty", "passwords", "size"]
        read_only_fields = fields


class LabSerializer(serializers.ModelSerializer):
    """Safe representation of a lab for its owner.

    Deliberately excludes ``target_password_hash``.  ``lab_token`` is read-only
    so a student can never repoint a lab at someone else's data.
    """

    wordlist_name = serializers.CharField(source="wordlist.name", read_only=True)
    difficulty = serializers.CharField(
        source="wordlist.difficulty", read_only=True
    )
    attempts_remaining = serializers.IntegerField(read_only=True)
    login_url = serializers.SerializerMethodField()
    successful_attempts = serializers.SerializerMethodField()
    latest_attempt = serializers.SerializerMethodField()

    class Meta:
        model = Lab
        fields = [
            "lab_token",
            "username",
            "status",
            "wordlist_name",
            "difficulty",
            "max_attempts",
            "attempt_count",
            "attempts_remaining",
            "successful_attempts",
            "latest_attempt",
            "started_at",
            "completed_at",
            "expires_at",
            "is_active",
            "login_url",
        ]
        read_only_fields = fields

    def get_login_url(self, obj: Lab) -> str:
        """The training endpoint path this lab's script must POST to."""
        request = self.context.get("request")
        path = reverse("labs_api:lab-login", kwargs={"lab_token": obj.lab_token})
        if request is not None:
            return request.build_absolute_uri(path)
        return path

    def get_successful_attempts(self, obj: Lab) -> int:
        # 0 or 1 in practice, since the lab completes on first success.
        return obj.attempts.filter(success=True).count()

    def get_latest_attempt(self, obj: Lab):
        latest = obj.attempts.order_by("-attempt_number").first()
        if latest is None:
            return None
        from apps.attempts.serializers import _display_password

        return {
            "attempt_number": latest.attempt_number,
            "password": _display_password(latest),
            "success": latest.success,
            "created_at": latest.created_at.isoformat(),
        }


class LabStartSerializer(serializers.Serializer):
    """Input for starting a new lab. Difficulty is optional and validated."""

    difficulty = serializers.ChoiceField(
        choices=Wordlist.Difficulty.choices, required=False, allow_null=True
    )


class TrainingLoginSerializer(serializers.Serializer):
    """Input for the training authentication endpoint."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)
