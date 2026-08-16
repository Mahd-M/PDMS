from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_index, name="index"),
    path("crime-statistics/", views.crime_statistics, name="crime_statistics"),
    path("monthly/", views.monthly_report, name="monthly_report"),
    path("officers/", views.officer_report, name="officer_report"),
    path("cases/", views.case_report, name="case_report"),
]
