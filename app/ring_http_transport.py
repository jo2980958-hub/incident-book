"""HttpTransport: real HTTP calls to the Ring API, against the documented
Ring for Business webhook and endpoint shapes. Never exercised against a
live account -- no documented sandbox was reachable in the time given.
Swapping fixtures for this is a one-line change (see SPEC.md, "What would
change with a real device")."""

from __future__ import annotations

from typing import Optional

from .ring_types import (
    Ring416TimestampNotFound,
    RingClip,
    RingDevice,
    RingEvent,
    RingSnapshot,
    validate_clip_duration,
)


class HttpTransport:
    BASE_URL = "https://api.amazonvision.com"

    def __init__(
        self,
        access_token: str,
        base_url: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.access_token = access_token
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    def _request(
        self,
        method: str,
        path: str,
        device_id: str = "?",
        timestamp_ms: int = -1,
        **kwargs,
    ):
        # device_id and timestamp_ms are named parameters rather than part of
        # **kwargs because requests.request() rejects unknown keyword
        # arguments: the first version of this passed them straight through
        # and would have raised TypeError on the first real call, which no
        # test caught because no test can reach a live Ring account.
        import requests  # local import: only needed if HttpTransport is used

        resp = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs,
        )
        if resp.status_code == 416:
            raise Ring416TimestampNotFound(device_id, timestamp_ms)
        resp.raise_for_status()
        return resp

    def list_devices(self) -> list[RingDevice]:
        data = self._request("GET", "/v1/devices").json()
        return [
            RingDevice(
                device_id=d["device_id"],
                name=d["name"],
                location=d.get("location", ""),
                status=d.get("status", "unknown"),
                continuous_recording=d.get("subscription", {}).get(
                    "continuous_recording", False
                ),
            )
            for d in data.get("devices", [])
        ]

    def get_event_history(
        self, device_id: str, since_ms: Optional[int] = None
    ) -> list[RingEvent]:
        params = {"since": since_ms} if since_ms is not None else {}
        path = f"/v1/history/devices/{device_id}/events"
        data = self._request("GET", path, params=params).json()
        return [
            RingEvent(
                event_id=e["event_id"],
                device_id=device_id,
                event_type=e["event_type"],
                created_at=e["created_at"],
                sub_type=e.get("attributes", {}).get("sub_type"),
            )
            for e in data.get("events", [])
        ]

    def download_clip(
        self, device_id: str, timestamp_ms: int, duration_ms: int
    ) -> RingClip:
        validate_clip_duration(duration_ms)
        resp = self._request(
            "POST",
            f"/v1/devices/{device_id}/media/video/download",
            json={"timestamp": timestamp_ms, "duration": duration_ms},
            device_id=device_id,
            timestamp_ms=timestamp_ms,
        )
        return RingClip(
            device_id=device_id,
            timestamp_ms=timestamp_ms,
            duration_ms=duration_ms,
            content=resp.content,
            content_type=resp.headers.get("Content-Type", "video/mp4"),
            source="live",
        )

    def download_snapshot(self, device_id: str, timestamp_ms: int) -> RingSnapshot:
        resp = self._request(
            "POST",
            f"/v1/devices/{device_id}/media/image/download",
            json={"timestamp": timestamp_ms},
            device_id=device_id,
            timestamp_ms=timestamp_ms,
        )
        return RingSnapshot(
            device_id=device_id,
            timestamp_ms=timestamp_ms,
            content=resp.content,
            content_type=resp.headers.get("Content-Type", "image/jpeg"),
            source="live",
        )
