import os
import sys

from django.apps import AppConfig

# Management commands during which we must NOT touch the database (tables may
# not exist yet, or seeding would be wrong/pointless).  When the app is served
# (daphne/gunicorn/uvicorn/runserver) sys.argv[1] is none of these, so seeding
# runs on every real app start.
_NO_SEED_COMMANDS = {
    "migrate", "makemigrations", "collectstatic", "test",
    "shell", "shell_plus", "dumpdata", "loaddata", "createsuperuser",
    "check", "showmigrations", "sqlmigrate", "flush",
}


class LabsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.labs"
    label = "labs"
    verbose_name = "Labs"

    def ready(self):
        """Ensure the crackable target account exists on every app start.

        This is a belt-and-suspenders companion to the data migration: a deploy
        that only restarts the app (without running ``migrate``) still ends up
        with a loginable target, so students always have something to crack.

        Guarded so it never runs during migrations/tests/other management
        commands, and wrapped so a not-yet-migrated database can never crash
        startup.  Disable entirely with ``LAB_SKIP_STARTUP_SEED=1``.
        """
        if os.environ.get("LAB_SKIP_STARTUP_SEED"):
            return
        if len(sys.argv) > 1 and sys.argv[1] in _NO_SEED_COMMANDS:
            return
        try:
            self._seed_target()
        except Exception:
            # Never let seeding break app startup (e.g. DB not migrated yet).
            pass

    @staticmethod
    def _seed_target():
        from django.db import connection

        from .services import ensure_victim_user

        # If the users table isn't there yet, silently skip — a later start
        # (after migrate has created it) will seed successfully.
        if "accounts_user" not in connection.introspection.table_names():
            return

        username = (os.environ.get("LAB_TARGET_USERNAME") or "abraham").strip()
        password = os.environ.get("LAB_TARGET_PASSWORD") or "sunshine213"
        ensure_victim_user(username, password)
