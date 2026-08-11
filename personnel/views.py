from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Role
from audit.models import AuditLog
from .forms import AssignmentForm
from .models import Assignment, Officer, OfficerAttendance

# Covers both attendance-marking (Step 26) and assignment editing (Step 27) --
# renamed from ATTENDANCE_MARKER_ROLES now that a second view needs the same gate.
SUPERVISOR_ROLES = (Role.ADMIN, Role.SHO)


@login_required
def roster(request):
    officers = Officer.objects.select_related("user").filter(active=True).order_by("station", "rank")
    return render(request, "personnel/roster.html", {"officers": officers})


@login_required
def officer_detail(request, pk):
    officer = get_object_or_404(Officer.objects.select_related("user"), pk=pk)
    assignments = officer.assignments.all()
    return render(request, "personnel/officer_detail.html", {"officer": officer, "assignments": assignments})


@login_required
def mark_attendance(request):
    if request.user.role not in SUPERVISOR_ROLES:
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


@login_required
def assignment_create(request, officer_pk):
    officer = get_object_or_404(Officer, pk=officer_pk)
    if request.user.role not in SUPERVISOR_ROLES:
        return redirect("personnel:officer_detail", pk=officer.pk)
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.officer = officer
        assignment.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.CREATE, object_type="Assignment",
            object_id=str(assignment.pk), ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("personnel:officer_detail", pk=officer.pk)
    return render(request, "personnel/assignment_form.html", {"form": form, "officer": officer})


@login_required
def assignment_edit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    officer = assignment.officer
    if request.user.role not in SUPERVISOR_ROLES:
        return redirect("personnel:officer_detail", pk=officer.pk)
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="Assignment",
            object_id=str(assignment.pk), ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("personnel:officer_detail", pk=officer.pk)
    return render(request, "personnel/assignment_form.html", {"form": form, "officer": officer, "assignment": assignment})
