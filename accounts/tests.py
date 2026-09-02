import pyotp
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User


class MFAEnrollmentTests(TestCase):
    """
    Covers the mfa_setup_view path: a user with no authenticator
    enrolled yet gets a secret generated on first login and must enter
    a correct code before mfa_enabled flips on and the session becomes
    fully authenticated.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="enroll_test", password="Correct-Horse-1!", role=Role.CLERK)

    def test_password_correct_routes_to_mfa_setup_when_unenrolled(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "enroll_test", "password": "Correct-Horse-1!"},
        )
        self.assertRedirects(response, reverse("accounts:mfa_setup"))

    def test_correct_code_completes_enrollment_and_logs_in(self):
        self.client.post(reverse("accounts:login"), {"username": "enroll_test", "password": "Correct-Horse-1!"})
        self.client.get(reverse("accounts:mfa_setup"))  # ensures ensure_totp_secret() has run

        self.user.refresh_from_db()
        self.assertTrue(self.user.totp_secret)
        self.assertFalse(self.user.mfa_enabled)

        code = pyotp.TOTP(self.user.totp_secret).now()
        response = self.client.post(reverse("accounts:mfa_setup"), {"code": code}, follow=True)

        self.user.refresh_from_db()
        self.assertTrue(self.user.mfa_enabled)
        self.assertRedirects(response, reverse("dashboard:home"))

    def test_wrong_code_does_not_enable_mfa(self):
        self.client.post(reverse("accounts:login"), {"username": "enroll_test", "password": "Correct-Horse-1!"})
        self.client.get(reverse("accounts:mfa_setup"))
        response = self.client.post(reverse("accounts:mfa_setup"), {"code": "000000"})

        self.user.refresh_from_db()
        self.assertFalse(self.user.mfa_enabled)
        self.assertEqual(response.status_code, 200)


class MFAVerificationTests(TestCase):
    """Covers mfa_verify_view: an already-enrolled user's second factor."""

    def setUp(self):
        self.user = User.objects.create_user(username="verify_test", password="Correct-Horse-2!", role=Role.SHO)
        self.user.ensure_totp_secret()
        self.user.mfa_enabled = True
        self.user.save(update_fields=["mfa_enabled"])

    def test_password_correct_routes_to_mfa_verify_when_enrolled(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "verify_test", "password": "Correct-Horse-2!"},
        )
        self.assertRedirects(response, reverse("accounts:mfa_verify"))

    def test_correct_code_logs_in(self):
        self.client.post(reverse("accounts:login"), {"username": "verify_test", "password": "Correct-Horse-2!"})
        code = pyotp.TOTP(self.user.totp_secret).now()
        response = self.client.post(reverse("accounts:mfa_verify"), {"code": code}, follow=True)
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_wrong_code_is_rejected(self):
        self.client.post(reverse("accounts:login"), {"username": "verify_test", "password": "Correct-Horse-2!"})
        response = self.client.post(reverse("accounts:mfa_verify"), {"code": "000000"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class AccountLockoutTests(TestCase):
    """CJIS: an account must lock after repeated failed attempts, even with the right password after that point."""

    def setUp(self):
        self.user = User.objects.create_user(username="lockout_test", password="Correct-Horse-3!", role=Role.CLERK)

    def test_five_failed_attempts_locks_the_account(self):
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": "lockout_test", "password": "wrong"})

        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 5)
        self.assertTrue(self.user.is_locked_out())

    def test_locked_account_rejects_even_the_correct_password(self):
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"username": "lockout_test", "password": "wrong"})

        response = self.client.post(
            reverse("accounts:login"), {"username": "lockout_test", "password": "Correct-Horse-3!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_successful_login_resets_the_failed_counter(self):
        for _ in range(3):
            self.client.post(reverse("accounts:login"), {"username": "lockout_test", "password": "wrong"})

        # register_successful_login() only fires once authentication is
        # *fully* complete -- a correct password alone earns a pending
        # session, not a reset counter, so the flow has to run through
        # MFA (this user has none enrolled yet) before the reset happens.
        self.client.post(reverse("accounts:login"), {"username": "lockout_test", "password": "Correct-Horse-3!"})
        self.client.get(reverse("accounts:mfa_setup"))
        self.user.refresh_from_db()
        code = pyotp.TOTP(self.user.totp_secret).now()
        self.client.post(reverse("accounts:mfa_setup"), {"code": code})

        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_attempts, 0)
        self.assertIsNone(self.user.locked_until)
