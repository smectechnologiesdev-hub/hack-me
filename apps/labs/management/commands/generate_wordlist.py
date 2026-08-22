"""
Generate a large wordlist for load/《feel》 testing (e.g. 500 passwords).

Usage:
    python manage.py generate_wordlist --count 500
    python manage.py generate_wordlist --count 1000 --name "Stress Test" --difficulty HARD

Creates (or updates) a Wordlist containing `count` unique passwords: a base of
realistic common passwords plus generated word+number/year/symbol mutations.
Pair it with `create_lab --wordlist "<name>" --max-attempts <>= count>`.
"""

import secrets

from django.core.management.base import BaseCommand

from apps.labs.models import Wordlist

# A base of realistic weak passwords.
_COMMON = [
    "password", "123456", "123456789", "qwerty", "12345678", "111111",
    "1234567", "sunshine", "iloveyou", "princess", "admin", "welcome",
    "666666", "abc123", "football", "123123", "monkey", "654321",
    "!@#$%^&*", "charlie", "aa123456", "donald", "password1", "qwerty123",
    "letmein", "dragon", "baseball", "superman", "batman", "trustno1",
    "master", "shadow", "michael", "jennifer", "hunter", "harley",
    "ranger", "buster", "thomas", "robert", "soccer", "hockey",
    "killer", "george", "andrew", "charlie1", "michelle", "jordan",
    "computer", "internet", "samsung", "starwars", "cheese", "summer",
    "ashley", "bailey", "passw0rd", "shadow1", "123qwe", "zxcvbnm",
]

_WORDS = [
    "spring", "autumn", "winter", "summer", "silver", "golden", "shadow",
    "dragon", "phoenix", "falcon", "tiger", "eagle", "cobra", "viper",
    "matrix", "ninja", "wizard", "hunter", "ranger", "captain", "orange",
    "purple", "crimson", "coffee", "guitar", "rocket", "sunset", "thunder",
    "diamond", "emerald", "sapphire", "titan", "nova", "comet", "raven",
    "wolf", "bear", "hawk", "storm", "frost", "ember", "shark", "panther",
]
_SUFFIXES = ["", "1", "12", "123", "!", "01", "99", "007", "2023", "2024",
             "2025", "#1", "22", "88", "00", "77", "69", "42"]
_LEET = str.maketrans({"a": "@", "o": "0", "i": "1", "e": "3", "s": "$"})


class Command(BaseCommand):
    help = "Generate a large wordlist (default 500 passwords) for testing."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=500)
        parser.add_argument("--name", default=None, help="Wordlist name (default: 'Stress Test <count>').")
        parser.add_argument("--difficulty", default=Wordlist.Difficulty.HARD,
                            choices=[c[0] for c in Wordlist.Difficulty.choices])

    def handle(self, *args, **opts):
        count = max(1, opts["count"])
        name = opts["name"] or f"Stress Test {count}"

        passwords = []
        seen = set()

        def add(p):
            if p and p not in seen:
                seen.add(p)
                passwords.append(p)

        # Seed with common passwords first.
        for p in _COMMON:
            add(p)
            if len(passwords) >= count:
                break

        # Then generate word + mutation combinations until we hit the count.
        guard = 0
        while len(passwords) < count and guard < count * 200:
            guard += 1
            word = secrets.choice(_WORDS)
            suffix = secrets.choice(_SUFFIXES)
            if secrets.randbelow(4) == 0:
                word = word.translate(_LEET)
            if secrets.randbelow(3) == 0:
                word = word.capitalize()
            add(word + suffix)

        passwords = passwords[:count]

        obj, created = Wordlist.objects.update_or_create(
            name=name,
            defaults={
                "difficulty": opts["difficulty"],
                "description": f"Auto-generated wordlist with {len(passwords)} passwords for testing.",
                "passwords": passwords,
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} wordlist '{name}' with {len(passwords)} passwords."
        ))
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Next: create a lab that uses it (raise the attempt cap!):"))
        self.stdout.write(self.style.SUCCESS(
            f'    python manage.py create_lab --wordlist "{name}" --max-attempts {len(passwords) + 50}'
        ))
        self.stdout.write("  (omit --password to pick a random target from the list, or pass one to fix it)")
