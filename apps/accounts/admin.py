"""Admin registration for the custom user model."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

User = get_user_model()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_staff", "is_active", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    # Add the role field to the default UserAdmin fieldsets.
    fieldsets = UserAdmin.fieldsets + (("Lab role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Lab role", {"fields": ("role",)}),
    )
