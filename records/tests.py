from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from .models import CourtDate, CriminalRecord


class FieldEncryptionTests(TestCase):
    """full_name and cnic carry the same sensitivity as an FIR's complainant fields."""

    def test_full_name_round_trips_and_is_not_stored_in_plaintext(self):
        record = CriminalRecord.objects.create(full_name="Fahad Malik", cnic="42101-1234567-1")
        fetched = CriminalRecord.objects.get(pk=record.pk)
        self.assertEqual(fetched.full_name, "Fahad Malik")

        with connection.cursor() as cursor:
            cursor.execute("SELECT full_name FROM records_criminalrecord WHERE id = %s", [record.pk])
            raw_value = cursor.fetchone()[0]
        self.assertNotIn("Fahad", raw_value)


class WantedListTests(TestCase):
    """
    Step 22: "wanted" is a filter over CriminalRecord, not a separate
    model, so flipping a record's status must make it appear on the
    wanted page with no extra step.
    """

    def setUp(self):
        self.viewer = User.objects.create_user(username="wanted_viewer", password="Correct-Horse-17!", role=Role.CLERK)
        self.record = CriminalRecord.objects.create(full_name="Zubair Hassan", status=CriminalRecord.Status.IN_CUSTODY)

    def test_record_not_on_wanted_list_until_status_changes(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("records:wanted_list"))
        self.assertNotContains(response, "Zubair Hassan")

        self.record.status = CriminalRecord.Status.WANTED
        self.record.save()

        response = self.client.get(reverse("records:wanted_list"))
        self.assertContains(response, "Zubair Hassan")


class RecordCreateViewTests(TestCase):
    def setUp(self):
        self.investigator = User.objects.create_user(username="rec_investigator", password="Correct-Horse-18!", role=Role.INVESTIGATOR)
        self.auditor = User.objects.create_user(username="rec_auditor", password="Correct-Horse-18!", role=Role.AUDITOR)

    def test_investigator_can_create_a_record(self):
        self.client.force_login(self.investigator)
        response = self.client.post(reverse("records:record_create"), {
            "full_name": "Imran Sheikh", "cnic": "35202-7654321-9", "aliases": "", "fingerprint_id": "",
            "status": CriminalRecord.Status.WANTED, "charges": "", "notes": "",
        })
        # cnic is Fernet-encrypted -- a random IV means a plaintext
        # .get(cnic=...) lookup could never match the stored ciphertext,
        # so fetch the one record this test created instead.
        record = CriminalRecord.objects.get()
        self.assertRedirects(response, reverse("records:record_detail", args=[record.pk]))

    def test_auditor_cannot_create_a_record(self):
        self.client.force_login(self.auditor)
        response = self.client.post(reverse("records:record_create"), {
            "full_name": "Imran Sheikh", "cnic": "35202-0000000-0", "aliases": "", "fingerprint_id": "",
            "status": CriminalRecord.Status.WANTED, "charges": "", "notes": "",
        })
        self.assertRedirects(response, reverse("records:record_list"))
        self.assertEqual(CriminalRecord.objects.count(), 0)


class CourtDateTests(TestCase):
    def setUp(self):
        self.sho = User.objects.create_user(username="cd_sho", password="Correct-Horse-19!", role=Role.SHO)
        self.record = CriminalRecord.objects.create(full_name="Waqas Tariq")

    def test_sho_can_add_a_court_date(self):
        self.client.force_login(self.sho)
        response = self.client.post(reverse("records:court_date_create", args=[self.record.pk]), {
            "date": "2026-03-01", "court_name": "Sessions Court", "outcome": "",
        })
        self.assertRedirects(response, reverse("records:record_detail", args=[self.record.pk]))
        self.assertEqual(CourtDate.objects.filter(criminal_record=self.record).count(), 1)
