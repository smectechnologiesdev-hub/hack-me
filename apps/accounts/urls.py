from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LabLoginView.as_view(), name="login"),
    path("logout/", views.LabLogoutView.as_view(), name="logout"),
]
