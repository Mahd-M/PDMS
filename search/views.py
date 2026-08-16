from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from cases.views import visible_firs_for
from missing_persons.models import MissingPerson
from records.models import CriminalRecord
from vehicles.views import visible_vehicles_for


@login_required
def search_results(request):
    q = request.GET.get("q", "").strip()
    results = {"firs": [], "criminal_records": [], "vehicles": [], "missing_persons": []}

    if q:
        # FIR number and vehicle registration are plain, indexed columns --
        # a normal database-level filter, going through the same
        # visible_firs_for / visible_vehicles_for row-level security every
        # other view in these apps uses, so search can't leak a sealed FIR
        # or a vehicle tied to one.
        results["firs"] = list(visible_firs_for(request.user).filter(fir_number__icontains=q))
        results["vehicles"] = list(visible_vehicles_for(request.user).filter(registration_number__icontains=q))

        # full_name / cnic are encrypted at rest (config/encrypted_fields.py).
        # Fernet ciphertext can't be matched with a database-level icontains --
        # each row is decrypted on read and matched in memory instead.
        # CriminalRecord/MissingPerson have no sealed-style visibility
        # restriction anywhere else in the app (record_list/person_list show
        # all of them to any authenticated user), so none is added here either.
        q_lower = q.lower()
        results["criminal_records"] = [
            r for r in CriminalRecord.objects.all()
            if q_lower in r.full_name.lower() or q_lower in r.cnic.lower()
        ]
        results["missing_persons"] = [
            p for p in MissingPerson.objects.all()
            if q_lower in p.full_name.lower()
        ]

    return render(request, "search/results.html", {"q": q, "results": results})
