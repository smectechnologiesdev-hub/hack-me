"""Student dashboard routes (mounted at /dashboard/)."""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    path("new/", views.NewChallengeView.as_view(), name="new"),
]
