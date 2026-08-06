from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Officer


@login_required
def roster(request):
    officers = Officer.objects.select_related("user").filter(active=True).order_by("station", "rank")
    return render(request, "personnel/roster.html", {"officers": officers})
