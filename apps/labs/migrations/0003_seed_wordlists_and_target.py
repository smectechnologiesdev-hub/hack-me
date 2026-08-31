"""Data migration: intentionally a no-op.

Seeding the crackable target account used to happen here, but seeding data from
a migration also runs against the **test** database, where it polluted unrelated
labs tests (extra wordlists changed random wordlist selection, an extra user
collided with fixtures).

Seeding now lives solely in ``apps.labs.apps.LabsConfig.ready()`` (the app
startup hook), which is guarded to skip during ``test``/``migrate`` and other
management commands, so the test database stays clean while a real deploy still
gets a target account whenever the app boots.

This migration is kept (rather than deleted) so migration history stays linear
for any environment that already recorded it as applied.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0002_lab_is_primary"),
        ("accounts", "0001_initial"),
    ]

    operations = []
