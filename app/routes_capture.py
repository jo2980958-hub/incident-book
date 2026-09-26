"""The capture stage: one button, which must never block on anything.

Everything here either serves that one screen or reacts to a signed Ring
webhook (or its replay, see tools/replay_webhook.py). Nothing on this path
waits for a model, a premises record, or a network: the tap saves what it can
and the confirmation says plainly what it got.
"""

from __future__ import annotations

import time

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .config import CLIP_WINDOW_MS, WEBHOOK_SECRET
from .incident import draft_from_event
from .ring_client import Ring416TimestampNotFound, RingApiError, RingEvent
from .webhooks import parse_webhook, verify_signature

capture_bp = Blueprint("capture", __name__)


@capture_bp.get("/")
def capture_screen():
    store = current_app.config["STORE"]
    return render_template(
        "index.html",
        practice=False,
        counts=store.counts(),
        first_run=not store.list_premises(),
    )


@capture_bp.get("/practice")
def practice_screen():
    """A drill. The button on a shop counter is pressed once a quarter, under
    stress, by somebody who has never pressed it. This is where a new member
    of staff presses it once before it matters. It runs the same code as the
    real thing and saves nothing."""
    return render_template(
        "index.html", practice=True, counts=current_app.config["STORE"].counts(),
        first_run=False,
    )


@capture_bp.post("/webhooks/ring")
def receive_webhook():
    raw_body = request.get_data()
    signature = request.headers.get("X-Signature", "")
    if not verify_signature(WEBHOOK_SECRET, raw_body, signature):
        return jsonify({"error": "invalid signature"}), 401
    payload = parse_webhook(raw_body)
    device_id = payload.get("device_id")
    if not device_id:
        return jsonify({"error": "missing device_id"}), 400
    current_app.config["LATEST_EVENT"][device_id] = payload
    return jsonify({"status": "received"}), 200


@capture_bp.post("/incidents/tap")
def tap():
    store = current_app.config["STORE"]
    ring = current_app.config["RING"]
    device_id = request.form.get("device_id", "dev_counter_cam_01")
    practice = request.form.get("practice") == "1"

    devices = {d.device_id: d for d in ring.list_devices()}
    device = devices.get(device_id)
    if device is None:
        abort(404, f"unknown device {device_id}")

    tapped_at = int(time.time() * 1000)
    event = _event_from_latest_webhook(device_id)
    clip, attempt, snapshot = fetch_evidence(ring, device_id, event)

    registration = store.get_device_registration(device_id)
    incident = draft_from_event(
        device_id=device_id,
        location=device.location,
        event=event,
        clip=clip,
        clip_attempt=attempt,
        snapshot=snapshot,
        tapped_at=tapped_at,
        premises_id=registration.premises_id if registration else "",
    )

    if practice:
        # Nothing is written. The drill has to feel the same and cost nothing.
        return render_template("captured.html", incident=incident, practice=True)

    store.save_incident(incident)
    store.add_revision(
        incident.incident_id,
        kind="captured",
        changes={},
        note=(
            "Created by a button press. The date, time, location and evidence "
            "were filled from the device. No statutory field was answered."
        ),
        at=tapped_at,
    )
    if clip is not None:
        store.save_evidence(incident.incident_id, "clip", clip.content)
    if snapshot is not None:
        store.save_evidence(incident.incident_id, "snapshot", snapshot.content)

    return redirect(url_for("capture.captured_screen", incident_id=incident.incident_id))


@capture_bp.get("/incidents/<incident_id>/captured")
def captured_screen(incident_id: str):
    incident = current_app.config["STORE"].get_incident(incident_id)
    if incident is None:
        abort(404)
    return render_template("captured.html", incident=incident, practice=False)


@capture_bp.post("/incidents/<incident_id>/clip/retry")
def retry_clip(incident_id: str):
    """Try the clip again against the original window.

    The window is the whole product and it closes. A fetch that failed because
    the shop's wifi was down at 19:07 may succeed at 19:20, and the first build
    of this app gave nobody a way to find out. Every attempt, including the
    ones that fail, is kept on the record and printed in the manifest, because
    a gap is an entry and not an absence.
    """
    store = current_app.config["STORE"]
    ring = current_app.config["RING"]
    incident = store.get_incident(incident_id)
    if incident is None:
        abort(404)
    if incident.clip_status == "attached" or incident.is_purged:
        return redirect(url_for("admin.edit_form", incident_id=incident_id))

    start = incident.clip_window_start or (incident.occurred_at - CLIP_WINDOW_MS)
    duration = 2 * CLIP_WINDOW_MS
    now = int(time.time() * 1000)
    try:
        clip = ring.fetch_clip(incident.device_id, start, duration)
    except (Ring416TimestampNotFound, RingApiError) as exc:
        incident.clip_attempts.append(
            {"at": now, "outcome": "unavailable", "reason": _reason(exc)}
        )
        incident.clip_status = f"unavailable: {_reason(exc)}"
    else:
        import hashlib

        store.save_evidence(incident.incident_id, "clip", clip.content)
        incident.clip_status = "attached"
        incident.clip_sha256 = hashlib.sha256(clip.content).hexdigest()
        incident.clip_source = clip.source
        incident.clip_content_type = clip.content_type
        incident.clip_attempts.append(
            {"at": now, "outcome": "attached", "reason": "the clip was returned"}
        )
    store.save_incident(incident)
    store.add_retention_event(
        incident.incident_id,
        action="clip retry",
        note=f"Clip status after the retry: {incident.clip_status}.",
    )
    return redirect(url_for("admin.edit_form", incident_id=incident_id))


def _event_from_latest_webhook(device_id: str):
    payload = current_app.config["LATEST_EVENT"].get(device_id)
    if payload is None:
        return None
    return RingEvent(
        event_id=f"webhook_{payload['created_at']}",
        device_id=device_id,
        event_type=payload["event_type"],
        created_at=payload["created_at"],
        sub_type=payload.get("attributes", {}).get("sub_type"),
    )


def fetch_evidence(ring, device_id: str, event):
    """Returns (clip, attempt, snapshot). ``attempt`` is always a dict, even
    when the clip came back, so the record keeps the whole history of what was
    asked for and what happened."""
    now = int(time.time() * 1000)
    if event is None:
        return (
            None,
            {
                "at": now,
                "outcome": "not attempted",
                "reason": "no device event was held when the button was pressed",
            },
            None,
        )
    start = event.created_at - CLIP_WINDOW_MS
    duration = 2 * CLIP_WINDOW_MS
    try:
        clip = ring.fetch_clip(device_id, start, duration)
        snapshot = ring.fetch_snapshot(device_id, event.created_at)
    except (Ring416TimestampNotFound, RingApiError) as exc:
        return None, {"at": now, "outcome": "unavailable", "reason": _reason(exc)}, None
    return (
        clip,
        {"at": now, "outcome": "attached", "reason": "the clip was returned"},
        snapshot,
    )


def _reason(exc: Exception) -> str:
    if isinstance(exc, Ring416TimestampNotFound):
        return (
            "the camera was not recording at that timestamp "
            "(416 TIMESTAMP_NOT_FOUND). Continuous recording is a paid tier; "
            "a camera on event-only recording will usually answer this way"
        )
    return str(exc)
