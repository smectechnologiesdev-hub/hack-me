"""Account/role tests."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import OtpChallenge

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


class OtpLoginTests(TestCase):
    """The 'Sign in with OTP' flow: request a hidden code, then brute-force it.

    The code is keyed by username (not the session), so verification is stateless:
    the caller just posts ``{username, otp}`` — no cookie needed.
    """

    def setUp(self):
        self.user = User.objects.create_user("otp.user", password="whatever-123")
        self.staff = User.objects.create_user(
            "boss", password="pw", is_staff=True, role=User.Role.INSTRUCTOR
        )

    def _request_code(self, username="otp.user"):
        return self.client.post(
            "/login/otp/request/", {"username": username}, HTTP_ACCEPT="*/*"
        )

    def _stored_code(self, username="otp.user"):
        return OtpChallenge.objects.get(username=username).code

    # --- request step -------------------------------------------------------
    def test_request_mints_hidden_code(self):
        resp = self._request_code()
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        code = self._stored_code()
        self.assertRegex(code, r"^\d{4}$")
        # The code must NEVER appear in the response body.
        self.assertNotIn(code, resp.content.decode())

    def test_request_does_not_leak_unknown_username(self):
        resp = self._request_code(username="ghost")
        self.assertEqual(resp.status_code, 200)          # same generic answer
        self.assertTrue(resp.json()["success"])
        self.assertFalse(OtpChallenge.objects.filter(username="ghost").exists())

    def test_request_refuses_staff_account(self):
        self._request_code(username="boss")
        self.assertFalse(OtpChallenge.objects.filter(username="boss").exists())

    # --- verify step (stateless: post {username, otp}) ----------------------
    def test_verify_correct_code_logs_in(self):
        self._request_code()
        code = self._stored_code()
        resp = self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_verify_wrong_code_is_401(self):
        self._request_code()
        good = self._stored_code()
        bad = "0000" if good != "0000" else "1111"
        resp = self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": bad},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.json()["success"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_verify_without_request_is_401(self):
        resp = self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": "1234"},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 401)

    def test_stateless_verify_needs_no_session_cookie(self):
        # Mint a code with one client, verify with a brand-new client (no shared
        # cookies) — proves the code is bound to the username, not the session.
        from django.test import Client

        self._request_code()
        code = self._stored_code()
        fresh = Client()
        resp = fresh.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["success"])

    def test_code_is_single_use(self):
        self._request_code()
        code = self._stored_code()
        self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertFalse(OtpChallenge.objects.filter(username="otp.user").exists())
        self.client.logout()
        resp = self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 401)

    def test_expired_code_is_rejected(self):
        from datetime import timedelta

        from django.utils import timezone

        self._request_code()
        code = self._stored_code()
        # Backdate beyond the TTL via .update() so auto_now doesn't reset it.
        OtpChallenge.objects.filter(username="otp.user").update(
            issued_at=timezone.now() - timedelta(seconds=6000)
        )
        resp = self.client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(resp.status_code, 401)

    def test_otp_endpoints_are_csrf_exempt(self):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        r1 = csrf_client.post(
            "/login/otp/request/", {"username": "otp.user"}, HTTP_ACCEPT="*/*"
        )
        self.assertEqual(r1.status_code, 200)
        code = self._stored_code()
        r2 = csrf_client.post(
            "/login/otp/verify/",
            {"username": "otp.user", "otp": code},
            HTTP_ACCEPT="*/*",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["success"])
