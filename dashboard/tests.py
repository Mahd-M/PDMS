from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from cases.models import Case, FIR
from personnel.models import Officer, OfficerAttendance


class DashboardHomeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="dash_admin", password="Correct-Horse-24!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="dash_clerk", password="Correct-Horse-24!", role=Role.CLERK)

        sealed_fir = FIR.objects.create(
            fir_number="FIR-DASH-SEALED", station="Saddar", sections_of_law="PPC 379",
            complainant_name="X", narrative="n", is_sealed=True, filed_by=self.admin,
        )
        Case.objects.create(fir=sealed_fir, status=Case.Status.OPEN)
        plain_fir = FIR.objects.create(
            fir_number="FIR-DASH-PLAIN", station="Saddar", sections_of_law="PPC 379",
            complainant_name="X", narrative="n", is_sealed=False, filed_by=self.admin,
        )
        Case.objects.create(fir=plain_fir, status=Case.Status.CLOSED)

        officer_user = User.objects.create_user(username="dash_officer", password="Correct-Horse-24!", role=Role.INVESTIGATOR)
        officer = Officer.objects.create(user=officer_user, rank="Constable", station="Saddar")
        OfficerAttendance.objects.create(officer=officer, date=timezone.localdate(), status=OfficerAttendance.Status.PRESENT, marked_by=self.admin)

    def test_admin_sees_both_firs_and_status_breakdown(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_firs"], 2)
        status_counts = {row["label"]: row["count"] for row in response.context["status_counts"]}
        self.assertEqual(status_counts["Open"], 1)
        self.assertEqual(status_counts["Closed"], 1)

    def test_clerk_never_sees_the_sealed_fir_in_recent_firs(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("dashboard:home"))
        recent_numbers = [fir.fir_number for fir in response.context["recent_firs"]]
        self.assertNotIn("FIR-DASH-SEALED", recent_numbers)
        self.assertIn("FIR-DASH-PLAIN", recent_numbers)

    def test_attendance_today_counts_are_real(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        attendance = response.context["attendance_today"]
        self.assertEqual(attendance["present"], 1)
        self.assertEqual(attendance["absent"], 0)


class AccessibilitySettingsTests(TestCase):
    def test_reachable_without_login(self):
        response = self.client.get(reverse("dashboard:accessibility_settings"))
        self.assertEqual(response.status_code, 200)

    def test_submitting_sets_both_cookies_and_redirects_to_next(self):
        response = self.client.get(
            reverse("dashboard:accessibility_settings"),
            {"save": "1", "large_text": "on", "high_contrast": "on", "next": "/accounts/login/"},
        )
        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)
        self.assertEqual(response.cookies["large_text"].value, "1")
        self.assertEqual(response.cookies["high_contrast"].value, "1")

    def test_unchecking_a_box_clears_only_that_cookie(self):
        self.client.cookies["large_text"] = "1"
        self.client.cookies["high_contrast"] = "1"
        response = self.client.get(reverse("dashboard:accessibility_settings"), {"save": "1", "large_text": "on"})
        self.assertEqual(response.cookies["large_text"].value, "1")
        self.assertEqual(response.cookies["high_contrast"].value, "")

    def test_external_next_url_is_rejected(self):
        response = self.client.get(
            reverse("dashboard:accessibility_settings"), {"save": "1", "next": "https://evil.example.com/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/dashboard/"))

    def test_body_carries_cookie_derived_classes_on_the_next_page(self):
        self.client.cookies["large_text"] = "1"
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, '<body class="large-text ">')
