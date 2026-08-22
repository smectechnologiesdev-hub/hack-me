"""
Tests for lab creation, the training login flow, isolation and limits.

Run with:
    python manage.py test
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.attempts.models import Attempt
from apps.attempts.services import Outcome, process_login_attempt
from apps.labs.models import Lab, Wordlist
from apps.labs.services import create_lab_for_student

User = get_user_model()


def make_wordlist(name="Test List", passwords=None):
    return Wordlist.objects.create(
        name=name,
        difficulty=Wordlist.Difficulty.EASY,
        passwords=passwords or ["password", "123456", "python123", "letmein"],
        is_active=True,
    )


class LabCreationTests(TestCase):
    def setUp(self):
        self.wordlist = make_wordlist()
        self.student = User.objects.create_user("alice", password="pw-alice-123")

    def test_create_lab_sets_secure_fields(self):
        lab = create_lab_for_student(self.student)
        self.assertEqual(lab.student, self.student)
        self.assertEqual(lab.status, Lab.Status.ACTIVE)
        # Token and username are generated and non-empty.
        self.assertTrue(lab.lab_token)
        self.assertTrue(lab.username and "." in lab.username)
        # The target password is stored ONLY as a hash, never in the clear.
        self.assertTrue(lab.target_password_hash)
        self.assertNotIn(lab.target_password_hash, self.wordlist.passwords)
        # Expiry is in the future.
        self.assertGreater(lab.expires_at, timezone.now())

    def test_target_password_is_from_wordlist(self):
        lab = create_lab_for_student(self.student)
        # Exactly one wordlist password verifies against the stored hash.
        matches = [p for p in self.wordlist.passwords if lab.check_target_password(p)]
        self.assertEqual(len(matches), 1)


class LoginFlowTests(TestCase):
    def setUp(self):
        # A single-password wordlist makes the "correct" value deterministic.
        self.wordlist = make_wordlist(passwords=["onlypass"])
        self.student = User.objects.create_user("bob", password="pw-bob-123")
        self.lab = create_lab_for_student(self.student)

    def test_wrong_password_records_failed_attempt(self):
        result = process_login_attempt(
            lab_token=self.lab.lab_token,
            username=self.lab.username,
            password="wrong",
        )
        self.assertEqual(result.outcome, Outcome.FAILED)
        self.assertFalse(result.success)
        self.assertEqual(result.attempt_number, 1)
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.attempt_count, 1)
        self.assertEqual(self.lab.status, Lab.Status.ACTIVE)

    def test_correct_password_completes_lab(self):
        result = process_login_attempt(
            lab_token=self.lab.lab_token,
            username=self.lab.username,
            password="onlypass",
        )
        self.assertTrue(result.success)
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.status, Lab.Status.COMPLETED)
        self.assertIsNotNone(self.lab.completed_at)

    def test_attempts_are_numbered_sequentially(self):
        for i in range(3):
            process_login_attempt(
                lab_token=self.lab.lab_token,
                username=self.lab.username,
                password=f"guess{i}",
            )
        numbers = list(
            Attempt.objects.filter(lab=self.lab)
            .order_by("attempt_number")
            .values_list("attempt_number", flat=True)
        )
        self.assertEqual(numbers, [1, 2, 3])

    def test_completed_lab_rejects_further_attempts(self):
        process_login_attempt(
            lab_token=self.lab.lab_token,
            username=self.lab.username,
            password="onlypass",
        )
        result = process_login_attempt(
            lab_token=self.lab.lab_token,
            username=self.lab.username,
            password="onlypass",
        )
        self.assertEqual(result.outcome, Outcome.ALREADY_COMPLETED)


class MaxAttemptsTests(TestCase):
    def setUp(self):
        self.wordlist = make_wordlist(passwords=["neverguessed"])
        self.student = User.objects.create_user("carol", password="pw-carol-123")
        self.lab = create_lab_for_student(self.student)
        # Shrink the limit for a fast test.
        self.lab.max_attempts = 3
        self.lab.save(update_fields=["max_attempts"])

    def test_attempt_count_never_exceeds_max(self):
        outcomes = []
        for i in range(6):
            r = process_login_attempt(
                lab_token=self.lab.lab_token,
                username=self.lab.username,
                password=f"x{i}",
            )
            outcomes.append(r.outcome)
        self.lab.refresh_from_db()
        # Counter is capped at the maximum.
        self.assertEqual(self.lab.attempt_count, 3)
        self.assertEqual(self.lab.status, Lab.Status.LOCKED)
        # The 4th+ calls were blocked as LIMIT_REACHED.
        self.assertEqual(outcomes[3:], [Outcome.LIMIT_REACHED] * 3)
        # And only 3 attempts were ever recorded.
        self.assertEqual(Attempt.objects.filter(lab=self.lab).count(), 3)


class ExpiryTests(TestCase):
    def setUp(self):
        self.wordlist = make_wordlist(passwords=["p"])
        self.student = User.objects.create_user("dave", password="pw-dave-123")
        self.lab = create_lab_for_student(self.student)

    def test_expired_lab_is_rejected(self):
        self.lab.expires_at = timezone.now() - timezone.timedelta(minutes=1)
        self.lab.save(update_fields=["expires_at"])
        result = process_login_attempt(
            lab_token=self.lab.lab_token,
            username=self.lab.username,
            password="p",
        )
        self.assertEqual(result.outcome, Outcome.EXPIRED)
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.status, Lab.Status.EXPIRED)


class IsolationTests(TestCase):
    """A student must never reach another student's lab through the API."""

    def setUp(self):
        self.wordlist = make_wordlist(passwords=["secret1"])
        self.alice = User.objects.create_user("alice2", password="pw-alice-123")
        self.mallory = User.objects.create_user("mallory", password="pw-mallory-1")
        self.alice_lab = create_lab_for_student(self.alice)

    def test_other_student_gets_404_on_detail(self):
        client = APIClient()
        client.force_authenticate(self.mallory)
        url = reverse("labs_api:lab-detail", kwargs={"lab_token": self.alice_lab.lab_token})
        self.assertEqual(client.get(url).status_code, 404)

    def test_other_student_cannot_read_attempts(self):
        client = APIClient()
        client.force_authenticate(self.mallory)
        url = reverse("labs_api:lab-attempts", kwargs={"lab_token": self.alice_lab.lab_token})
        self.assertEqual(client.get(url).status_code, 404)

    def test_owner_can_access_own_lab(self):
        client = APIClient()
        client.force_authenticate(self.alice)
        url = reverse("labs_api:lab-detail", kwargs={"lab_token": self.alice_lab.lab_token})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        # The response never leaks the target password hash.
        self.assertNotIn("target_password", resp.json())
        self.assertNotIn("target_password_hash", resp.json())


