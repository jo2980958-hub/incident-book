import pytest

from app.ring_client import (
    MAX_CLIP_DURATION_MS,
    Ring416TimestampNotFound,
)


def test_list_devices_returns_both_fixture_devices(ring):
    devices = ring.list_devices()
    ids = {d.device_id for d in devices}
    assert ids == {"dev_counter_cam_01", "dev_backdoor_cam_01"}


def test_event_history_filters_by_device(ring):
    events = ring.get_event_history("dev_counter_cam_01")
    assert all(e.device_id == "dev_counter_cam_01" for e in events)
    assert len(events) == 4  # excludes the vehicle event on the other device


def test_event_history_consent_gate_excludes_pre_consent_events(ring):
    # 1758500000000 is after evt_before_consent_01 (1758400000000) and at
    # or before every other fixture event on this device.
    events = ring.get_event_history("dev_counter_cam_01", since_ms=1758500000000)
    ids = {e.event_id for e in events}
    assert "evt_before_consent_01" not in ids
    assert "evt_motion_human_01" in ids


def test_event_history_without_since_returns_everything_including_pre_consent(ring):
    events = ring.get_event_history("dev_counter_cam_01")
    ids = {e.event_id for e in events}
    assert "evt_before_consent_01" in ids


def test_fetch_clip_succeeds_on_continuous_recording_device(ring):
    clip = ring.fetch_clip("dev_counter_cam_01", timestamp_ms=1758500100000, duration_ms=180000)
    assert clip.source == "fixture"
    assert clip.content_type == "video/mp4"
    assert b"FIXTURE_CLIP" in clip.content


def test_fetch_clip_416_produces_explicit_gap_not_a_crash(ring):
    # dev_backdoor_cam_01 is on the fixture's event-only plan
    # (subscription.continuous_recording: false in fixtures/devices.json).
    with pytest.raises(Ring416TimestampNotFound) as excinfo:
        ring.fetch_clip("dev_backdoor_cam_01", timestamp_ms=1758500400000, duration_ms=180000)
    assert excinfo.value.device_id == "dev_backdoor_cam_01"


def test_fetch_clip_rejects_duration_above_documented_max(ring):
    with pytest.raises(ValueError):
        ring.fetch_clip(
            "dev_counter_cam_01",
            timestamp_ms=1758500100000,
            duration_ms=MAX_CLIP_DURATION_MS + 1,
        )


def test_fetch_snapshot_respects_same_plan_gate(ring):
    with pytest.raises(Ring416TimestampNotFound):
        ring.fetch_snapshot("dev_backdoor_cam_01", timestamp_ms=1758500400000)

    snapshot = ring.fetch_snapshot("dev_counter_cam_01", timestamp_ms=1758500100000)
    assert snapshot.content_type == "image/jpeg"
    assert b"FIXTURE_SNAPSHOT" in snapshot.content
