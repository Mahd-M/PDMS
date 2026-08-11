from django.urls import path
from . import views

app_name = "missing_persons"

urlpatterns = [
    path("", views.person_list, name="person_list"),
    path("new/", views.person_create, name="person_create"),
    path("<int:pk>/", views.person_detail, name="person_detail"),
    path("<int:pk>/edit/", views.person_edit, name="person_edit"),
]