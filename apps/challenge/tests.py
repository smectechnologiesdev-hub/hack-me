"""Tests for the Vaultline Heist challenge chain."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import crypto
from .models import VaultClient

User = get_user_model()


def make_target(username="v.harper", password="cheese123", assigned_to=None):
    vault_id, vault_password = "VLT-1234", "onyx-5678"
    return VaultClient.objects.create(
        username=username,
        password=password,
        display_name="V Harper",
        vault_id=vault_id,
        vault_password=vault_password,
        account_key=crypto.generate_key(),
        vault_key=crypto.generate_key(),
        assigned_to=assigned_to,
    )


class PortalLoginTests(TestCase):
    def setUp(self):
        self.target = make_target()
        self.url = reverse("challenge:portal_login")

    def test_bruteforce_success(self):
        r = self.client.post(
            self.url, data=json.dumps({"username": self.target.username, "password": "cheese123"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        self.target.refresh_from_db()
        self.assertIsNotNone(self.target.cracked_login_at)

    def test_bruteforce_wrong_password(self):
        r = self.client.post(
            self.url, data=json.dumps({"username": self.target.username, "password": "nope"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 401)
        self.assertFalse(r.json()["success"])

    def test_sqli_auth_bypass(self):
        # username = victim' --  comments out the password check.
        r = self.client.post(
            self.url,
            data=json.dumps({"username": f"{self.target.username}' --", "password": "anything"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])

    def test_login_does_not_reflect_data(self):
        # Auth-bypass oracle only: a UNION-style payload must not leak rows.
        r = self.client.post(
            self.url,
            data=json.dumps({"username": "x' UNION SELECT flag FROM challenge_vaultclient --", "password": "y"}),
            content_type="application/json",
        )
        # Whatever happens, the flag must never appear in the response body.
        self.assertNotIn(self.target.flag, r.content.decode())


class ChainTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user("student1", password="x")
        self.target = make_target(assigned_to=self.student)
        # Establish a browser portal session by cracking the login.
        self.client.post(
            reverse("challenge:portal_login"),
            {"username": self.target.username, "password": "cheese123"},
            HTTP_ACCEPT="text/html",
        )

    def test_vault_gated_until_rotation(self):
        r = self.client.post(reverse("challenge:vault"), {
            "vault_id": self.target.vault_id, "vault_password": self.target.vault_password,
        })
        self.assertEqual(r.status_code, 403)

    def test_data_export_leaks_keys_and_decrypts(self):
        r = self.client.get(reverse("challenge:data_export"))
        export = r.json()
        # Account blob -> {username, password}.
        self.assertIn("account_key", export)
        acct = crypto.decrypt(export["account_blob"], export["account_key"])
        self.assertEqual(acct["username"], self.target.username)
        self.assertEqual(acct["password"], self.target.password)
        # Vault blob -> {vault_id, vault_password}, under a *different* key.
        self.assertIn("vault_key", export)
        self.assertNotEqual(export["account_key"], export["vault_key"])
        creds = crypto.decrypt(export["vault_blob"], export["vault_key"])
        self.assertEqual(creds["vault_id"], self.target.vault_id)
        self.assertEqual(creds["vault_password"], self.target.vault_password)

    def test_full_chain_scores_1000(self):
        self.client.get(reverse("challenge:data_export"))
        self.client.post(reverse("challenge:rotate_password"),
                         {"new_password": "abcd1234", "confirm_password": "abcd1234"})
        r = self.client.post(reverse("challenge:vault"), {
            "vault_id": self.target.vault_id, "vault_password": self.target.vault_password,
        })
        self.assertEqual(r.status_code, 200)
        # Grab the flag from loot and submit as the participant.
        self.client.force_login(self.student)
        r = self.client.post(reverse("challenge:flag_submit"), {"flag": self.target.flag})
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_solved)
        self.assertEqual(self.target.points, 1000)


class FlagBindingTests(TestCase):
    def test_cannot_submit_another_students_flag(self):
        alice = User.objects.create_user("alice", password="x")
        bob = User.objects.create_user("bob", password="x")
        alice_target = make_target(username="a.one", assigned_to=alice)
        bob_target = make_target(username="b.two", assigned_to=bob)

        self.client.force_login(alice)
        # Alice submits Bob's flag -> rejected, no credit.
        self.client.post(reverse("challenge:flag_submit"), {"flag": bob_target.flag})
        alice_target.refresh_from_db()
        bob_target.refresh_from_db()
        self.assertFalse(alice_target.is_solved)
        self.assertFalse(bob_target.is_solved)


class RegistrationAssignmentTests(TestCase):
    def test_registration_auto_assigns_target(self):
        spare = make_target(username="spare.one")
        self.assertIsNone(spare.assigned_to)
        self.client.post(reverse("accounts:register"), {
            "username": "newstudent", "email": "n@example.com",
            "password1": "Str0ng-Pass-99!", "password2": "Str0ng-Pass-99!",
        })
        spare.refresh_from_db()
        self.assertIsNotNone(spare.assigned_to)
        self.assertEqual(spare.assigned_to.username, "newstudent")
