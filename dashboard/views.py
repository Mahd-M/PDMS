from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from cases.models import Case
from cases.views import case_status_breakdown, visible_firs_for
from personnel.models import Officer, OfficerAttendance


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
