"""Challenge routes.

Mounted at ``/`` so the victim portal lives at ``/portal/…`` and the scoreboard
at ``/scoreboard/``.
"""

from django.urls import path

from . import views

app_name = "challenge"

urlpatterns = [
    # The vulnerable victim portal (brute-force / SQLi target).
    path("portal/login/", views.PortalLoginView.as_view(), name="portal_login"),
    path("portal/logout/", views.PortalLogoutView.as_view(), name="portal_logout"),
    path("portal/", views.PortalHomeView.as_view(), name="portal_home"),
    path("portal/profile/", views.ProfileView.as_view(), name="profile"),
    path("portal/profile/data/", views.DataExportView.as_view(), name="data_export"),
    path("portal/rotate/", views.RotatePasswordView.as_view(), name="rotate_password"),
    path("portal/vault/", views.VaultView.as_view(), name="vault"),
    path("portal/vault/loot/", views.VaultLootView.as_view(), name="vault_loot"),

    # Password list download (for brute-forcing the target login).
    path("passwords.txt", views.WordlistDownloadView.as_view(), name="wordlist"),

    # Scoreboard + flag submission.
    path("scoreboard/", views.ScoreboardView.as_view(), name="scoreboard"),
    path("scoreboard/data/", views.ScoreboardDataView.as_view(), name="scoreboard_data"),
    path("flag/submit/", views.FlagSubmitView.as_view(), name="flag_submit"),
]
