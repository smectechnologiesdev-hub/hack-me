"""
Set the target account students must crack.

The target is a REAL login account with a weak password, so that once a student
brute-forces it they can actually sign in at /login/ as that account.

Usage:
    python manage.py set_target --username m.kessler --password hello123
"""

from django.core.management.base import BaseCommand, CommandError

from apps.labs.services import ensure_victim_user


class Command(BaseCommand):
    help = "Create/update the crackable target account (a real login)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Target account username.")
        parser.add_argument("--password", required=True, help="Target account password (weak on purpose).")

    def handle(self, *args, **opts):
        username, password = opts["username"], opts["password"]
        user = ensure_victim_user(username, password)
        if user.is_staff or user.is_superuser:
            raise CommandError(
                f"'{username}' is a staff/admin account — refusing to give it a weak password."
            )
        self.stdout.write(self.style.SUCCESS("Target account ready."))
        self.stdout.write(f"  username: {username}")
        self.stdout.write(f"  password: {password}   (weak on purpose — students will crack it)")
        self.stdout.write("")
        self.stdout.write("  The ONE endpoint (browser form AND script): /login/")
        self.stdout.write("  Students crack the password, then sign in at /login/ as this account.")
