from django.db import connection
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from cases.models import Case, FIR
from .models import Vehicle
from .views import visible_vehicles_for


def make_fir_and_case(number, sealed, filed_by):
    fir = FIR.objects.create(
        fir_number=number, station="Saddar", sections_of_law="PPC 379",
        complainant_name="Test Complainant", narrative="Test narrative.",
        is_sealed=sealed, filed_by=filed_by,
    )
    return Case.objects.create(fir=fir)


class FieldEncryptionTests(TestCase):
    def test_owner_name_round_trips_and_is_not_stored_in_plaintext(self):
        vehicle = Vehicle.objects.create(registration_number="KHI-1234", make="Honda", model="Civic", owner_name="Owais Malik")
        fetched = Vehicle.objects.get(pk=vehicle.pk)
        self.assertEqual(fetched.owner_name, "Owais Malik")

        with connection.cursor() as cursor:
            cursor.execute("SELECT owner_name FROM vehicles_vehicle WHERE id = %s", [vehicle.pk])
            raw_value = cursor.fetchone()[0]
        self.assertNotIn("Owais", raw_value)


class VehicleVisibilityTests(TestCase):
    """Mirrors cases.tests.SealedFIRVisibilityTests -- a vehicle tied to a sealed FIR is exactly as sensitive as that FIR."""

    def setUp(self):
        self.admin = User.objects.create_user(username="veh_admin", password="Correct-Horse-22!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="veh_clerk", password="Correct-Horse-22!", role=Role.CLERK)
        sealed_case = make_fir_and_case("FIR-VEH-SEALED", sealed=True, filed_by=self.admin)
        plain_case = make_fir_and_case("FIR-VEH-PLAIN", sealed=False, filed_by=self.admin)
        self.sealed_vehicle = Vehicle.objects.create(registration_number="KHI-SEALED", make="Suzuki", model="Alto", owner_name="X", case=sealed_case)
        self.plain_vehicle = Vehicle.objects.create(registration_number="KHI-PLAIN", make="Toyota", model="Corolla", owner_name="Y", case=plain_case)
        self.unlinked_vehicle = Vehicle.objects.create(registration_number="KHI-FREE", make="Kia", model="Sportage", owner_name="Z")

    def test_clerk_does_not_see_vehicle_on_a_sealed_case(self):
        visible = set(visible_vehicles_for(self.clerk).values_list("registration_number", flat=True))
        self.assertEqual(visible, {"KHI-PLAIN", "KHI-FREE"})

    def test_admin_sees_every_vehicle(self):
        visible = set(visible_vehicles_for(self.admin).values_list("registration_number", flat=True))
        self.assertEqual(visible, {"KHI-SEALED", "KHI-PLAIN", "KHI-FREE"})

    def test_clerk_gets_404_on_a_sealed_vehicles_detail_page(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("vehicles:vehicle_detail", args=[self.sealed_vehicle.pk]))
        self.assertEqual(response.status_code, 404)


class VehicleCreateViewTests(TestCase):
    def setUp(self):
        self.sho = User.objects.create_user(username="veh_sho", password="Correct-Horse-23!", role=Role.SHO)
        self.clerk = User.objects.create_user(username="veh_create_clerk", password="Correct-Horse-23!", role=Role.CLERK)

    def test_sho_can_create_a_vehicle(self):
        self.client.force_login(self.sho)
        response = self.client.post(reverse("vehicles:vehicle_create"), {
            "registration_number": "KHI-9999", "make": "Honda", "model": "City",
            "owner_name": "Tariq Iqbal", "owner_contact": "", "status": Vehicle.Status.NORMAL,
        })
        vehicle = Vehicle.objects.get(registration_number="KHI-9999")
        self.assertRedirects(response, reverse("vehicles:vehicle_detail", args=[vehicle.pk]))

    def test_clerk_cannot_create_a_vehicle(self):
        self.client.force_login(self.clerk)
        response = self.client.post(reverse("vehicles:vehicle_create"), {
            "registration_number": "KHI-8888", "make": "Honda", "model": "City",
            "owner_name": "Tariq Iqbal", "owner_contact": "", "status": Vehicle.Status.NORMAL,
        })
        self.assertRedirects(response, reverse("vehicles:vehicle_list"))
        self.assertFalse(Vehicle.objects.filter(registration_number="KHI-8888").exists())
