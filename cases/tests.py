from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from .models import Case, FIR
from .views import visible_firs_for


def make_fir(number, sealed, filed_by, station="Saddar"):
    fir = FIR.objects.create(
        fir_number=number, station=station, sections_of_law="PPC 379",
        complainant_name="Ayesha Khan", complainant_contact="0300-0000000",
        narrative="Test narrative.", is_sealed=sealed, filed_by=filed_by,
    )
    Case.objects.create(fir=fir)
    return fir


class FieldEncryptionTests(TestCase):
    """
    complainant_name is an EncryptedTextField -- it must round-trip
    correctly through the ORM (encrypt on write, decrypt on read) while
    staying unreadable to anyone reading the raw table.
    """

    def setUp(self):
        self.filer = User.objects.create_user(username="enc_filer", password="Correct-Horse-6!", role=Role.SHO)

    def test_round_trips_through_the_orm(self):
        fir = make_fir("FIR-ENC-1", sealed=False, filed_by=self.filer)
        fetched = FIR.objects.get(pk=fir.pk)
        self.assertEqual(fetched.complainant_name, "Ayesha Khan")

    def test_raw_column_is_not_plaintext(self):
        fir = make_fir("FIR-ENC-2", sealed=False, filed_by=self.filer)
        with connection.cursor() as cursor:
            cursor.execute("SELECT complainant_name FROM cases_fir WHERE id = %s", [fir.pk])
            raw_value = cursor.fetchone()[0]
        self.assertNotIn("Ayesha", raw_value)
        self.assertNotEqual(raw_value, "Ayesha Khan")


class SealedFIRVisibilityTests(TestCase):
    """
    visible_firs_for is the single choke point every FIR-touching view
    goes through. This locks down, per role, exactly which of a sealed
    FIR, an FIR sealed but assigned to the investigator, and a plain
    FIR should be visible -- the row-level security the rest of the
    app depends on.
    """

    def setUp(self):
        self.admin = User.objects.create_user(username="rbac_admin", password="Correct-Horse-7!", role=Role.ADMIN)
        self.sho = User.objects.create_user(username="rbac_sho", password="Correct-Horse-7!", role=Role.SHO)
        self.auditor = User.objects.create_user(username="rbac_auditor", password="Correct-Horse-7!", role=Role.AUDITOR)
        self.investigator = User.objects.create_user(username="rbac_investigator", password="Correct-Horse-7!", role=Role.INVESTIGATOR)
        self.other_investigator = User.objects.create_user(username="rbac_other_inv", password="Correct-Horse-7!", role=Role.INVESTIGATOR)
        self.clerk = User.objects.create_user(username="rbac_clerk", password="Correct-Horse-7!", role=Role.CLERK)

        self.sealed_assigned = make_fir("FIR-SEALED-ASSIGNED", sealed=True, filed_by=self.admin)
        self.sealed_assigned.case.assigned_officer = self.investigator
        self.sealed_assigned.case.save()

        self.sealed_unassigned = make_fir("FIR-SEALED-OTHER", sealed=True, filed_by=self.admin)
        self.plain = make_fir("FIR-PLAIN", sealed=False, filed_by=self.admin)

    def test_admin_sho_and_auditor_see_everything(self):
        for user in (self.admin, self.sho, self.auditor):
            visible = set(visible_firs_for(user).values_list("fir_number", flat=True))
            self.assertEqual(visible, {"FIR-SEALED-ASSIGNED", "FIR-SEALED-OTHER", "FIR-PLAIN"}, user.username)

    def test_investigator_sees_own_sealed_case_plus_all_unsealed(self):
        visible = set(visible_firs_for(self.investigator).values_list("fir_number", flat=True))
        self.assertEqual(visible, {"FIR-SEALED-ASSIGNED", "FIR-PLAIN"})

    def test_investigator_does_not_see_someone_elses_sealed_case(self):
        visible = set(visible_firs_for(self.other_investigator).values_list("fir_number", flat=True))
        self.assertEqual(visible, {"FIR-PLAIN"})

    def test_clerk_never_sees_sealed_firs(self):
        visible = set(visible_firs_for(self.clerk).values_list("fir_number", flat=True))
        self.assertEqual(visible, {"FIR-PLAIN"})

    def test_clerk_gets_404_on_a_sealed_firs_detail_page(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("cases:fir_detail", args=[self.sealed_unassigned.pk]))
        self.assertEqual(response.status_code, 404)

    def test_clerk_can_view_an_unsealed_firs_detail_page(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("cases:fir_detail", args=[self.plain.pk]))
        self.assertEqual(response.status_code, 200)


class FIRCreateViewTests(TestCase):
    def setUp(self):
        self.sho = User.objects.create_user(username="create_sho", password="Correct-Horse-8!", role=Role.SHO)
        self.clerk = User.objects.create_user(username="create_clerk", password="Correct-Horse-8!", role=Role.CLERK)
        self.investigator = User.objects.create_user(username="create_inv", password="Correct-Horse-8!", role=Role.INVESTIGATOR)

    def test_sho_can_file_a_new_fir(self):
        self.client.force_login(self.sho)
        response = self.client.post(reverse("cases:fir_create"), {
            "fir_number": "FIR-NEW-1", "station": "Saddar", "sections_of_law": "PPC 379",
            "complainant_name": "Bilal Ahmed", "complainant_contact": "0300-1111111",
            "narrative": "Theft reported.",
        })
        fir = FIR.objects.get(fir_number="FIR-NEW-1")
        self.assertRedirects(response, reverse("cases:fir_detail", args=[fir.pk]))
        self.assertTrue(Case.objects.filter(fir=fir).exists())

    def test_investigator_cannot_file_a_new_fir(self):
        self.client.force_login(self.investigator)
        response = self.client.post(reverse("cases:fir_create"), {
            "fir_number": "FIR-NEW-2", "station": "Saddar", "sections_of_law": "PPC 379",
            "complainant_name": "Bilal Ahmed", "complainant_contact": "0300-1111111",
            "narrative": "Theft reported.",
        })
        self.assertRedirects(response, reverse("cases:fir_list"))
        self.assertFalse(FIR.objects.filter(fir_number="FIR-NEW-2").exists())
