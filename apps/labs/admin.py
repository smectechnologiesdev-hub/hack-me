"""Admin for wordlists and labs, including instructor actions."""

from django.contrib import admin, messages

from .models import Lab, Wordlist
from .services import reset_lab


@admin.register(Wordlist)
class WordlistAdmin(admin.ModelAdmin):
    list_display = ("name", "difficulty", "size", "is_active", "created_at")
    list_filter = ("difficulty", "is_active")
    search_fields = ("name", "description")
    readonly_fields = ("created_at",)

    @admin.display(description="passwords")
    def size(self, obj):
        return obj.size


@admin.register(Lab)
class LabAdmin(admin.ModelAdmin):
    list_display = (
        "lab_token_short",
        "student",
        "username",
        "wordlist",
        "status",
        "attempt_count",
        "max_attempts",
        "is_active",
        "started_at",
        "expires_at",
    )
    list_filter = ("status", "is_active", "wordlist")
    search_fields = ("lab_token", "student__username", "username")
    # target_password_hash is intentionally NOT shown; the rest is read-only so
    # instructors can inspect but not tamper with lifecycle fields by hand.
    readonly_fields = (
        "lab_token",
        "username",
        "student",
        "wordlist",
        "attempt_count",
        "started_at",
        "completed_at",
        "expires_at",
    )
    exclude = ("target_password_hash",)
    actions = ("disable_labs", "enable_labs", "reset_labs")

    @admin.display(description="token")
    def lab_token_short(self, obj):
        return f"{obj.lab_token[:10]}…"

    @admin.action(description="Disable selected labs")
    def disable_labs(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Disabled {updated} lab(s).", messages.SUCCESS)

    @admin.action(description="Enable selected labs")
    def enable_labs(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"Enabled {updated} lab(s).", messages.SUCCESS)

    @admin.action(description="Reset selected labs (wipe attempts, re-arm)")
    def reset_labs(self, request, queryset):
        count = 0
        for lab in queryset:
            reset_lab(lab)
            count += 1
        self.message_user(request, f"Reset {count} lab(s).", messages.SUCCESS)
