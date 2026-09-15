from django.contrib import admin

from .models import VaultClient


@admin.register(VaultClient)
class VaultClientAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "assigned_to",
        "stages_done",
        "points",
        "password_rotated",
        "is_solved",
    )
    list_filter = ("password_rotated",)
    search_fields = ("username", "flag", "assigned_to__username")
    readonly_fields = (
        "cracked_login_at",
        "downloaded_data_at",
        "rotated_password_at",
        "opened_vault_at",
        "captured_flag_at",
        "created_at",
    )

    @admin.display(description="Stages")
    def stages_done(self, obj):
        return f"{obj.stages_done}/{len(obj.POINTS)}"

    @admin.display(boolean=True, description="Solved")
    def is_solved(self, obj):
        return obj.is_solved
