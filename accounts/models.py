import pyotp
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Role(models.TextChoices):
    """
    CJIS Policy Area 5 (Access Control) requires role-based access with
    verified need-to-know -- users get the least access that lets them
    do their job, not blanket access "just in case".
    """
    ADMIN = "admin", "System administrator"
    SHO = "sho", "Station House Officer"
    INVESTIGATOR = "investigator", "Investigating officer"
    CLERK = "clerk", "Records clerk"
    AUDITOR = "auditor", "Read-only auditor / oversight"


class User(AbstractUser):
    """
    Custom user model carrying the role and the fields CJIS Policy Area 6
    (Identification and Authentication) requires: advanced authentication
    (MFA / TOTP) has been an auditable requirement since October 1, 2024,
    and accounts must lock out after repeated failed attempts.
    """
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLERK)
    badge_number = models.CharField(max_length=20, blank=True)

    # --- Advanced authentication (MFA), CJIS Policy Area 6 ---
    totp_secret = models.CharField(max_length=32, blank=True)
    mfa_enabled = models.BooleanField(default=False)

    # --- Account lockout, CJIS Policy Area 6 (Identification & Authentication) ---
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    # --- Password history / rotation flag ---
    must_change_password = models.BooleanField(default=True)
    password_last_changed = models.DateTimeField(null=True, blank=True)

    def is_locked_out(self) -> bool:
        return bool(self.locked_until and self.locked_until > timezone.now())

    def register_failed_login(self, max_attempts: int = 5, lockout_minutes: int = 15):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def register_successful_login(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def ensure_totp_secret(self) -> str:
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            self.save(update_fields=["totp_secret"])
        return self.totp_secret

    def verify_totp(self, code: str) -> bool:
        if not self.totp_secret:
            return False
        return pyotp.TOTP(self.totp_secret).verify(code, valid_window=1)

    def totp_provisioning_uri(self, issuer: str = "PDMS") -> str:
        secret = self.ensure_totp_secret()
        return pyotp.TOTP(secret).provisioning_uri(name=self.username, issuer_name=issuer)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
