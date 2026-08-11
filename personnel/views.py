from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import Role
from audit.models import AuditLog
from .models import Officer, OfficerAttendance

ATTENDANCE_MARKER_ROLES = (Role.ADMIN, Role.SHO)


@login_required
def roster(request):
    officers = Officer.objects.select_related("user").filter(active=True).order_by("station", "rank")
    return render(request, "personnel/roster.html", {"officers": officers})


@login_required
def mark_attendance(request):
    if request.user.role not in ATTENDANCE_MARKER_ROLES:
        return redirect("personnel:roster")

    if request.method == "POST":
        selected_date = request.POST.get("date") or timezone.localdate().isoformat()
        officers = Officer.objects.filter(active=True)
        for officer in officers:
            status = request.POST.get(f"status_{officer.pk}")
            if status in OfficerAttendance.Status.values:
                OfficerAttendance.objects.update_or_create(
                    officer=officer, date=selected_date,
                    defaults={"status": status, "marked_by": request.user},
                )
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="OfficerAttendance",
            object_id=selected_date, ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect(f"{request.path}?date={selected_date}")

    selected_date = request.GET.get("date") or timezone.localdate().isoformat()
    officers = Officer.objects.select_related("user").filter(active=True).order_by("station", "rank")
    existing = {a.officer_id: a.status for a in OfficerAttendance.objects.filter(date=selected_date)}
    rows = [{"officer": o, "current_status": existing.get(o.pk, "")} for o in officers]

    return render(request, "personnel/attendance_form.html", {
        "rows": rows,
        "selected_date": selected_date,
        "status_choices": OfficerAttendance.Status.choices,
    })
