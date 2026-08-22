"""Instructor dashboard routes (mounted at /instructor/)."""

from django.urls import path

from . import views

# app_name is provided by the include() tuple in config/urls.py.
urlpatterns = [
    path("", views.InstructorDashboardView.as_view(), name="dashboard"),
    path("labs/", views.InstructorLabListView.as_view(), name="labs"),
    path("attempts/", views.InstructorAttemptListView.as_view(), name="attempts"),
]
