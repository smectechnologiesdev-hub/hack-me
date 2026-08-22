"""
WebSocket consumer for the live lab monitor.

Authorization model (matches the training login endpoint): the unguessable,
per-lab token in the URL is the capability.  Anyone who holds a valid token —
a logged-in owner, an instructor, or a student who was given a public challenge
link — may watch that lab's attempt stream.  The token is only ever shown to
the lab's owner and staff, so possession authorizes viewing.

Isolation still holds: each lab has its OWN Channels group (``lab_<token>``),
so a subscriber only ever receives events for the single lab they subscribed
to — never another lab's attempts.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.labs.models import Lab

from .services import lab_group_name


class LabMonitorConsumer(AsyncJsonWebsocketConsumer):
    """Streams a single lab's attempts to anyone holding its token."""

    async def connect(self):
        self.lab_token = self.scope["url_route"]["kwargs"]["lab_token"]

        # The token is the capability: accept only if it maps to a real lab.
        if not await self._lab_exists():
            await self.close(code=4404)  # 4404: unknown lab (app-defined)
            return

        self.group_name = lab_group_name(self.lab_token)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Clients are receive-only; only answer a ping."""
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    # -- Group event handlers -------------------------------------------------
    async def lab_attempt(self, message):
        """Handle a ``{"type": "lab.attempt", ...}`` group message."""
        await self.send_json(message["event"])

    # -- Helpers --------------------------------------------------------------
    @database_sync_to_async
    def _lab_exists(self) -> bool:
        return Lab.objects.filter(lab_token=self.lab_token).exists()
