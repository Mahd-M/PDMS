from django.conf import settings
from django.db import models

from .hashchain import GENESIS_HASH, compute_row_hash


class AuditLog(models.Model):
    """
    Append-only record of who did what, to which record, and when.

    Maps to CJIS Security Policy Area 4 (Audit and Accountability):
    agencies must log all access to and modification of criminal
    justice information, and that log must itself be protected from
    unauthorized modification or deletion. Hash-chaining each row to
    the one before it means the log detects its own tampering --
    editing row 500 breaks the stored hash of every row after it.
    """

    class Action(models.TextChoices):
        VIEW = "view", "Viewed"
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        LOGIN = "login", "Logged in"
        LOGIN_FAILED = "login_failed", "Failed login"
        LOGOUT = "logout", "Logged out"

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Null only for pre-authentication events such as failed logins.",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    detail = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    prev_hash = models.CharField(max_length=64)
    row_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["timestamp"]

    def _content_fields(self):
        return (
            str(self.user_id or ""),
            self.action,
            self.object_type,
            self.object_id,
            self.detail,
            str(self.ip_address or ""),
        )

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("AuditLog rows are immutable and cannot be updated.")
        last = AuditLog.objects.order_by("-id").first()
        self.prev_hash = last.row_hash if last else GENESIS_HASH
        self.row_hash = compute_row_hash(self.prev_hash, *self._content_fields())
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog rows cannot be deleted; the chain must stay intact.")

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {self.user} {self.action} {self.object_type} {self.object_id}"
