import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from audit.hashchain import verify_chain
from cases.models import Case, FIR
from .models import ChainOfCustodyEntry, Evidence
from .views import visible_evidence_for

TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="pdms_evidence_test_")


def make_fir_and_case(number, sealed, filed_by):
    fir = FIR.objects.create(
        fir_number=number, station="Saddar", sections_of_law="PPC 379",
        complainant_name="Test Complainant", narrative="Test narrative.",
        is_sealed=sealed, filed_by=filed_by,
    )
    return Case.objects.create(fir=fir)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class EvidenceHashingTests(TestCase):
    """
    The SHA-256 fingerprint is computed once at upload and never
    recomputed -- that's what lets a later integrity check detect a
    swapped or corrupted file. It also kicks off the first
    chain-of-custody entry ("received").
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.officer = User.objects.create_user(username="ev_officer", password="Correct-Horse-9!", role=Role.INVESTIGATOR)
        self.case = make_fir_and_case("FIR-EV-1", sealed=False, filed_by=self.officer)

    def test_sha256_is_computed_on_save(self):
        item = Evidence.objects.create(
            case=self.case, description="Recovered phone", evidence_type=Evidence.EvidenceType.DOCUMENT,
            file=SimpleUploadedFile("note.txt", b"hello evidence world"), uploaded_by=self.officer,
        )
        import hashlib
        expected = hashlib.sha256(b"hello evidence world").hexdigest()
        self.assertEqual(item.sha256_hash, expected)

    def test_first_custody_entry_is_recorded_on_upload(self):
        item = Evidence.objects.create(
            case=self.case, description="Recovered phone", evidence_type=Evidence.EvidenceType.DOCUMENT,
            file=SimpleUploadedFile("note.txt", b"hello evidence world"), uploaded_by=self.officer,
        )
        entries = list(item.custody_log.all())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].action, ChainOfCustodyEntry.Action.RECEIVED)
        self.assertEqual(entries[0].actor, self.officer)

    def test_viewing_evidence_adds_an_accessed_custody_entry(self):
        item = Evidence.objects.create(
            case=self.case, description="Recovered phone", evidence_type=Evidence.EvidenceType.DOCUMENT,
            file=SimpleUploadedFile("note.txt", b"hello evidence world"), uploaded_by=self.officer,
        )
        self.client.force_login(self.officer)
        self.client.get(reverse("evidence:detail", args=[item.pk]))
        actions = list(item.custody_log.values_list("action", flat=True))
        self.assertEqual(actions, [ChainOfCustodyEntry.Action.RECEIVED, ChainOfCustodyEntry.Action.ACCESSED])


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ChainOfCustodyHashChainTests(TestCase):
    """Same tamper-evidence guarantee as AuditLog, but scoped per exhibit."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.officer = User.objects.create_user(username="coc_officer", password="Correct-Horse-10!", role=Role.INVESTIGATOR)
        self.case = make_fir_and_case("FIR-EV-2", sealed=False, filed_by=self.officer)
        self.item = Evidence.objects.create(
            case=self.case, description="Bloodied knife", evidence_type=Evidence.EvidenceType.DNA,
            file=SimpleUploadedFile("sample.txt", b"chain of custody test"), uploaded_by=self.officer,
        )

    def _extractor(self, entry):
        return (str(entry.evidence_id), entry.action, str(entry.actor_id), entry.note)

    def test_intact_chain_verifies(self):
        ChainOfCustodyEntry.record(self.item, action=ChainOfCustodyEntry.Action.TRANSFERRED, actor=self.officer, note="to lab")
        rows = list(ChainOfCustodyEntry.objects.filter(evidence=self.item).order_by("id"))
        ok, bad_pk = verify_chain(rows, self._extractor)
        self.assertTrue(ok)
        self.assertIsNone(bad_pk)

    def test_corrupting_an_entry_directly_via_sql_is_detected(self):
        ChainOfCustodyEntry.record(self.item, action=ChainOfCustodyEntry.Action.TRANSFERRED, actor=self.officer, note="to lab")
        rows = list(ChainOfCustodyEntry.objects.filter(evidence=self.item).order_by("id"))
        tampered = rows[0]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE evidence_chainofcustodyentry SET note = %s WHERE id = %s",
                ["forged", tampered.pk],
            )
        fresh_rows = list(ChainOfCustodyEntry.objects.filter(evidence=self.item).order_by("id"))
        ok, bad_pk = verify_chain(fresh_rows, self._extractor)
        self.assertFalse(ok)
        self.assertEqual(bad_pk, tampered.pk)

    def test_entries_cannot_be_edited(self):
        entry = self.item.custody_log.first()
        entry.note = "edited"
        with self.assertRaises(ValueError):
            entry.save()

    def test_entries_cannot_be_deleted(self):
        entry = self.item.custody_log.first()
        with self.assertRaises(ValueError):
            entry.delete()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class EvidenceVisibilityTests(TestCase):
    """visible_evidence_for mirrors visible_firs_for -- evidence on a sealed FIR must not leak to a clerk."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.admin = User.objects.create_user(username="ev_admin", password="Correct-Horse-11!", role=Role.ADMIN)
        self.clerk = User.objects.create_user(username="ev_clerk", password="Correct-Horse-11!", role=Role.CLERK)
        sealed_case = make_fir_and_case("FIR-EV-SEALED", sealed=True, filed_by=self.admin)
        plain_case = make_fir_and_case("FIR-EV-PLAIN", sealed=False, filed_by=self.admin)
        self.sealed_item = Evidence.objects.create(
            case=sealed_case, description="Sealed exhibit", file=SimpleUploadedFile("a.txt", b"a"), uploaded_by=self.admin,
        )
        self.plain_item = Evidence.objects.create(
            case=plain_case, description="Plain exhibit", file=SimpleUploadedFile("b.txt", b"b"), uploaded_by=self.admin,
        )

    def test_clerk_does_not_see_evidence_on_a_sealed_fir(self):
        visible = set(visible_evidence_for(self.clerk).values_list("description", flat=True))
        self.assertEqual(visible, {"Plain exhibit"})

    def test_admin_sees_all_evidence(self):
        visible = set(visible_evidence_for(self.admin).values_list("description", flat=True))
        self.assertEqual(visible, {"Sealed exhibit", "Plain exhibit"})

    def test_clerk_gets_404_on_sealed_evidence_detail(self):
        self.client.force_login(self.clerk)
        response = self.client.get(reverse("evidence:detail", args=[self.sealed_item.pk]))
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class EvidenceUploadViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.officer = User.objects.create_user(username="upload_officer", password="Correct-Horse-12!", role=Role.INVESTIGATOR)
        self.case = make_fir_and_case("FIR-EV-UPLOAD", sealed=False, filed_by=self.officer)

    def test_upload_creates_evidence_with_hash_and_custody_entry(self):
        self.client.force_login(self.officer)
        response = self.client.post(
            reverse("evidence:upload", args=[self.case.pk]),
            {
                "description": "Weapon recovered at scene",
                "evidence_type": Evidence.EvidenceType.PHOTO,
                "storage_location": "Locker A",
                "file": SimpleUploadedFile("weapon.jpg", b"fake image bytes"),
            },
        )
        item = Evidence.objects.get(description="Weapon recovered at scene")
        # assertRedirects follows the redirect by default to confirm the
        # target loads, which itself fires evidence_detail's "accessed"
        # custody entry -- so the meaningful check is that exactly one
        # "received" entry exists, not that the log has exactly one row.
        self.assertRedirects(response, reverse("evidence:detail", args=[item.pk]))
        self.assertTrue(item.sha256_hash)
        self.assertEqual(item.custody_log.filter(action=ChainOfCustodyEntry.Action.RECEIVED).count(), 1)
