"""
Provision Vaultline Heist target accounts.

Each target is a self-contained ``VaultClient``: a portal username + a wordlist
password (the brute-force answer), two AES-256 recovery keys (one for the
account creds, one for the vault creds — the data export encrypts under these),
and a unique capture flag.

Typical event setup (point it at the SAME rockyou students will use, so every
target password is guaranteed to be crackable from that list):

    python manage.py provision_challenge --count 30 --wordlist /usr/share/wordlists/rockyou.txt

Without ``--wordlist`` it falls back to a small curated list of well-known
leaked passwords (fine for testing, but tell students which list to use).
"""

import random
import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.challenge import crypto
from apps.challenge.models import VaultClient

# Bank-style username parts (kept apart from the target passwords). The pool is
# sized so hundreds of UNIQUE first.last usernames generate without collisions
# (26 x 70 = 1820 combinations — comfortably above a 500-target event).
_FIRST = list("abcdefghijklmnopqrstuvwxyz")
_LAST = [
    "reynolds", "kessler", "harper", "donovan", "mercer", "vaughn", "sloane",
    "ellison", "brooks", "navarro", "whitlock", "ashford", "lockhart", "sterling",
    "beckett", "hollis", "marlowe", "cavanagh", "rutledge", "delacroix", "fairbanks",
    "abernathy", "castellano", "hawthorne", "kingsley", "underwood", "wolcott",
    "caldwell", "prescott", "langley", "hargrove", "winslow", "ashby", "corbin",
    "driscoll", "farrow", "greaves", "hadley", "jarvis", "kirkland", "lanning",
    "mabry", "ogden", "pemberton", "radcliffe", "sinclair", "thorne", "upton",
    "vance", "waverly", "yates", "ziegler", "ashcroft", "bexley", "cromwell",
    "danforth", "everett", "fenwick", "grimshaw", "holloway", "ingram", "keswick",
    "lockwood", "merrick", "norcross", "orwell", "pennington", "quimby", "ridley",
]

# Curated fallback passwords: real, well-known leaked passwords (present in
# rockyou), none of them top-20. Used only when no --wordlist is given.
_FALLBACK_PASSWORDS = [
    "babygirl1", "iloveyou2", "sunshine7", "princess7", "chocolate1", "michelle1",
    "superman1", "blink182x", "jasmine12", "soccer123", "monkey123", "hannah12",
    "jessica10", "charlie11", "hunter123", "cookie123", "bandit99", "ginger12",
    "orange99", "purple12", "dolphin12", "flower123", "summer2023", "winter22",
    "liverpool8", "arsenal12", "chelsea99", "cheese123", "tigger12", "snoopy99",
    "peanut123", "buster12", "shadow123", "maggie12", "taylor13", "madison7",
    "brandon1", "matthew12", "andrew123", "nicole123", "danielle1", "amanda12",
    "ashley123", "brittany1", "samantha7", "victoria1", "elizabeth1", "anthony12",
]


# Shared vault credentials — the SAME for every target by design. The vault_id
# and vault_password are constant across all clients; each student still has to
# decrypt them from their own AES export. (Sharing the answer is deterred by the
# cash prize for first solve, so uniqueness isn't needed here.) Overridable per
# event via --vault-id / --vault-password.
SHARED_VAULT_ID = "VLT-4096"
SHARED_VAULT_PASSWORD = "vaultline-mainframe-27"


class Command(BaseCommand):
    help = "Create Vaultline Heist target accounts (VaultClients)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20, help="Total targets to ensure exist.")
        parser.add_argument("--wordlist", type=str, default="", help="Path to a wordlist (e.g. rockyou.txt).")
        parser.add_argument("--min-rank", type=int, default=500, help="Skip the first N lines of the wordlist.")
        parser.add_argument("--max-rank", type=int, default=6000, help="Only draw passwords from before this line.")
        parser.add_argument("--vault-id", type=str, default=SHARED_VAULT_ID, help="Shared vault id for every target.")
        parser.add_argument("--vault-password", type=str, default=SHARED_VAULT_PASSWORD, help="Shared vault password for every target.")
        parser.add_argument("--fresh", action="store_true", help="Delete existing UNASSIGNED targets first.")
        parser.add_argument("--reset", action="store_true", help="Delete ALL targets first (full from-scratch refresh; clears every student's progress).")
        parser.add_argument("--assign", action="store_true", help="Assign spare targets to students who lack one.")

    def handle(self, *args, **opts):
        if opts["reset"]:
            deleted, _ = VaultClient.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"RESET: removed ALL {deleted} existing target(s) + their progress."))
        elif opts["fresh"]:
            deleted, _ = VaultClient.objects.filter(assigned_to__isnull=True).delete()
            self.stdout.write(f"Removed {deleted} unassigned target(s).")

        passwords = self._load_passwords(opts)
        existing = VaultClient.objects.count()
        target_total = opts["count"]
        to_create = max(target_total - existing, 0)

        used_usernames = set(VaultClient.objects.values_list("username", flat=True))
        created = 0
        for _ in range(to_create):
            username = self._unique_username(used_usernames)
            used_usernames.add(username)
            password = passwords.pop() if passwords else secrets.choice(_FALLBACK_PASSWORDS)

            VaultClient.objects.create(
                username=username,
                password=password,
                display_name=username.replace(".", " ").title(),
                # Shared vault credentials — identical for every target.
                vault_id=opts["vault_id"],
                vault_password=opts["vault_password"],
                account_key=crypto.generate_key(),
                vault_key=crypto.generate_key(),
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} target(s); {VaultClient.objects.count()} total."))

        if opts["assign"]:
            self._assign_spares()

        if not opts["wordlist"]:
            self.stdout.write(self.style.WARNING(
                "No --wordlist given: used the curated fallback list. Make sure students "
                "brute-force with a list that contains these passwords (e.g. rockyou.txt)."
            ))

    # ------------------------------------------------------------------
    def _load_passwords(self, opts) -> list[str]:
        path = opts["wordlist"]
        if not path:
            pool = list(_FALLBACK_PASSWORDS)
            random.shuffle(pool)
            return pool
        try:
            with open(path, "r", encoding="latin-1", errors="ignore") as fh:
                lines = [ln.strip() for ln in fh]
        except OSError as exc:
            raise CommandError(f"Could not read wordlist {path!r}: {exc}")
        band = [
            w for w in lines[opts["min_rank"]: opts["max_rank"]]
            if 6 <= len(w) <= 16 and w.isprintable() and " " not in w
        ]
        if not band:
            raise CommandError("Wordlist band is empty — adjust --min-rank/--max-rank.")
        random.shuffle(band)
        self.stdout.write(f"Loaded {len(band)} candidate passwords from {path} (ranks {opts['min_rank']}–{opts['max_rank']}).")
        return band

    def _unique_username(self, used: set[str]) -> str:
        for _ in range(500):
            name = f"{secrets.choice(_FIRST)}.{secrets.choice(_LAST)}"
            if name not in used:
                return name
        # Extremely unlikely fallback: append digits.
        return f"{secrets.choice(_FIRST)}.{secrets.choice(_LAST)}{secrets.randbelow(999)}"

    def _assign_spares(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        unassigned_students = (
            User.objects.filter(role=User.Role.STUDENT, is_staff=False, vault_target__isnull=True)
        )
        spares = list(VaultClient.objects.filter(assigned_to__isnull=True))
        n = 0
        for student in unassigned_students:
            if not spares:
                break
            target = spares.pop()
            target.assigned_to = student
            target.save(update_fields=["assigned_to"])
            n += 1
        self.stdout.write(f"Assigned {n} target(s) to students who lacked one.")
