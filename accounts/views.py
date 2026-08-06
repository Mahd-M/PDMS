import io

import qrcode
from qrcode.image.pil import PilImage

from django.contrib.auth import authenticate, get_user_model, login as django_login, logout as django_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from audit.models import AuditLog
from .forms import LoginForm, TOTPForm

User = get_user_model()


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


def login_view(request):
    """
    Step 1 of authentication: username + password.

    Deliberately does NOT fully log the user in here -- CJIS Advanced
    Authentication requires a second factor before access to CJI is
    granted, so a password match only earns a "pending" session flag
    that step 2 (mfa_verify_view) must clear.
    """
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        try:
            candidate = User.objects.get(username=username)
        except User.DoesNotExist:
            candidate = None

        if candidate and candidate.is_locked_out():
            messages.error(request, "This account is temporarily locked due to repeated failed attempts.")
            AuditLog.objects.create(
                user=None, action=AuditLog.Action.LOGIN_FAILED, object_type="user",
                object_id=username, detail="Attempt while locked out", ip_address=_client_ip(request),
            )
            return render(request, "accounts/login.html", {"form": form})

        user = authenticate(request, username=username, password=password)
        if user is None:
            if candidate:
                candidate.register_failed_login(
                    max_attempts=settings.ACCOUNT_LOCKOUT_MAX_ATTEMPTS,
                    lockout_minutes=settings.ACCOUNT_LOCKOUT_MINUTES,
                )
            AuditLog.objects.create(
                user=None, action=AuditLog.Action.LOGIN_FAILED, object_type="user",
                object_id=username, detail="Bad credentials", ip_address=_client_ip(request),
            )
            messages.error(request, "Invalid username or password.")
            return render(request, "accounts/login.html", {"form": form})

        # Password correct -- hold in a pending state until MFA clears.
        request.session["pre_auth_user_id"] = user.pk
        if user.mfa_enabled:
            return redirect("accounts:mfa_verify")
        return redirect("accounts:mfa_setup")

    return render(request, "accounts/login.html", {"form": form})


def mfa_verify_view(request):
    """Step 2 of authentication: TOTP code from an authenticator app."""
    pre_auth_id = request.session.get("pre_auth_user_id")
    if not pre_auth_id:
        return redirect("accounts:login")
    user = User.objects.get(pk=pre_auth_id)

    form = TOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if user.verify_totp(form.cleaned_data["code"]):
            del request.session["pre_auth_user_id"]
            django_login(request, user)
            user.register_successful_login()
            request.session["_last_seen"] = timezone.now().timestamp()
            AuditLog.objects.create(
                user=user, action=AuditLog.Action.LOGIN, object_type="user",
                object_id=str(user.pk), ip_address=_client_ip(request),
            )
            return redirect(settings.LOGIN_REDIRECT_URL)
        messages.error(request, "Incorrect authenticator code.")

    return render(request, "accounts/mfa_verify.html", {"form": form})


def mfa_setup_view(request):
    """
    Shown once, right after first correct password entry, if the
    account has no authenticator enrolled yet. The QR code is a plain
    PNG <img> -- no client JS involved in rendering it.
    """
    pre_auth_id = request.session.get("pre_auth_user_id")
    if not pre_auth_id:
        return redirect("accounts:login")
    user = User.objects.get(pk=pre_auth_id)
    user.ensure_totp_secret()

    form = TOTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if user.verify_totp(form.cleaned_data["code"]):
            user.mfa_enabled = True
            user.save(update_fields=["mfa_enabled"])
            del request.session["pre_auth_user_id"]
            django_login(request, user)
            user.register_successful_login()
            request.session["_last_seen"] = timezone.now().timestamp()
            AuditLog.objects.create(
                user=user, action=AuditLog.Action.LOGIN, object_type="user",
                object_id=str(user.pk), detail="MFA enrolled", ip_address=_client_ip(request),
            )
            return redirect(settings.LOGIN_REDIRECT_URL)
        messages.error(request, "That code didn't match -- check the time on your device and try again.")

    return render(request, "accounts/mfa_setup.html", {"form": form})


def mfa_qr_code_view(request):
    """Serves the enrollment QR code as a PNG for the pending user only."""
    pre_auth_id = request.session.get("pre_auth_user_id")
    if not pre_auth_id:
        return HttpResponse(status=403)
    user = User.objects.get(pk=pre_auth_id)
    uri = user.totp_provisioning_uri(issuer="PDMS")

    img = qrcode.make(uri, image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


@login_required
def logout_view(request):
    AuditLog.objects.create(
        user=request.user, action=AuditLog.Action.LOGOUT, object_type="user",
        object_id=str(request.user.pk), ip_address=_client_ip(request),
    )
    django_logout(request)
    return redirect("accounts:login")
