from django.db import models

from cases.models import Case
from config.encrypted_fields import EncryptedTextField


class Vehicle(models.Model):
    """
    A registered vehicle -- either just a general lookup entry, or tied
    to an open investigation via `case`. Owner details are PII, encrypted
    the same way as every other person-identifying field in this app.
    """

    class Status(models.TextChoices):
        NORMAL = "normal", "Normal"
        RECOVERED = "recovered", "Recovered"
        WANTED = "wanted", "Wanted"

    registration_number = models.CharField(max_length=30, unique=True, db_index=True)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    owner_name = EncryptedTextField()
    owner_contact = EncryptedTextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NORMAL)
    case = models.ForeignKey(
        Case, on_delete=models.SET_NULL, null=True, blank=True, related_name="vehicles"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.registration_number} ({self.get_status_display()})"
