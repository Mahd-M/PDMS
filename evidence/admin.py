from django.contrib import admin
from .models import Evidence, ChainOfCustodyEntry


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    readonly_fields = ("sha256_hash",)
    list_display = ("description", "case", "sha256_hash", "uploaded_at")


@admin.register(ChainOfCustodyEntry)
class ChainOfCustodyEntryAdmin(admin.ModelAdmin):
    list_display = ("evidence", "action", "actor", "timestamp")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
