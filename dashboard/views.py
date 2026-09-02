from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from cases.models import Case
from cases.views import case_status_breakdown, visible_firs_for
from personnel.models import Officer, OfficerAttendance

ACCESSIBILITY_COOKIE_NAMES = ("large_text", "high_contrast")


@login_required
def home(request):
    """
    A server-rendered dashboard: every number and every bar in the
    chart is computed in Python and sent down as plain HTML/SVG. There
    is no charting library, no fetch call, and no client-side redraw --
    the whole page is disposable and regenerated on every request.
    """
    visible_firs = visible_firs_for(request.user)
    cases = Case.objects.filter(fir__in=visible_firs)
    status_counts = case_status_breakdown(cases)

    # Recent FIRs stays scoped through the same RBAC every other FIR
    # view uses -- a "recent activity" widget is exactly the kind of
    # thing that's easy to accidentally build unfiltered.
    recent_firs = visible_firs.order_by("-date_filed")[:5]

    today = timezone.localdate()
    today_attendance = OfficerAttendance.objects.filter(date=today)
    attendance_today = {
        "date": today,
        "present": today_attendance.filter(status=OfficerAttendance.Status.PRESENT).count(),
        "absent": today_attendance.filter(status=OfficerAttendance.Status.ABSENT).count(),
        "leave": today_attendance.filter(status=OfficerAttendance.Status.LEAVE).count(),
        "not_marked": Officer.objects.filter(active=True).exclude(
            pk__in=today_attendance.values_list("officer_id", flat=True)
        ).count(),
    }

    return render(request, "dashboard/home.html", {
        "total_cases": cases.count(),
        "total_firs": visible_firs.count(),
        "status_counts": status_counts,
        "recent_firs": recent_firs,
        "attendance_today": attendance_today,
    })


def accessibility_settings(request):
    """
    Deliberately not @login_required: someone who needs large text or
    high contrast to read comfortably needs that *before* they can
    read the login form, not just after. The whole toggle is a GET
    form -- checking a box and submitting is a normal page load with
    the choices in the query string, not an onclick handler -- so the
    cookie it sets is available to every page (including login.html,
    which also extends base.html) on the very next request.
    """
    fallback = reverse("dashboard:home")
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or fallback
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = fallback

    if "save" in request.GET:
        response = redirect(next_url)
        for name in ACCESSIBILITY_COOKIE_NAMES:
            if request.GET.get(name):
                response.set_cookie(
                    name, "1", max_age=60 * 60 * 24 * 365,
                    samesite="Strict", secure=settings.SESSION_COOKIE_SECURE,
                )
            else:
                response.delete_cookie(name)
        return response

    return render(request, "dashboard/accessibility_settings.html", {
        "large_text": request.COOKIES.get("large_text") == "1",
        "high_contrast": request.COOKIES.get("high_contrast") == "1",
        "next_url": next_url,
    })
