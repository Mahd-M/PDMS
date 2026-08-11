from django.conf import settings
from django.db import models


class Officer(models.Model):
    """Roster entry linking a person to their login account and duty station."""

    class Shift(models.TextChoices):
        MORNING = "morning", "Morning"
        EVENING = "evening", "Evening"
        NIGHT = "night", "Night"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="officer_profile")
    rank = models.CharField(max_length=100)
    station = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True, default="")
    shift = models.CharField(max_length=20, choices=Shift.choices, blank=True, default="")
    contact_number = models.CharField(max_length=20, blank=True, default="")
    date_joined_force = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.rank} {self.user.get_full_name() or self.user.username} -- {self.station}"
