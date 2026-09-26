"""Shared types for the Ring client. Every other app module (server,
incident, export) only ever sees these -- never raw JSON, and never
whether the data came from FixtureTransport or HttpTransport. That's the
fixture boundary described in SPEC.md, and it's why these types live in
their own file instead of next to either transport.

Endpoints modelled, from Ring's own published API documentation:
  GET  /v1/devices
  GET  /v1/history/devices/{device_id}/events
  POST /v1/devices/{device_id}/media/video/download
  POST /v1/devices/{device_id}/media/image/download
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

# Ring's documented cap on clip duration for a single download request.
MAX_CLIP_DURATION_MS = 900_000  # documented cap, ms


class RingApiError(Exception):
    """Base class for errors the Ring API itself returns."""


class Ring416TimestampNotFound(RingApiError):
    """Mirrors the documented 416 TIMESTAMP_NOT_FOUND response: the camera
    was not recording at the requested timestamp. Per the docs, this is
    the expected outcome for any device without a paid continuous-recording
    plan, for almost any timestamp that isn't the current moment."""

    def __init__(self, device_id: str, timestamp_ms: int):
        self.device_id = device_id
        self.timestamp_ms = timestamp_ms
        super().__init__(
            f"416 TIMESTAMP_NOT_FOUND: device {device_id} was not recording "
            f"at {timestamp_ms}"
        )


@dataclass(frozen=True)
class RingDevice:
    device_id: str
    name: str
    location: str
    status: str
    continuous_recording: bool


@dataclass(frozen=True)
class RingEvent:
    event_id: str
    device_id: str
    event_type: str  # e.g. "motion.human", "on_demand", "ding"
    created_at: int  # epoch ms
    sub_type: Optional[str] = None  # e.g. "human" -- never a person's identity


@dataclass(frozen=True)
class RingClip:
    device_id: str
    timestamp_ms: int
    duration_ms: int
    content: bytes
    content_type: str
    source: str  # "fixture" or "live" -- carried through to every export


@dataclass(frozen=True)
class RingSnapshot:
    device_id: str
    timestamp_ms: int
    content: bytes
    content_type: str
    source: str


def validate_clip_duration(duration_ms: int) -> None:
    """Shared by both transports so the documented cap is enforced in
    exactly one place. Ring's docs: clip download supports duration up to
    900,000 ms (900 seconds)."""
    if duration_ms > MAX_CLIP_DURATION_MS:
        raise ValueError(
            f"duration_ms {duration_ms} exceeds documented max {MAX_CLIP_DURATION_MS}"
        )


class Transport(Protocol):
    def list_devices(self) -> list[RingDevice]: ...

    def get_event_history(
        self, device_id: str, since_ms: Optional[int] = None
    ) -> list[RingEvent]: ...

    def download_clip(
        self, device_id: str, timestamp_ms: int, duration_ms: int
    ) -> RingClip: ...

    def download_snapshot(self, device_id: str, timestamp_ms: int) -> RingSnapshot: ...
