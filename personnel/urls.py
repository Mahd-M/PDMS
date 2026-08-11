from django.urls import path
from . import views

app_name = "personnel"

urlpatterns = [
    path("", views.roster, name="roster"),
    path("attendance/", views.mark_attendance, name="mark_attendance"),
    path("<int:pk>/", views.officer_detail, name="officer_detail"),
    path("<int:officer_pk>/assignments/new/", views.assignment_create, name="assignment_create"),
    path("assignments/<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
]
