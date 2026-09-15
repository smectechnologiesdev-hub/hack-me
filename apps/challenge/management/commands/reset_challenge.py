"""
Reset the Vaultline Heist for a fresh event.

Wipes every target (and, with ``--wipe-students``, every student account and
their progress), then re-provisions fresh targets from the SAME wordlist that
``/passwords.txt`` serves — so every target password is guaranteed crackable
from the list students download.

Fresh-event reset (500 targets, students re-register to get assigned):

    python manage.py reset_challenge --count 500 --wipe-students --yes

Keeps staff / instructor / superuser accounts. Targets are left UNASSIGNED;
each student is auto-assigned one when they register (or run with ``--assign``).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.challenge.models import VaultClient

DEFAULT_WORDLIST = str(settings.BASE_DIR / "tools" / "wordlist.txt")


class Command(BaseCommand):
    help = "Wipe and re-provision the challenge for a fresh event."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=500, help="Fresh targets to create (default 500).")
        parser.add_argument("--wordlist", type=str, default=DEFAULT_WORDLIST,
                            help="Wordlist to draw passwords from (default: the bundled tools/wordlist.txt served at /passwords.txt).")
        parser.add_argument("--min-rank", type=int, default=20, help="Skip the first N lines of the wordlist.")
        parser.add_argument("--max-rank", type=int, default=1400, help="Only draw passwords from before this line.")
        parser.add_argument("--wipe-students", action="store_true",
                            help="Also delete all student accounts (keeps staff/instructors/superusers).")
        parser.add_argument("--assign", action="store_true", help="Assign the fresh targets to any existing students now.")
        parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")

    def handle(self, *args, **opts):
        User = get_user_model()
        n_targets = VaultClient.objects.count()
        n_students = User.objects.filter(is_staff=False, is_superuser=False).count()

        plan = [f"delete ALL {n_targets} target(s) + their progress",
                f"create {opts['count']} fresh target(s) from {opts['wordlist']}"]
        if opts["wipe_students"]:
            plan.insert(1, f"delete ALL {n_students} student account(s) (staff kept)")

        self.stdout.write(self.style.WARNING("This will:"))
        for step in plan:
            self.stdout.write(f"  - {step}")

        if not opts["yes"]:
            confirm = input("Type 'yes' to proceed: ").strip().lower()
            if confirm != "yes":
                self.stdout.write("Aborted.")
                return

        # 1. Wipe targets (and their progress + assignments).
        deleted, _ = VaultClient.objects.all().delete()
        self.stdout.write(f"Removed {deleted} target row(s).")

        # 2. Optionally wipe student accounts (never staff/instructors/superusers).
        if opts["wipe_students"]:
            qs = User.objects.filter(is_staff=False, is_superuser=False)
            count = qs.count()
            qs.delete()
            self.stdout.write(f"Removed {count} student account(s).")

        # 3. Re-provision fresh targets from the wordlist.
        call_command(
            "provision_challenge",
            count=opts["count"],
            wordlist=opts["wordlist"],
            min_rank=opts["min_rank"],
            max_rank=opts["max_rank"],
            assign=opts["assign"],
        )

        self.stdout.write(self.style.SUCCESS(
            f"Reset complete — {VaultClient.objects.count()} fresh target(s) ready. "
            "Students get one on registration."
        ))
