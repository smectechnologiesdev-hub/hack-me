"""API URL routes for labs (mounted at /api/labs/)."""

from django.urls import path

from . import api_views

app_name = "labs_api"

urlpatterns = [
    path("start/", api_views.LabStartView.as_view(), name="lab-start"),
    path("<str:lab_token>/", api_views.LabDetailView.as_view(), name="lab-detail"),
    path(
        "<str:lab_token>/wordlist/",
        api_views.LabWordlistView.as_view(),
        name="lab-wordlist",
    ),
    path(
        "<str:lab_token>/attempts/",
        api_views.LabAttemptsView.as_view(),
        name="lab-attempts",
    ),
    path(
        "<str:lab_token>/login/",
        api_views.LabLoginView.as_view(),
        name="lab-login",
    ),
]
