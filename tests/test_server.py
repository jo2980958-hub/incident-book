import json
from pathlib import Path

from factories import completion_form

from app.webhooks import sign

SECRET = "demo-shared-secret"  # matches app.config.WEBHOOK_SECRET default
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
MOTION_WEBHOOK = FIXTURES / "webhook_motion_human.json"


def _post_webhook(client, fixture_path=MOTION_WEBHOOK):
    payload = json.loads(fixture_path.read_text())
    payload.pop("_comment", None)
    raw_body = json.dumps(payload).encode("utf-8")
    signature = sign(SECRET, raw_body)
    return client.post(
        "/webhooks/ring",
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Signature": signature},
    )


def _tap(client, device_id="dev_counter_cam_01"):
    resp = client.post("/incidents/tap", data={"device_id": device_id})
    assert resp.status_code == 302
    return resp.headers["Location"].rsplit("/", 2)[-2]


def test_capture_screen_loads_with_one_button(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Log an incident" in resp.data


def test_webhook_with_bad_signature_is_rejected(client):
    resp = client.post(
        "/webhooks/ring",
        data=b'{"event_type": "motion_detected", "device_id": "dev_counter_cam_01"}',
        headers={"X-Signature": "not-a-real-signature"},
    )
    assert resp.status_code == 401


def test_tap_without_any_prior_webhook_still_saves_a_draft(client):
    resp = client.post("/incidents/tap", data={"device_id": "dev_counter_cam_01"})
    assert resp.status_code == 302
    followed = client.get(resp.headers["Location"])
    assert followed.status_code == 200
    assert b"Captured." in followed.data


def test_tap_after_replayed_webhook_attaches_a_clip_on_continuous_recording_device(
    client,
):
    assert _post_webhook(client).status_code == 200
    incident_id = _tap(client)
    captured = client.get(f"/incidents/{incident_id}/captured")
    assert b"Attached, source fixture." in captured.data


def test_tap_on_non_continuous_recording_device_reports_gap_not_crash(client):
    # No webhook was replayed for this device, so there is no trigger event
    # and no clip attempt at all -- this proves the tap path never crashes
    # when there's nothing to attach, the honest "not attempted" case.
    incident_id = _tap(client, "dev_backdoor_cam_01")
    captured = client.get(f"/incidents/{incident_id}/captured")
    assert captured.status_code == 200
    assert b"not attempted" in captured.data


def test_full_flow_capture_then_complete_then_export(client):
    _post_webhook(client)
    incident_id = _tap(client)

    edit_resp = client.get(f"/incidents/{incident_id}/edit")
    assert edit_resp.status_code == 200
    assert b"6401.9" in edit_resp.data

    save_resp = client.post(f"/incidents/{incident_id}/edit", data=completion_form())
    assert save_resp.status_code == 302

    log_resp = client.get(f"/incidents/{incident_id}/export/log")
    assert log_resp.status_code == 200
    log = log_resp.get_json()
    assert log["statute_complete"] is True
    assert log["missing_fields"] == []
    assert log["I_completed_by"]["name"] == "A. Owner"

    pack_resp = client.get(f"/incidents/{incident_id}/export/pack")
    assert pack_resp.status_code == 200
    assert b"Incident evidence pack" in pack_resp.data

    manifest = client.get(f"/incidents/{incident_id}/export/pack.json").get_json()
    clip = next(e for e in manifest["exhibits"] if e["ref"] == "E1")
    assert clip["sha256"] is not None
    assert len(clip["sha256"]) == 64


def test_manifest_sha256_file_downloads_in_coreutils_format(client):
    _post_webhook(client)
    incident_id = _tap(client)
    resp = client.get(f"/incidents/{incident_id}/export/manifest.sha256")
    assert resp.status_code == 200
    assert "manifest.sha256" in resp.headers["Content-Disposition"]
    for line in resp.get_data(as_text=True).splitlines():
        digest, sep, name = line.partition("  ")
        assert sep == "  " and len(digest) == 64 and name


def test_incident_list_shows_needs_finishing_and_complete_status(client):
    """The list says "Needs finishing", not "Draft": a half-written statutory
    record is not a draft, it is a record with unanswered fields, and the
    count beside it says how many."""
    incident_id = _tap(client)
    list_resp = client.get("/incidents")
    assert list_resp.status_code == 200
    # The status filter offers both words, so match the pill rather than
    # the word, or this passes on the dropdown alone.
    assert b'class="pill pill-todo">Needs finishing' in list_resp.data
    assert b"of the nine fields are still empty" in list_resp.data

    client.post(f"/incidents/{incident_id}/edit", data=completion_form())
    list_resp = client.get("/incidents")
    assert b'class="pill pill-done">Complete' in list_resp.data
    assert b'class="pill pill-todo">' not in list_resp.data