class TokenOnlyLoginTests(TestCase):
    """The login endpoint is authorized by the secret lab token (a capability),
    so a standalone script needs no platform login."""

    def setUp(self):
        self.wordlist = make_wordlist(passwords=["onlypass"])
        self.student = User.objects.create_user("grace", password="pw-grace-123")
        self.lab = create_lab_for_student(self.student)

    def test_unknown_token_returns_404(self):
        client = APIClient()  # anonymous
        url = reverse("labs_api:lab-login", kwargs={"lab_token": "no-such-token"})
        resp = client.post(url, {"username": "x", "password": "y"}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_anonymous_script_can_attempt_with_valid_token(self):
        # No login/session at all — just the token in the URL.
        client = APIClient()
        url = reverse("labs_api:lab-login", kwargs={"lab_token": self.lab.lab_token})
        fail = client.post(
            url, {"username": self.lab.username, "password": "nope"}, format="json"
        )
        self.assertEqual(fail.status_code, 401)
        success = client.post(
            url, {"username": self.lab.username, "password": "onlypass"}, format="json"
        )
        self.assertEqual(success.status_code, 200)
        self.assertTrue(success.json()["success"])
        # The attempts were logged to this lab.
        self.assertEqual(Attempt.objects.filter(lab=self.lab).count(), 2)


class WordlistDownloadTests(TestCase):
    def setUp(self):
        self.wordlist = make_wordlist(passwords=["alpha", "beta", "gamma"])
        self.owner = User.objects.create_user("heidi", password="pw-heidi-123")
        self.other = User.objects.create_user("ivan", password="pw-ivan-1234")
        self.lab = create_lab_for_student(self.owner)

    def test_owner_downloads_txt_file(self):
        self.client.force_login(self.owner)
        url = reverse("labs:wordlist-download", kwargs={"lab_token": self.lab.lab_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/plain; charset=utf-8")
        self.assertIn("attachment", resp["Content-Disposition"])
        body = resp.content.decode()
        # One password per line.
        self.assertEqual(body.strip().splitlines(), ["alpha", "beta", "gamma"])

    def test_other_student_cannot_download(self):
        self.client.force_login(self.other)
        url = reverse("labs:wordlist-download", kwargs={"lab_token": self.lab.lab_token})
        self.assertEqual(self.client.get(url).status_code, 404)


class ApiLoginEndpointTests(TestCase):
    def setUp(self):
        self.wordlist = make_wordlist(passwords=["onlypass"])
        self.student = User.objects.create_user("erin", password="pw-erin-123")
        self.lab = create_lab_for_student(self.student)
        self.client = APIClient()
        self.client.force_authenticate(self.student)
        self.url = reverse("labs_api:lab-login", kwargs={"lab_token": self.lab.lab_token})

    def test_failed_login_returns_401(self):
        resp = self.client.post(
            self.url, {"username": self.lab.username, "password": "nope"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)
        body = resp.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["attempt_number"], 1)

    def test_successful_login_returns_200(self):
        resp = self.client.post(
            self.url,
            {"username": self.lab.username, "password": "onlypass"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status"], Lab.Status.COMPLETED)

    def test_start_lab_endpoint_creates_lab(self):
        url = reverse("labs_api:lab-start")
        resp = self.client.post(url, {}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("lab_token", resp.json())
        self.assertIn("login_url", resp.json())
