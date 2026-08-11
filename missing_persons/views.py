from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from audit.models import AuditLog
from .forms import MissingPersonForm
from .models import MissingPerson

# Intake-driven, like FIR filing -- see note in the roadmap chat for why
# this differs from records/views.py::EDITOR_ROLES.
EDITOR_ROLES = (Role.ADMIN, Role.SHO, Role.CLERK)


@login_required
def person_list(request):
    people = MissingPerson.objects.all()
    page = Paginator(people, 20).get_page(request.GET.get("page"))
    return render(request, "missing_persons/person_list.html", {"page": page})


@login_required
def person_detail(request, pk):
    person = get_object_or_404(MissingPerson, pk=pk)
    AuditLog.objects.create(
        user=request.user, action=AuditLog.Action.VIEW, object_type="MissingPerson",
        object_id=str(person.pk), ip_address=request.META.get("REMOTE_ADDR"),
    )
    return render(request, "missing_persons/person_detail.html", {"person": person})


@login_required
def person_create(request):
    if request.user.role not in EDITOR_ROLES:
        return redirect("missing_persons:person_list")
    form = MissingPersonForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.CREATE, object_type="MissingPerson",
            object_id=str(person.pk), ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("missing_persons:person_detail", pk=person.pk)
    return render(request, "missing_persons/person_form.html", {"form": form})


@login_required
def person_edit(request, pk):
    person = get_object_or_404(MissingPerson, pk=pk)
    if request.user.role not in EDITOR_ROLES:
        return redirect("missing_persons:person_detail", pk=person.pk)
    form = MissingPersonForm(request.POST or None, request.FILES or None, instance=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        AuditLog.objects.create(
            user=request.user, action=AuditLog.Action.UPDATE, object_type="MissingPerson",
            object_id=str(person.pk), detail=f"status -> {person.status}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return redirect("missing_persons:person_detail", pk=person.pk)
    return render(request, "missing_persons/person_form.html", {"form": form, "person": person})