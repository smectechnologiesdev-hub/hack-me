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
                "phone": "+1 555 0100",
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
                "phone": "+1 555 0111",
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


class PortalLoginTests(TestCase):
    """The single /login/ endpoint serves the browser form AND the script."""

    def setUp(self):
        # A real, crackable target account.
        self.user = User.objects.create_user("m.kessler", password="hello123")

    def test_get_renders_login_form(self):
        resp = self.client.get("/login/")
        self.assertEqual(resp.status_code, 200)

    # --- Browser form (Accept: text/html) -----------------------------------
    def test_browser_success_redirects_to_dashboard(self):
        resp = self.client.post(
            "/login/",
            {"username": "m.kessler", "password": "hello123"},
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/dashboard/", resp["Location"])

    def test_browser_failure_rerenders_form(self):
        resp = self.client.post(
            "/login/",
            {"username": "m.kessler", "password": "wrong"},
            HTTP_ACCEPT="text/html",
        )
        self.assertEqual(resp.status_code, 200)  # form re-rendered, not redirect

    # --- Script (Accept: */*, like the requests library) --------------------
    def test_script_success_returns_json(self):
        resp = self.client.post(
            "/login/",
            {"username": "m.kessler", "password": "hello123"},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

    def test_script_failure_returns_401(self):
        resp = self.client.post(
            "/login/",
            {"username": "m.kessler", "password": "nope"},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()["success"])

    def test_endpoint_is_csrf_exempt(self):
        # A CSRF-enforcing client with no token must still be allowed.
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        resp = csrf_client.post(
            "/login/",
            {"username": "m.kessler", "password": "hello123"},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
