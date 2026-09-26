"""The Ring client boundary, per SPEC.md ("The fixture boundary, stated
plainly"). This module and its ring_types.py / ring_fixture_transport.py /
ring_http_transport.py neighbours are the ONLY place in the app that knows
Ring's HTTP shapes. Everything above them (server, incident, export) only
ever sees RingDevice / RingEvent / RingClip / RingSnapshot and never knows
whether the data came from FixtureTransport (used everywhere in this
build) or HttpTransport (written, never exercised against a live account).

This file is intentionally the thin, readable entry point: RingClient
wraps whichever Transport it's given, and build_client() is the one
switch between fixture and live Ring API access.
"""

from __future__ import annotations

from .ring_fixture_transport import FixtureTransport
from .ring_http_transport import HttpTransport
from .ring_types import (
    MAX_CLIP_DURATION_MS,
    Ring416TimestampNotFound,
    RingApiError,
    RingClip,
    RingDevice,
    RingEvent,
    RingSnapshot,
    Transport,
)

__all__ = [
    "MAX_CLIP_DURATION_MS",
    "Ring416TimestampNotFound",
    "RingApiError",
    "RingClip",
    "RingDevice",
    "RingEvent",
    "RingSnapshot",
    "Transport",
    "FixtureTransport",
    "HttpTransport",
    "RingClient",
    "build_client",
]


class RingClient:
    """Thin wrapper that all app code calls. Delegates to whichever
    Transport it was built with."""

    def __init__(self, transport: Transport):
        self.transport = transport

    def list_devices(self) -> list[RingDevice]:
        return self.transport.list_devices()

    def get_event_history(self, device_id: str, since_ms: int | None = None) -> list[RingEvent]:
        return self.transport.get_event_history(device_id, since_ms=since_ms)

    def fetch_clip(self, device_id: str, timestamp_ms: int, duration_ms: int) -> RingClip:
        return self.transport.download_clip(device_id, timestamp_ms, duration_ms)

    def fetch_snapshot(self, device_id: str, timestamp_ms: int) -> RingSnapshot:
        return self.transport.download_snapshot(device_id, timestamp_ms)


def build_client(use_fixtures: bool = True, **http_kwargs) -> RingClient:
    """Single switch point between fixture and live Ring API access.
    See SPEC.md, 'What would change with a real device'."""
    if use_fixtures:
        return RingClient(FixtureTransport())
    return RingClient(HttpTransport(**http_kwargs))
