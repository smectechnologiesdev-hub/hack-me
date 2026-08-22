from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    # The single login endpoint — browser form AND brute-force target.
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", views.LabLogoutView.as_view(), name="logout"),
]
