from django.urls import path
from . import views

app_name = "vehicles"

urlpatterns = [
    path("", views.vehicle_list, name="vehicle_list"),
    path("new/", views.vehicle_create, name="vehicle_create"),
    path("<int:pk>/", views.vehicle_detail, name="vehicle_detail"),
    path("<int:pk>/edit/", views.vehicle_edit, name="vehicle_edit"),
]
