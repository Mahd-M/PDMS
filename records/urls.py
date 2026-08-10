from django.urls import path
from . import views

app_name = "records"

urlpatterns = [
    path("", views.record_list, name="record_list"),
    path("new/", views.record_create, name="record_create"),
    path("wanted/", views.wanted_list, name="wanted_list"),
    path("<int:pk>/", views.record_detail, name="record_detail"),
    path("<int:pk>/edit/", views.record_edit, name="record_edit"),
    path("<int:record_pk>/court-dates/new/", views.court_date_create, name="court_date_create"),
    path("court-dates/<int:pk>/edit/", views.court_date_edit, name="court_date_edit"),
]