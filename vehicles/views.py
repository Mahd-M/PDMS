from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from audit.models import AuditLog
from .forms import VehicleForm
from .models import Vehicle

# Investigation-linked, like CriminalRecord -- see note in the roadmap chat
# for why this differs from missing_persons/views.py::EDITOR_ROLES.
EDITOR_ROLES = (Role.ADMIN, Role.SHO, Role.INVESTIGATOR)


@login_required
def vehicle_list(request):
    vehicles = Vehicle.objects.all()
    page = Paginator(vehicles, 20).get_page(request.GET.get("page"))
    return render(request, "vehicles/vehicle_list.html", {"page": page})


@login_required
def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    AuditLog.objects.create(
        user=request.user, action=AuditLog.Action.VIEW, object_type="Vehicle",
        object_id=vehicle.registration_number, ip_address=request.META.get("REMOTE_ADDR"),
    )
    return render(request, "vehicles/vehicle_detail.html", {"vehicle": vehicle})


@login_required
def vehicle_create(request):
    if request.user.role not in EDITOR_ROLES:
        return redirect("vehicles:vehicle_list")
    form = VehicleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehicle = form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.CREATE, object_type="Vehicle",
            object_id=vehicle.registration_number, ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("vehicles:vehicle_detail", pk=vehicle.pk)
    return render(request, "vehicles/vehicle_form.html", {"form": form})


@login_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.user.role not in EDITOR_ROLES:
        return redirect("vehicles:vehicle_detail", pk=vehicle.pk)
    form = VehicleForm(request.POST or None, instance=vehicle)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="Vehicle",
            object_id=vehicle.registration_number, detail=f"status -> {vehicle.status}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("vehicles:vehicle_detail", pk=vehicle.pk)
    return render(request, "vehicles/vehicle_form.html", {"form": form, "vehicle": vehicle})
