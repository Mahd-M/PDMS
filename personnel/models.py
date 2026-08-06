from django.conf import settings
from django.db import models


class Officer(models.Model):
    """Roster entry linking a person to their login account and duty station."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="officer_profile")
    rank = models.CharField(max_length=100)
    station = models.CharField(max_length=100)
    date_joined_force = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.rank} {self.user.get_full_name() or self.user.username} -- {self.station}"
