"""
Attempt model — an immutable log row for every training login attempt.

Every POST to the training endpoint creates exactly one ``Attempt`` inside the
same database transaction that increments the lab's counter, so the log and the
counter can never drift apart.

Password visibility policy:

* ``password_attempted`` stores the raw candidate value.  This is TRAINING
  data submitted by the student against their OWN isolated lab — it is not a
  real credential.  It is retained so the request flow can be demonstrated.
* The API/serializers mask it by default and only reveal the full value inside
  the student's own lab when ``SHOW_FULL_CANDIDATE_PASSWORDS`` is enabled.  It
  is never exposed across labs.
"""

from django.db import models


class Attempt(models.Model):
    """One recorded authentication attempt against a lab."""

    lab = models.ForeignKey(
        "labs.Lab", on_delete=models.CASCADE, related_name="attempts"
    )
    username_attempted = models.CharField(max_length=150)
    password_attempted = models.CharField(max_length=256)
    success = models.BooleanField(default=False)
    # 1-based ordinal within the lab (matches the lab's attempt_count).
    attempt_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ["lab", "attempt_number"]
        indexes = [
            models.Index(fields=["lab", "attempt_number"]),
            models.Index(fields=["lab", "success"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            # Attempt numbers are unique within a lab.
            models.UniqueConstraint(
                fields=["lab", "attempt_number"], name="unique_attempt_number_per_lab"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        result = "success" if self.success else "fail"
        return f"Lab {self.lab_id} #{self.attempt_number} ({result})"

    @staticmethod
    def mask_password(value: str) -> str:
        """Return a masked form like ``p*******`` for dashboards."""
        if not value:
            return ""
        first = value[0]
        return first + ("*" * max(len(value) - 1, 1))
