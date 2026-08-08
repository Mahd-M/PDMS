# records/admin.py
from django.contrib import admin
from .models import CriminalRecord, CourtDate

admin.site.register(CriminalRecord)
admin.site.register(CourtDate)