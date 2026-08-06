from django.urls import path
from . import views

app_name = "cases"

urlpatterns = [
    path("", views.fir_list, name="fir_list"),
    path("new/", views.fir_create, name="fir_create"),
    path("<int:pk>/", views.fir_detail, name="fir_detail"),
    path("case/<int:pk>/status/", views.case_update_status, name="case_status"),
]
