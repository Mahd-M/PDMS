from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from cases.models import Case
from .forms import EvidenceUploadForm
from .models import ChainOfCustodyEntry, Evidence


@login_required
def evidence_upload(request, case_pk):
    case = get_object_or_404(Case, pk=case_pk)
    form = EvidenceUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.case = case
        item.uploaded_by = request.user
        item.save()  # hash + first custody entry are recorded inside Evidence.save()
        return redirect("evidence:detail", pk=item.pk)
    return render(request, "evidence/upload.html", {"form": form, "case": case})


@login_required
def evidence_detail(request, pk):
    item = get_object_or_404(Evidence, pk=pk)
    ChainOfCustodyEntry.record(item, action=ChainOfCustodyEntry.Action.ACCESSED, actor=request.user)
    custody_log = item.custody_log.select_related("actor").all()
    return render(request, "evidence/detail.html", {"item": item, "custody_log": custody_log})
