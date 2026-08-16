from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q
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
        # fir_number/registration_number are identifiers, not prose -- full-text
        # search tokenizes into lexemes, which breaks substring matching (e.g.
        # "2026-0000" against "FIR-2026-000001"), so those two stay on icontains.
        # station/sections_of_law/narrative and make/model are genuine free text,
        # so those get real Postgres full-text search, ranked and OR'd with the
        # icontains branch. Both go through visible_firs_for/visible_vehicles_for
        # so search can't leak a sealed FIR or a vehicle tied to one.
        query = SearchQuery(q)

        fir_vector = SearchVector("station", "sections_of_law", "narrative")
        results["firs"] = list(
            visible_firs_for(request.user)
            .annotate(search=fir_vector, rank=SearchRank(fir_vector, query))
            .filter(Q(fir_number__icontains=q) | Q(search=query))
            .order_by("-rank")
        )

        vehicle_vector = SearchVector("make", "model")
        results["vehicles"] = list(
            visible_vehicles_for(request.user)
            .annotate(search=vehicle_vector, rank=SearchRank(vehicle_vector, query))
            .filter(Q(registration_number__icontains=q) | Q(search=query))
            .order_by("-rank")
        )

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
