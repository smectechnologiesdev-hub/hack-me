from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    # The single password login endpoint — browser form AND brute-force target.
    path("login/", views.PortalLoginView.as_view(), name="login"),
    # OTP sign-in: page + the two script-friendly (CSRF-exempt) API steps.
    path("login/otp/", views.OtpLoginPageView.as_view(), name="otp_login"),
    path("login/otp/request/", views.OtpRequestView.as_view(), name="otp_request"),
    path("login/otp/verify/", views.OtpVerifyView.as_view(), name="otp_verify"),
    path("logout/", views.LabLogoutView.as_view(), name="logout"),
]
