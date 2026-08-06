from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("mfa/verify/", views.mfa_verify_view, name="mfa_verify"),
    path("mfa/setup/", views.mfa_setup_view, name="mfa_setup"),
    path("mfa/qr.png", views.mfa_qr_code_view, name="mfa_qr"),
    path("logout/", views.logout_view, name="logout"),
]
