"""HTML URL routes for labs (mounted at /labs/)."""

from django.urls import path

from . import views

app_name = "labs"

urlpatterns = [
    path("", views.LabListView.as_view(), name="list"),
    path("start/", views.LabStartView.as_view(), name="start"),
    path("<str:lab_token>/", views.LabDetailView.as_view(), name="detail"),
    path(
        "<str:lab_token>/instructions/",
        views.LabInstructionsView.as_view(),
        name="instructions",
    ),
    path(
        "<str:lab_token>/monitor/",
        views.LabMonitorView.as_view(),
        name="monitor",
    ),
    path(
        "<str:lab_token>/wordlist.txt",
        views.LabWordlistDownloadView.as_view(),
        name="wordlist-download",
    ),
]
