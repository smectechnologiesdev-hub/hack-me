"""
Custom user model.

We swap in a custom ``User`` from day one (Django strongly recommends this)
so we can attach a ``role`` field distinguishing students from instructors
without a second table lookup.  Instructor privileges are ALSO gated on
``is_staff`` for Django admin, so ``role`` is an application-level convenience
that must never be the *only* gate on sensitive actions.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Platform user — either a Student or an Instructor."""

    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        INSTRUCTOR = "INSTRUCTOR", "Instructor"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Application role. Instructor actions also require is_staff.",
    )
    # Contact phone collected at registration (used to reach operators, e.g. a
    # prize winner). Not a credential; auth is by username.
    phone = models.CharField("phone number", max_length=20, blank=True)

    @property
    def is_instructor(self) -> bool:
        """True for users who may view aggregate/instructor data.

        Requires BOTH the instructor role and staff status so that flipping a
        single field can never silently escalate a student.
        """
        return self.role == self.Role.INSTRUCTOR and self.is_staff

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.get_username()
