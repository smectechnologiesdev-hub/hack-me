"""Instructor dashboard routes (mounted at /instructor/)."""

from django.urls import path

from . import views

# app_name is provided by the include() tuple in config/urls.py.
urlpatterns = [
    path("", views.InstructorDashboardView.as_view(), name="dashboard"),
    # Vaultline Heist live monitor (scoreboard + activity log).
    path("challenge/", views.ChallengeMonitorView.as_view(), name="challenge"),
    path("challenge/data/", views.ChallengeMonitorDataView.as_view(), name="challenge_data"),
    path("labs/", views.InstructorLabListView.as_view(), name="labs"),
    path("attempts/", views.InstructorAttemptListView.as_view(), name="attempts"),
]
