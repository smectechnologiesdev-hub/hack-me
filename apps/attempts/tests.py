"""
Concurrency and attempt-model tests.

The concurrency test fires many simultaneous login requests at a single lab and
asserts that ``max_attempts`` is never breached — i.e. a student cannot bypass
the limit by sending requests in parallel.

Note on backends: true row-level locking (``select_for_update``) is enforced by
PostgreSQL/MySQL.  SQLite serialises writers instead, which still yields the
correct capped result, so this test is meaningful on every supported backend.
"""

import threading

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from apps.attempts.models import Attempt
from apps.attempts.services import process_login_attempt
from apps.labs.models import Lab, Wordlist
from apps.labs.services import create_lab_for_student

User = get_user_model()


class MaskingTests(TransactionTestCase):
    def test_mask_password(self):
        self.assertEqual(Attempt.mask_password("python123"), "p********")
        self.assertEqual(Attempt.mask_password("a"), "a*")
        self.assertEqual(Attempt.mask_password(""), "")


class ConcurrentAttemptTests(TransactionTestCase):
    # TransactionTestCase (not TestCase) so real commits happen and threads see
    # each other's writes.
    reset_sequences = True

    def setUp(self):
        self.wordlist = Wordlist.objects.create(
            name="Concurrency List",
            passwords=["target-not-guessed"],
            difficulty=Wordlist.Difficulty.EASY,
            is_active=True,
        )
        self.student = User.objects.create_user("frank", password="pw-frank-123")
        self.lab = create_lab_for_student(self.student)
        self.lab.max_attempts = 10
        self.lab.save(update_fields=["max_attempts"])

    def test_parallel_requests_do_not_exceed_max(self):
        errors = []

        def worker(i):
            try:
                process_login_attempt(
                    lab_token=self.lab.lab_token,
                    username=self.lab.username,
                    password=f"candidate-{i}",
                )
            except Exception as exc:  # pragma: no cover - surfaced via assert
                errors.append(exc)
            finally:
                # Close the thread's DB connection cleanly.
                from django.db import connection

                connection.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"worker errors: {errors}")

        self.lab.refresh_from_db()
        # The counter must never exceed the maximum.
        self.assertLessEqual(self.lab.attempt_count, self.lab.max_attempts)
        # And the number of *recorded* attempts equals the counter — no
        # double-counting and no lost updates.
        self.assertEqual(
            Attempt.objects.filter(lab=self.lab).count(), self.lab.attempt_count
        )
        # Attempt numbers are a contiguous 1..N with no duplicates
        # (enforced by the unique constraint, verified here explicitly).
        numbers = sorted(
            Attempt.objects.filter(lab=self.lab).values_list(
                "attempt_number", flat=True
            )
        )
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        self.assertEqual(self.lab.status, Lab.Status.LOCKED)
