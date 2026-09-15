"""Split the single vault recovery key into two independent AES-256 secrets.

The data export now encrypts {username, password} under ``account_key`` and
{vault_id, vault_password} under ``vault_key``; both ciphertext blobs are
generated on the fly at export time, so the stored ``vault_blob`` is dropped.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenge", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="vaultclient", name="recovery_key"),
        migrations.RemoveField(model_name="vaultclient", name="vault_blob"),
        migrations.AddField(
            model_name="vaultclient",
            name="account_key",
            field=models.CharField(blank=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="vaultclient",
            name="vault_key",
            field=models.CharField(blank=True, default="", max_length=64),
            preserve_default=False,
        ),
    ]
