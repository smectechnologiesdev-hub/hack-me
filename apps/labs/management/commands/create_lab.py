"""
Management command: create a lab with an instructor-chosen target.

Handy when YOU want to define exactly what students brute-force — a specific
target username and password — rather than letting the server pick a random
password from the wordlist.

Examples
--------
# A ready-to-share challenge (no student account needed):
    python manage.py create_lab --username admin --password hello123

# Assign it to a specific existing student account:
    python manage.py create_lab --student alice --username admin --password hello123

If the chosen --password is not already in the assigned wordlist, it is added
to that wordlist so students can actually find it by brute force.

The command prints a public challenge link.  Share that link with students —
they need no login: they just download the password list and run their script.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.labs.models import Lab, Wordlist
from apps.labs.services import (
    _pick_target_password,
    _pick_wordlist,
    ensure_victim_user,
    set_primary_lab,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Set the global target account for the /api/login/ endpoint."

    def add_arguments(self, parser):
        parser.add_argument("--student", help="Owner account username (default: a shared 'lab_host' account).")
        parser.add_argument("--username", help="Target account username (default: auto-generated).")
        parser.add_argument("--password", help="Target password (default: random from wordlist).")
        parser.add_argument("--wordlist", help="Wordlist name to assign (default: any active).")
        parser.add_argument("--max-attempts", type=int, default=settings.LAB_MAX_ATTEMPTS)
        parser.add_argument("--minutes", type=int, default=settings.LAB_DURATION_MINUTES)

    def handle(self, *args, **opts):
        if opts.get("student"):
            try:
                student = User.objects.get(username=opts["student"])
            except User.DoesNotExist:
                raise CommandError(
                    f"No user named '{opts['student']}'. Create the account first."
                )
        else:
            # No owner given: use a shared, login-less host account so a
            # challenge can exist without any student registering.
            student, created = User.objects.get_or_create(username="lab_host")
            if created:
                student.set_unusable_password()
                student.save()

        # Pick the wordlist (by name if given, else any active one).
        if opts.get("wordlist"):
            try:
                wordlist = Wordlist.objects.get(name=opts["wordlist"], is_active=True)
            except Wordlist.DoesNotExist:
                raise CommandError(f"No active wordlist named '{opts['wordlist']}'.")
        else:
            wordlist = _pick_wordlist()

        # Determine the target password.
        target_password = opts.get("password")
        if target_password:
            # Ensure it is in the wordlist so it can actually be found.
            passwords = list(wordlist.passwords or [])
            if target_password not in passwords:
                passwords.append(target_password)
                wordlist.passwords = passwords
                wordlist.save(update_fields=["passwords"])
                self.stdout.write(
                    self.style.WARNING(
                        f"Added '{target_password}' to wordlist '{wordlist.name}' "
                        "so students can find it."
                    )
                )
        else:
            target_password = _pick_target_password(wordlist)

        now = timezone.now()
        lab = Lab(
            student=student,
            wordlist=wordlist,
            status=Lab.Status.ACTIVE,
            max_attempts=opts["max_attempts"],
            expires_at=now + timedelta(minutes=opts["minutes"]),
        )
        if opts.get("username"):
            lab.username = opts["username"]
        lab.set_target_password(target_password)
        lab.save()

        # Make this the single global target behind /api/login/.
        set_primary_lab(lab)
        # Make the target a real, loginable account (cracked creds -> /login/).
        ensure_victim_user(lab.username, target_password)

        self.stdout.write(self.style.SUCCESS("Global target set."))
        self.stdout.write(f"  username:  {lab.username}   (the account students attack)")
        self.stdout.write(f"  wordlist:  {wordlist.name} ({wordlist.size} passwords)")
        self.stdout.write(
            f"  This account is a REAL login: once cracked, sign in at /login/ as {lab.username}."
        )
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Students attack these fixed endpoints (no token, no login):"))
        self.stdout.write(self.style.SUCCESS("    GET  /api/target/        -> the target username"))
        self.stdout.write(self.style.SUCCESS("    GET  /api/wordlist.txt   -> the password list"))
        self.stdout.write(self.style.SUCCESS("    POST /api/login/         -> {username, password}"))
        if opts.get("password"):
            self.stdout.write("")
            self.stdout.write(
                self.style.HTTP_INFO(f"  target pw: {target_password}   (for YOUR reference only)")
            )
