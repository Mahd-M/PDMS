from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from audit.models import AuditLog
from .forms import CriminalRecordForm
from .models import CriminalRecord

# Who can create or edit a criminal record -- see note above this file
# in the roadmap chat for why this differs from cases/views.py::fir_create's role set.
EDITOR_ROLES = (Role.ADMIN, Role.SHO, Role.INVESTIGATOR)


@login_required
def record_list(request):
    records = CriminalRecord.objects.all()
    page = Paginator(records, 20).get_page(request.GET.get("page"))
    return render(request, "records/record_list.html", {"page": page})


@login_required
def record_detail(request, pk):
    record = get_object_or_404(CriminalRecord, pk=pk)
    AuditLog.objects.create(
        user=request.user, action=AuditLog.Action.VIEW, object_type="CriminalRecord",
        object_id=str(record.pk), ip_address=request.META.get("REMOTE_ADDR"),
    )
    return render(request, "records/record_detail.html", {"record": record})


@login_required
def record_create(request):
    if request.user.role not in EDITOR_ROLES:
        return redirect("records:record_list")
    form = CriminalRecordForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.CREATE, object_type="CriminalRecord",
            object_id=str(record.pk), ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("records:record_detail", pk=record.pk)
    return render(request, "records/record_form.html", {"form": form})


@login_required
def record_edit(request, pk):
    record = get_object_or_404(CriminalRecord, pk=pk)
    if request.user.role not in EDITOR_ROLES:
        return redirect("records:record_detail", pk=record.pk)
    form = CriminalRecordForm(request.POST or None, request.FILES or None, instance=record)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="CriminalRecord",
            object_id=str(record.pk), detail=f"status -> {record.status}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("records:record_detail", pk=record.pk)
    return render(request, "records/record_form.html", {"form": form, "record": record})