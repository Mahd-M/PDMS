from django.contrib import admin
from .models import Assignment, Officer, OfficerAttendance

admin.site.register(Officer)
admin.site.register(OfficerAttendance)
admin.site.register(Assignment)
