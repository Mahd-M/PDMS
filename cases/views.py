from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from audit.models import AuditLog
from .forms import CaseStatusForm, FIRForm
from .models import FIR, Case


def visible_firs_for(user):
    """
    Row-level visibility, enforced here in the ORM for the demo.

    In the production Postgres deployment this exact policy is also
    expressed as a `CREATE POLICY` row-level security rule on the
    `cases_fir` table (see docs/DATABASE.md), so the restriction holds
    even for a raw SQL client that bypasses this application entirely.
    Application-layer + database-layer enforcement of the same rule is
    the "defense in depth" CJIS auditors specifically look for.
    """
    qs = FIR.objects.all()
    if user.role in (Role.ADMIN, Role.AUDITOR):
        return qs
    if user.role == Role.SHO:
        return qs
    if user.role == Role.INVESTIGATOR:
        return qs.filter(case__assigned_officer=user) | qs.filter(is_sealed=False)
    # Records clerks: no sealed FIRs, full stop.
    return qs.filter(is_sealed=False)


@login_required
def fir_list(request):
    firs = visible_firs_for(request.user).select_related("case")
    page = Paginator(firs, 20).get_page(request.GET.get("page"))
    return render(request, "cases/fir_list.html", {"page": page})


@login_required
def fir_detail(request, pk):
    fir = get_object_or_404(visible_firs_for(request.user), pk=pk)
    AuditLog.objects.create(
        user=request.user, action=AuditLog.Action.VIEW, object_type="FIR",
        object_id=fir.fir_number, ip_address=request.META.get("REMOTE_ADDR"),
    )
    return render(request, "cases/fir_detail.html", {"fir": fir})


@login_required
def fir_create(request):
    if request.user.role not in (Role.ADMIN, Role.SHO, Role.CLERK):
        return redirect("cases:fir_list")
    form = FIRForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fir = form.save(commit=False)
        fir.filed_by = request.user
        fir.save()
        Case.objects.create(fir=fir)
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.CREATE, object_type="FIR",
            object_id=fir.fir_number, ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("cases:fir_detail", pk=fir.pk)
    return render(request, "cases/fir_form.html", {"form": form})


@login_required
def case_update_status(request, pk):
    case = get_object_or_404(Case, pk=pk)
    if request.user.role not in (Role.ADMIN, Role.SHO, Role.INVESTIGATOR):
        return redirect("cases:fir_detail", pk=case.fir_id)
    form = CaseStatusForm(request.POST or None, instance=case)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="Case",
            object_id=str(case.pk), detail=f"status -> {case.status}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("cases:fir_detail", pk=case.fir_id)
    return render(request, "cases/case_status_form.html", {"form": form, "case": case})


def case_status_breakdown(cases_queryset):
    """
    Shared by the dashboard and the reports app -- both need the exact
    same "count by status, express as a 5%-stepped bar width" shape,
    just over different querysets (all visible cases vs. a date-filtered
    subset). One function means the two can't silently drift apart.
    """
    status_counts = []
    total = cases_queryset.count() or 1
    for value, label in Case.Status.choices:
        count = cases_queryset.filter(status=value).count()
        status_counts.append({
            "label": label,
            "count": count,
            "bar_width_pct": round(100 * count / total / 5) * 5,
        })
    return status_counts
