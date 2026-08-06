from django.urls import path
from . import views

app_name = "evidence"

urlpatterns = [
    path("case/<int:case_pk>/upload/", views.evidence_upload, name="upload"),
    path("<int:pk>/", views.evidence_detail, name="detail"),
]
