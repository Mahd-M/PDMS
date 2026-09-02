from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from cases.models import Case, FIR
from missing_persons.models import MissingPerson
from records.models import CriminalRecord
from vehicles.models import Vehicle


class SearchTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="search_admin", password="Correct-Horse-26!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="search_clerk", password="Correct-Horse-26!", role=Role.CLERK)

        sealed_fir = FIR.objects.create(
            fir_number="FIR-2026-000777", station="Saddar", sections_of_law="PPC 379",
            complainant_name="X", narrative="A confidential burglary case.", is_sealed=True, filed_by=self.admin,
        )
        Case.objects.create(fir=sealed_fir)
        self.plain_fir = FIR.objects.create(
            fir_number="FIR-2026-000888", station="Clifton", sections_of_law="PPC 420",
            complainant_name="X", narrative="A public fraud case.", is_sealed=False, filed_by=self.admin,
        )
        Case.objects.create(fir=self.plain_fir)

        self.record = CriminalRecord.objects.create(full_name="Kashif Nawaz", cnic="42101-9999999-9")
        self.person = MissingPerson.objects.create(
            full_name="Hina Aslam", last_seen_date="2026-01-01", last_seen_location="Malir",
            reporting_relative_name="Aslam Sr.",
        )
        self.vehicle = Vehicle.objects.create(registration_number="KHI-7777", make="Toyota", model="Fortuner", owner_name="Y")

    def test_matches_fir_by_identifier_substring(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"), {"q": "000888"})
        firs = response.context["results"]["firs"]
        self.assertEqual([f.fir_number for f in firs], ["FIR-2026-000888"])

    def test_matches_fir_by_free_text_narrative(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"), {"q": "fraud"})
        firs = response.context["results"]["firs"]
        self.assertIn(self.plain_fir, firs)

    def test_sealed_fir_never_appears_in_a_clerks_results(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("search:results"), {"q": "2026"})
        fir_numbers = [f.fir_number for f in response.context["results"]["firs"]]
        self.assertNotIn("FIR-2026-000777", fir_numbers)

    def test_matches_encrypted_criminal_record_name(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"), {"q": "Kashif"})
        self.assertIn(self.record, response.context["results"]["criminal_records"])

    def test_matches_encrypted_missing_person_name(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"), {"q": "Hina"})
        self.assertIn(self.person, response.context["results"]["missing_persons"])

    def test_matches_vehicle_by_registration_and_free_text(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"), {"q": "7777"})
        self.assertIn(self.vehicle, response.context["results"]["vehicles"])

        response = self.client.get(reverse("search:results"), {"q": "Fortuner"})
        self.assertIn(self.vehicle, response.context["results"]["vehicles"])

    def test_no_query_returns_empty_results_without_erroring(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("search:results"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["results"]["firs"], [])
