from django.db import models

from django.db import models

from config.encrypted_fields import EncryptedTextField


class MissingPerson(models.Model):
    """
    A missing-person report. `reporting_relative_*` fields are encrypted
    for the same reason as an FIR's complainant fields -- they're a
    named individual's personal contact details, not the missing
    person's own record.
    """

    class Status(models.TextChoices):
        MISSING = "missing", "Missing"
        FOUND = "found", "Found"
        DECEASED = "deceased", "Deceased"

    full_name = EncryptedTextField()
    last_seen_date = models.DateField()
    last_seen_location = models.CharField(max_length=255)
    reporting_relative_name = EncryptedTextField()
    reporting_relative_contact = EncryptedTextField(blank=True, default="")
    description = models.TextField(blank=True)
    photo = models.ImageField(upload_to="missing_persons/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.MISSING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"