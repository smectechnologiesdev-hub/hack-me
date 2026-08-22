"""Admin for attempts (read-only log)."""

from django.contrib import admin

from .models import Attempt


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lab",
        "attempt_number",
        "username_attempted",
        "masked_password",
        "success",
        "created_at",
        "ip_address",
    )
    list_filter = ("success", "created_at")
    search_fields = ("lab__lab_token", "username_attempted", "ip_address")
    readonly_fields = [f.name for f in Attempt._meta.fields]
    date_hierarchy = "created_at"

    @admin.display(description="password")
    def masked_password(self, obj):
        return Attempt.mask_password(obj.password_attempted)

    def has_add_permission(self, request):
        # Attempts are only ever created by the training endpoint.
        return False
