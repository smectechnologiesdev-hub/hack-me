"""
Management command: seed the predefined educational wordlists.

Usage:
    python manage.py seed_wordlists

Idempotent: re-running updates the passwords/description of existing wordlists
by name rather than creating duplicates.  These datasets are entirely
server-controlled; students can never create or upload their own.
"""

from django.core.management.base import BaseCommand

from apps.labs.models import Wordlist

# Small, safe, clearly-educational datasets.  These are deliberately weak
# passwords used only inside isolated training labs.
WORDLISTS = [
    {
        "name": "Starter Set",
        "difficulty": Wordlist.Difficulty.EASY,
        "description": "A tiny beginner wordlist for a first successful brute-force run.",
        "passwords": [
            "password",
            "123456",
            "student123",
            "welcome",
            "python",
            "django",
            "hello123",
            "training",
            "python123",
        ],
    },
    {
        "name": "Common Passwords",
        "difficulty": Wordlist.Difficulty.MEDIUM,
        "description": "A slightly larger list mixing common words and simple patterns.",
        "passwords": [
            "password",
            "password1",
            "qwerty",
            "letmein",
            "admin123",
            "iloveyou",
            "sunshine",
            "monkey",
            "football",
            "dragon",
            "trustno1",
            "student2024",
            "changeme",
            "welcome1",
            "training42",
        ],
    },
    {
        "name": "Extended Practice",
        "difficulty": Wordlist.Difficulty.HARD,
        "description": "A longer list so the loop must iterate more before success.",
        "passwords": [
            "password",
            "P@ssw0rd",
            "spring2024",
            "autumn2024",
            "summer!23",
            "qwerty123",
            "baseball",
            "superman",
            "batman123",
            "computer",
            "internet",
            "security",
            "network1",
            "database",
            "developer",
            "codewars",
            "hackerman",
            "keyboard1",
            "mustang",
            "shadow99",
        ],
    },
]


class Command(BaseCommand):
    help = "Create or update the predefined educational wordlists."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for spec in WORDLISTS:
            obj, was_created = Wordlist.objects.update_or_create(
                name=spec["name"],
                defaults={
                    "difficulty": spec["difficulty"],
                    "description": spec["description"],
                    "passwords": spec["passwords"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            self.stdout.write(
                f"  {'created' if was_created else 'updated'}: "
                f"{obj.name} ({obj.size} passwords)"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created} created, {updated} updated."
            )
        )
