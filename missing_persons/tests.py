from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from .models import MissingPerson


class FieldEncryptionTests(TestCase):
    def test_names_round_trip_and_are_not_stored_in_plaintext(self):
        person = MissingPerson.objects.create(
            full_name="Sana Rafiq", last_seen_date="2026-01-01", last_seen_location="Clifton",
            reporting_relative_name="Rafiq Ahmed", reporting_relative_contact="0300-2222222",
        )
        fetched = MissingPerson.objects.get(pk=person.pk)
        self.assertEqual(fetched.full_name, "Sana Rafiq")
        self.assertEqual(fetched.reporting_relative_name, "Rafiq Ahmed")

        with connection.cursor() as cursor:
            cursor.execute("SELECT full_name, reporting_relative_name FROM missing_persons_missingperson WHERE id = %s", [person.pk])
            raw_name, raw_relative = cursor.fetchone()
        self.assertNotIn("Sana", raw_name)
        self.assertNotIn("Rafiq Ahmed", raw_relative)


class PersonCreateViewTests(TestCase):
    def setUp(self):
        self.clerk = User.objects.create_user(username="mp_clerk", password="Correct-Horse-20!", role=Role.CLERK)
        self.investigator = User.objects.create_user(username="mp_investigator", password="Correct-Horse-20!", role=Role.INVESTIGATOR)

    def test_clerk_can_file_a_report(self):
        self.client.force_login(self.clerk)
        response = self.client.post(reverse("missing_persons:person_create"), {
            "full_name": "Adeel Qureshi", "last_seen_date": "2026-01-10", "last_seen_location": "Gulshan",
            "reporting_relative_name": "Qureshi Sr.", "reporting_relative_contact": "0300-3333333",
            "description": "", "status": MissingPerson.Status.MISSING,
        })
        # reporting_relative_contact is Fernet-encrypted -- each encryption
        # uses a random IV, so a plaintext .get(field=...) lookup could
        # never match the stored ciphertext. Fetch the one record this
        # test created instead of filtering on the encrypted field.
        person = MissingPerson.objects.get()
        self.assertRedirects(response, reverse("missing_persons:person_detail", args=[person.pk]))

    def test_investigator_cannot_file_a_report(self):
        self.client.force_login(self.investigator)
        response = self.client.post(reverse("missing_persons:person_create"), {
            "full_name": "Adeel Qureshi", "last_seen_date": "2026-01-10", "last_seen_location": "Gulshan",
            "reporting_relative_name": "Qureshi Sr.", "reporting_relative_contact": "0300-4444444",
            "description": "", "status": MissingPerson.Status.MISSING,
        })
        self.assertRedirects(response, reverse("missing_persons:person_list"))
        # Not filtering on the encrypted field here (see the note above) --
        # a plain count is the meaningful check for "nothing was created".
        self.assertEqual(MissingPerson.objects.count(), 0)


class PersonListTests(TestCase):
    def test_list_and_detail_render(self):
        viewer = User.objects.create_user(username="mp_viewer", password="Correct-Horse-21!", role=Role.AUDITOR)
        person = MissingPerson.objects.create(
            full_name="Nida Farooq", last_seen_date="2026-01-05", last_seen_location="North Nazimabad",
            reporting_relative_name="Farooq Sr.",
        )
        self.client.force_login(viewer)
        list_response = self.client.get(reverse("missing_persons:person_list"))
        self.assertEqual(list_response.status_code, 200)
        detail_response = self.client.get(reverse("missing_persons:person_detail", args=[person.pk]))
        self.assertEqual(detail_response.status_code, 200)
