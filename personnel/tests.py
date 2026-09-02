from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from .models import Assignment, Officer, OfficerAttendance


def make_officer(username, rank="Constable", station="Saddar"):
    user = User.objects.create_user(username=username, password="Correct-Horse-13!", role=Role.INVESTIGATOR)
    return Officer.objects.create(user=user, rank=rank, station=station)


class RosterTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="roster_viewer", password="Correct-Horse-14!", role=Role.CLERK)
        self.officer = make_officer("roster_officer")

    def test_roster_lists_active_officers(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("personnel:roster"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.officer.station)

    def test_officer_detail_renders(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("personnel:officer_detail", args=[self.officer.pk]))
        self.assertEqual(response.status_code, 200)


class AttendanceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="att_admin", password="Correct-Horse-15!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="att_clerk", password="Correct-Horse-15!", role=Role.CLERK)
        self.officer = make_officer("att_officer")

    def test_clerk_cannot_mark_attendance(self):
        self.client.force_login(self.clerk)
        response = self.client.post(reverse("personnel:mark_attendance"), {
            "date": "2026-01-15", f"status_{self.officer.pk}": OfficerAttendance.Status.PRESENT,
        })
        self.assertRedirects(response, reverse("personnel:roster"))
        self.assertFalse(OfficerAttendance.objects.filter(officer=self.officer).exists())

    def test_admin_can_mark_attendance(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("personnel:mark_attendance"), {
            "date": "2026-01-15", f"status_{self.officer.pk}": OfficerAttendance.Status.PRESENT,
        })
        self.assertEqual(response.status_code, 302)
        record = OfficerAttendance.objects.get(officer=self.officer, date="2026-01-15")
        self.assertEqual(record.status, OfficerAttendance.Status.PRESENT)
        self.assertEqual(record.marked_by, self.admin)

    def test_remarking_the_same_day_updates_rather_than_duplicates(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("personnel:mark_attendance"), {
            "date": "2026-01-15", f"status_{self.officer.pk}": OfficerAttendance.Status.PRESENT,
        })
        self.client.post(reverse("personnel:mark_attendance"), {
            "date": "2026-01-15", f"status_{self.officer.pk}": OfficerAttendance.Status.ABSENT,
        })
        self.assertEqual(OfficerAttendance.objects.filter(officer=self.officer, date="2026-01-15").count(), 1)
        record = OfficerAttendance.objects.get(officer=self.officer, date="2026-01-15")
        self.assertEqual(record.status, OfficerAttendance.Status.ABSENT)


class AssignmentTests(TestCase):
    def setUp(self):
        self.sho = User.objects.create_user(username="assign_sho", password="Correct-Horse-16!", role=Role.SHO)
        self.clerk = User.objects.create_user(username="assign_clerk", password="Correct-Horse-16!", role=Role.CLERK)
        self.officer = make_officer("assign_officer")

    def test_sho_can_create_assignment(self):
        self.client.force_login(self.sho)
        response = self.client.post(reverse("personnel:assignment_create", args=[self.officer.pk]), {
            "description": "Traffic duty", "station": "Saddar", "start_date": "2026-01-01",
        })
        assignment = Assignment.objects.get(officer=self.officer)
        self.assertRedirects(response, reverse("personnel:officer_detail", args=[self.officer.pk]))
        self.assertEqual(assignment.description, "Traffic duty")
        self.assertIsNone(assignment.end_date)

    def test_clerk_cannot_create_assignment(self):
        self.client.force_login(self.clerk)
        response = self.client.post(reverse("personnel:assignment_create", args=[self.officer.pk]), {
            "description": "Traffic duty", "station": "Saddar", "start_date": "2026-01-01",
        })
        self.assertRedirects(response, reverse("personnel:officer_detail", args=[self.officer.pk]))
        self.assertFalse(Assignment.objects.filter(officer=self.officer).exists())
