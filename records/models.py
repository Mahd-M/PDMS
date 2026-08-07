from django.db import models

from config.encrypted_fields import EncryptedTextField


class CriminalRecord(models.Model):
    """
    A standing record of a known offender, independent of any single
    FIR -- the same person can appear across multiple FIRs over time.
    Name and CNIC are PII at least as sensitive as an FIR's complainant
    fields, so they're encrypted the same way (config/encrypted_fields.py).
    """

    class Status(models.TextChoices):
        WANTED = "wanted", "Wanted"
        IN_CUSTODY = "in_custody", "In custody"
        RELEASED = "released", "Released"
        DECEASED = "deceased", "Deceased"

    full_name = EncryptedTextField()
    cnic = EncryptedTextField(blank=True, default="")
    aliases = models.CharField(max_length=255, blank=True, help_text="Comma-separated")
    fingerprint_id = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to="criminal_records/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WANTED)
    charges = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class CourtDate(models.Model):
    """A single scheduled or past court appearance tied to a criminal record."""

    criminal_record = models.ForeignKey(
        CriminalRecord, on_delete=models.CASCADE, related_name="court_dates"
    )
    date = models.DateField()
    court_name = models.CharField(max_length=150)
    outcome = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.criminal_record} -- {self.court_name} on {self.date}"