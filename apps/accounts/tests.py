"""Account/role tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegistrationTests(TestCase):
    def test_registration_creates_student(self):
        resp = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newstudent",
                "email": "s@example.com",
                "password1": "a-strong-pass-9x",
                "password2": "a-strong-pass-9x",
            },
        )
        self.assertEqual(resp.status_code, 302)  # redirect to dashboard
        user = User.objects.get(username="newstudent")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_instructor)

    def test_registration_cannot_grant_staff(self):
        # Even if a malicious client posts is_staff, the form ignores it.
        self.client.post(
            reverse("accounts:register"),
            {
                "username": "sneaky",
                "email": "x@example.com",
                "password1": "a-strong-pass-9x",
                "password2": "a-strong-pass-9x",
                "is_staff": "true",
                "role": "INSTRUCTOR",
            },
        )
        user = User.objects.get(username="sneaky")
        self.assertFalse(user.is_staff)
        self.assertEqual(user.role, User.Role.STUDENT)


class InstructorAccessTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("stud", password="pw-stud-123")
        self.instructor = User.objects.create_user(
            "prof", password="pw-prof-123", role=User.Role.INSTRUCTOR, is_staff=True
        )

    def test_student_cannot_open_instructor_dashboard(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse("instructor:dashboard"))
        self.assertEqual(resp.status_code, 403)

    def test_instructor_can_open_dashboard(self):
        self.client.force_login(self.instructor)
        resp = self.client.get(reverse("instructor:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_is_instructor_requires_both_role_and_staff(self):
        # role alone is not enough.
        u = User.objects.create_user(
            "halfprof", password="pw-1", role=User.Role.INSTRUCTOR, is_staff=False
        )
        self.assertFalse(u.is_instructor)
