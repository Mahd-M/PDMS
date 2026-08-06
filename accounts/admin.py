from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class PDMSUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("PDMS role & security", {
            "fields": ("role", "badge_number", "mfa_enabled", "failed_login_attempts", "locked_until", "must_change_password"),
        }),
    )
    list_display = ("username", "role", "mfa_enabled", "is_active", "is_staff")
    readonly_fields = ("failed_login_attempts", "locked_until")
