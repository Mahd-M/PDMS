from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("accessibility/", views.accessibility_settings, name="accessibility_settings"),
]
