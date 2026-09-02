from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from .hashchain import verify_chain
from .models import AuditLog


class AuditLogHashChainTests(TestCase):
    """
    The append-only, tamper-evident log at the heart of CJIS Policy
    Area 4: each row's hash covers the previous row's hash plus its
    own content, so corrupting any past row -- even by going straight
    at the table with SQL, bypassing the model entirely -- must make
    verify_chain() detect it.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="audit_actor", password="Correct-Horse-4!", role=Role.ADMIN)

    def _create_chain(self, count=5):
        for i in range(count):
            AuditLog.objects.create(
                user=self.user, action=AuditLog.Action.VIEW, object_type="FIR",
                object_id=f"FIR-{i}", ip_address="127.0.0.1",
            )
        return list(AuditLog.objects.order_by("id"))

    def test_intact_chain_verifies(self):
        rows = self._create_chain()
        ok, bad_pk = verify_chain(rows, lambda r: r._content_fields())
        self.assertTrue(ok)
        self.assertIsNone(bad_pk)

    def test_corrupting_a_row_directly_via_sql_is_detected(self):
        rows = self._create_chain()
        tampered = rows[2]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE audit_auditlog SET detail = %s WHERE id = %s",
                ["tampered after the fact", tampered.pk],
            )

        fresh_rows = list(AuditLog.objects.order_by("id"))
        ok, bad_pk = verify_chain(fresh_rows, lambda r: r._content_fields())
        self.assertFalse(ok)
        self.assertEqual(bad_pk, tampered.pk)

    def test_rows_cannot_be_edited_through_the_model(self):
        entry = AuditLog.objects.create(
            user=self.user, action=AuditLog.Action.VIEW, object_type="FIR", object_id="FIR-1",
        )
        entry.detail = "edited"
        with self.assertRaises(ValueError):
            entry.save()

    def test_rows_cannot_be_deleted(self):
        entry = AuditLog.objects.create(
            user=self.user, action=AuditLog.Action.VIEW, object_type="FIR", object_id="FIR-1",
        )
        with self.assertRaises(ValueError):
            entry.delete()
        self.assertTrue(AuditLog.objects.filter(pk=entry.pk).exists())


class AuditLogMiddlewareTests(TestCase):
    """
    Business views don't all call AuditLog.objects.create() themselves
    (evidence_upload doesn't, for instance) -- state-changing requests
    are caught generically by AuditLogMiddleware instead. This confirms
    that safety net actually fires on a real POST.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="mw_actor", password="Correct-Horse-5!", role=Role.ADMIN)
        self.client.force_login(self.user)

    def test_post_request_is_logged_by_the_middleware(self):
        # logout_view is a poor probe for this: it calls django_logout()
        # -- which flips request.user to AnonymousUser -- before the
        # middleware's post-response check runs, so it evades the net
        # (it's separately audited by its own explicit AuditLog.create
        # call). mark_attendance stays authenticated end to end, so it
        # actually exercises the generic safety net.
        before = AuditLog.objects.filter(object_type="http_request").count()
        self.client.post(reverse("personnel:mark_attendance"), {"date": timezone.localdate().isoformat()})
        after = AuditLog.objects.filter(object_type="http_request").count()
        self.assertGreater(after, before)

    def test_get_request_is_not_logged_by_the_middleware(self):
        self.client.get(reverse("dashboard:home"))
        self.assertFalse(AuditLog.objects.filter(object_type="http_request", object_id="/dashboard/").exists())
