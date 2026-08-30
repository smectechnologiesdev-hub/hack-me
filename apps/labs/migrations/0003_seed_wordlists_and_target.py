"""Data migration: seed reference wordlists and the crackable target account.

Runs automatically on every deploy (CI/CD executes ``manage.py migrate``), so a
fresh live box has something to crack without any shell access.  It:

* creates/updates the three predefined educational wordlists, and
* ensures a REAL, loginable target account with a deliberately weak password so
  students can brute-force ``POST /login/`` and then sign in as that account.

The target username/password default to a known pair but can be overridden at
deploy time with the ``LAB_TARGET_USERNAME`` / ``LAB_TARGET_PASSWORD`` env vars.
Everything here is idempotent and never touches a staff/superuser account.
"""

import os

from django.contrib.auth.hashers import make_password
from django.db import migrations

# Same datasets as the ``seed_wordlists`` management command, inlined so this
# migration stays frozen and self-contained.
WORDLISTS = [
    {
        "name": "Starter Set",
        "difficulty": "EASY",
        "description": "A tiny beginner wordlist for a first successful brute-force run.",
        "passwords": [
            "password", "123456", "student123", "welcome", "python",
            "django", "hello123", "training", "python123",
        ],
    },
    {
        "name": "Common Passwords",
        "difficulty": "MEDIUM",
        "description": "A slightly larger list mixing common words and simple patterns.",
        "passwords": [
            "password", "password1", "qwerty", "letmein", "admin123",
            "iloveyou", "sunshine", "monkey", "football", "dragon",
            "trustno1", "student2024", "changeme", "welcome1", "training42",
        ],
    },
    {
        "name": "Extended Practice",
        "difficulty": "HARD",
        "description": "A longer list so the loop must iterate more before success.",
        "passwords": [
            "password", "P@ssw0rd", "spring2024", "autumn2024", "summer!23",
            "qwerty123", "baseball", "superman", "batman123", "computer",
            "internet", "security", "network1", "database", "developer",
            "codewars", "hackerman", "keyboard1", "mustang", "shadow99",
        ],
    },
]

# The crackable target.  Deliberately weak password for the training exercise.
DEFAULT_TARGET_USERNAME = "abraham"
DEFAULT_TARGET_PASSWORD = "sunshine213"


def seed(apps, schema_editor):
    Wordlist = apps.get_model("labs", "Wordlist")
    User = apps.get_model("accounts", "User")

    for spec in WORDLISTS:
        Wordlist.objects.update_or_create(
            name=spec["name"],
            defaults={
                "difficulty": spec["difficulty"],
                "description": spec["description"],
                "passwords": spec["passwords"],
                "is_active": True,
            },
        )

    username = (os.environ.get("LAB_TARGET_USERNAME") or DEFAULT_TARGET_USERNAME).strip()
    password = os.environ.get("LAB_TARGET_PASSWORD") or DEFAULT_TARGET_PASSWORD

    user, _ = User.objects.get_or_create(
        username=username, defaults={"role": "STUDENT"},
    )
    # Never clobber an admin who happens to share the name.
    if user.is_staff or user.is_superuser:
        return
    user.is_staff = False
    user.is_superuser = False
    user.password = make_password(password)
    user.save()


def unseed(apps, schema_editor):
    """Remove the seeded wordlists; leave the user account untouched."""
    Wordlist = apps.get_model("labs", "Wordlist")
    Wordlist.objects.filter(name__in=[w["name"] for w in WORDLISTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0002_lab_is_primary"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
