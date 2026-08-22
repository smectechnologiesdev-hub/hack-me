"""WebSocket URL routing for the attempts app."""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # ws(s)://host/ws/labs/<lab_token>/  ->  live monitor for one lab.
    re_path(
        r"^ws/labs/(?P<lab_token>[A-Za-z0-9_\-]+)/$",
        consumers.LabMonitorConsumer.as_asgi(),
    ),
]
