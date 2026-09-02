from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from cases.models import Case, FIR


def make_fir_and_case(number, sealed, filed_by, status=Case.Status.OPEN):
    fir = FIR.objects.create(
        fir_number=number, station="Saddar", sections_of_law="PPC 379",
        complainant_name="X", narrative="n", is_sealed=sealed, filed_by=filed_by,
    )
    return Case.objects.create(fir=fir, status=status)


class ReportsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="rep_admin", password="Correct-Horse-25!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="rep_clerk", password="Correct-Horse-25!", role=Role.CLERK)
        make_fir_and_case("FIR-REP-SEALED", sealed=True, filed_by=self.admin, status=Case.Status.OPEN)
        make_fir_and_case("FIR-REP-PLAIN", sealed=False, filed_by=self.admin, status=Case.Status.CLOSED)

    def test_index_renders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:index"))
        self.assertEqual(response.status_code, 200)

    def test_crime_statistics_default_range_renders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:crime_statistics"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 2)

    def test_malformed_date_range_does_not_500(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:crime_statistics") + "?start=nonsense&end=also-nonsense")
        self.assertEqual(response.status_code, 200)

    def test_empty_date_range_shows_no_results_without_erroring(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:crime_statistics") + "?start=1990-01-01&end=1990-01-02")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total"], 0)

    def test_clerk_sees_fewer_firs_than_admin_because_sealed_is_excluded(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("reports:crime_statistics"))
        self.assertEqual(response.context["total"], 1)

    def test_case_report_status_breakdown_matches_dashboard(self):
        self.client.force_login(self.admin)
        dashboard_response = self.client.get(reverse("dashboard:home"))
        report_response = self.client.get(reverse("reports:case_report") + "?start=2000-01-01&end=2030-01-01")

        dashboard_counts = {row["label"]: row["count"] for row in dashboard_response.context["status_counts"]}
        report_counts = {row["label"]: row["count"] for row in report_response.context["status_counts"]}
        self.assertEqual(dashboard_counts, report_counts)

    def test_monthly_and_officer_reports_render(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("reports:monthly_report")).status_code, 200)
        self.assertEqual(self.client.get(reverse("reports:officer_report")).status_code, 200)
