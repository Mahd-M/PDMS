from django.conf import settings
from django.db import models

from config.encrypted_fields import EncryptedTextField


class FIR(models.Model):
    """
    First Information Report -- the formal document that opens a
    criminal case under Pakistani policing procedure (Cr.P.C. Section
    154). Complainant / victim details are encrypted at the field
    level since this is some of the most sensitive PII the system
    holds.
    """
    fir_number = models.CharField(max_length=30, unique=True, db_index=True)
    station = models.CharField(max_length=100)
    date_filed = models.DateTimeField(auto_now_add=True)
    sections_of_law = models.CharField(max_length=255, help_text="e.g. PPC 379, 411")

    complainant_name = EncryptedTextField()
    complainant_contact = EncryptedTextField(blank=True, default="")
    narrative = models.TextField()

    is_sealed = models.BooleanField(
        default=False,
        help_text="Sealed FIRs are excluded from clerk-level queries by row-level security.",
    )
    filed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="firs_filed"
    )

    class Meta:
        ordering = ["-date_filed"]

    def __str__(self):
        return f"FIR {self.fir_number} -- {self.station}"


class Case(models.Model):
    """An investigation opened against an FIR."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        UNDER_INVESTIGATION = "investigating", "Under investigation"
        CHALLAN_FILED = "challan", "Challan filed"
        IN_COURT = "court", "In court"
        CLOSED = "closed", "Closed"

    fir = models.OneToOneField(FIR, on_delete=models.PROTECT, related_name="case")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_cases",
    )
    court_reference = models.CharField(max_length=100, blank=True)
    next_hearing_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Case for {self.fir.fir_number} ({self.get_status_display()})"
