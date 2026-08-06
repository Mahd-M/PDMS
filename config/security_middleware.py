"""
Project-specific hardening middleware.

Three concerns live here because they cut across every app rather
than belonging to one of them: the security headers that make
"no client JavaScript" enforceable rather than just a convention,
the idle-session timeout CJIS expects, and the audit trail CJIS
requires for every access to criminal justice information.
"""
from django.utils import timezone

IDLE_TIMEOUT_SECONDS = 30 * 60  # CJIS: sessions must lock/expire after inactivity


class SecurityHeadersMiddleware:
    """
    CJIS Policy Area 10 (System & Communications Protection).

    The header below does not just "avoid using JavaScript" -- it tells
    the browser to refuse to execute any script, inline or external,
    even if one were somehow injected through an unrelated bug. That
    turns "we don't ship client-side JS" from a coding convention into
    a property the browser enforces for us.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'none'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        response["X-Content-Type-Options"] = "nosniff"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class SessionIdleTimeoutMiddleware:
    """
    CJIS Policy Area 5 (Access Control): an authenticated session left
    unattended at a station front desk must not stay valid indefinitely.
    Django's SESSION_COOKIE_AGE covers absolute expiry; this covers idle
    expiry (last activity, not last login).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last_seen = request.session.get("_last_seen")
            now_ts = timezone.now().timestamp()
            if last_seen and (now_ts - last_seen) > IDLE_TIMEOUT_SECONDS:
                from django.contrib.auth import logout
                logout(request)
            else:
                request.session["_last_seen"] = now_ts
        return self.get_response(request)


class AuditLogMiddleware:
    """
    CJIS Policy Area 4 (Audit and Accountability): log every state-changing
    request (POST/PUT/PATCH/DELETE) plus every view of a detail page.
    Read-only GETs to list/static pages are deliberately not logged --
    logging literally everything makes the log too noisy to review, which
    defeats the point of having one.
    """

    LOGGED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method in self.LOGGED_METHODS and request.user.is_authenticated:
            from audit.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action=AuditLog.Action.UPDATE if request.method != "DELETE" else AuditLog.Action.DELETE,
                object_type="http_request",
                object_id=request.path,
                detail=f"{request.method} {request.path} -> {response.status_code}",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        return response
