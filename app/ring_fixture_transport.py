"""FixtureTransport: reads recorded JSON/binary fixtures from fixtures/.
Never makes a network call. Used for every test and every demo run in this
build, because no documented Ring sandbox is reachable and no real device
was available (see SPEC.md, "The fixture boundary, stated plainly").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .ring_types import (
    Ring416TimestampNotFound,
    RingApiError,
    RingClip,
    RingDevice,
    RingEvent,
    RingSnapshot,
    validate_clip_duration,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"  # recorded fixtures


class FixtureTransport:
    """Reads recorded fixtures. Never makes a network call. This is what
    every test and every demo run in this build actually uses."""

    def __init__(self, fixtures_dir: Path = FIXTURES_DIR):
        self.fixtures_dir = fixtures_dir
        self._devices = self._load_devices()

    def _load_devices(self) -> dict[str, dict]:
        raw = json.loads((self.fixtures_dir / "devices.json").read_text())
        return {d["device_id"]: d for d in raw["devices"]}

    def list_devices(self) -> list[RingDevice]:
        return [
            RingDevice(
                device_id=d["device_id"],
                name=d["name"],
                location=d["location"],
                status=d["status"],
                continuous_recording=d["subscription"]["continuous_recording"],
            )
            for d in self._devices.values()
        ]

    def get_event_history(
        self, device_id: str, since_ms: Optional[int] = None
    ) -> list[RingEvent]:
        raw = json.loads((self.fixtures_dir / "events_history.json").read_text())
        events = []
        for e in raw["events"]:
            if e["device_id"] != device_id:
                continue
            if since_ms is not None and e["created_at"] < since_ms:
                # Mirrors the documented consent time-gate: "Only events
                # that occurred after the user granted consent to your
                # app are returned." No backfill.
                continue
            events.append(
                RingEvent(
                    event_id=e["event_id"],
                    device_id=e["device_id"],
                    event_type=e["event_type"],
                    created_at=e["created_at"],
                    sub_type=e.get("attributes", {}).get("sub_type"),
                )
            )
        return sorted(events, key=lambda e: e.created_at)

    def _require_continuous_recording(self, device_id: str, timestamp_ms: int) -> dict:
        device = self._devices.get(device_id)
        if device is None:
            raise RingApiError(f"unknown device {device_id}")
        if not device["subscription"]["continuous_recording"]:
            # Mirrors the documented behaviour exactly: clip download does
            # not trigger recording, so any timestamp not covered by an
            # active continuous-recording plan returns 416.
            raise Ring416TimestampNotFound(device_id, timestamp_ms)
        return device

    def download_clip(
        self, device_id: str, timestamp_ms: int, duration_ms: int
    ) -> RingClip:
        validate_clip_duration(duration_ms)
        self._require_continuous_recording(device_id, timestamp_ms)
        content = (self.fixtures_dir / "clip_placeholder.bin").read_bytes()
        return RingClip(
            device_id=device_id,
            timestamp_ms=timestamp_ms,
            duration_ms=duration_ms,
            content=content,
            content_type="video/mp4",
            source="fixture",
        )

    def download_snapshot(self, device_id: str, timestamp_ms: int) -> RingSnapshot:
        self._require_continuous_recording(device_id, timestamp_ms)
        content = (self.fixtures_dir / "snapshot_placeholder.bin").read_bytes()
        return RingSnapshot(
            device_id=device_id,
            timestamp_ms=timestamp_ms,
            content=content,
            content_type="image/jpeg",
            source="fixture",
        )
