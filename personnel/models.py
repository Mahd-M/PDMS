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


class OfficerAttendance(models.Model):
    """
    One row per officer per day. `marked_by` records who took
    attendance -- not the officer being marked -- same accountability
    idea as `Evidence.uploaded_by` or `FIR.filed_by`.
    """

    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LEAVE = "leave", "Leave"

    officer = models.ForeignKey(Officer, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    marked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="attendance_marked")

    class Meta:
        ordering = ["-date", "officer__station"]
        constraints = [
            models.UniqueConstraint(fields=["officer", "date"], name="unique_attendance_per_officer_per_day"),
        ]

    def __str__(self):
        return f"{self.officer} -- {self.date} -- {self.get_status_display()}"
