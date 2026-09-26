from app.incident import Incident


def test_save_and_get_incident_round_trips(store):
    incident = Incident(incident_id="inc_1", device_id="d", location="loc", occurred_at=1000)
    incident.description = "Something happened."
    store.save_incident(incident)

    loaded = store.get_incident("inc_1")
    assert loaded is not None
    assert loaded.incident_id == "inc_1"
    assert loaded.description == "Something happened."
    assert loaded.retain_until == incident.retain_until


def test_get_unknown_incident_returns_none(store):
    assert store.get_incident("does_not_exist") is None


def test_save_incident_upserts(store):
    incident = Incident(incident_id="inc_1", device_id="d", location="loc", occurred_at=1000)
    store.save_incident(incident)
    incident.description = "Updated."
    store.save_incident(incident)

    loaded = store.get_incident("inc_1")
    assert loaded.description == "Updated."


def test_list_incidents_orders_newest_first(store):
    a = Incident(incident_id="inc_a", device_id="d", location="loc", occurred_at=1000, created_at=1000)
    b = Incident(incident_id="inc_b", device_id="d", location="loc", occurred_at=2000, created_at=2000)
    store.save_incident(a)
    store.save_incident(b)

    ids = [i.incident_id for i in store.list_incidents()]
    assert ids == ["inc_b", "inc_a"]


def test_evidence_round_trips(store):
    path = store.save_evidence("inc_1", "clip", b"FIXTURE_CLIP_BYTES")
    assert path.exists()
    assert store.load_evidence("inc_1", "clip") == b"FIXTURE_CLIP_BYTES"


def test_load_missing_evidence_returns_none(store):
    assert store.load_evidence("inc_missing", "clip") is None


def test_consent_grant_round_trips(store):
    assert store.get_consent_granted_at("dev_counter_cam_01") is None
    store.record_consent_grant("dev_counter_cam_01", 1758500000000)
    assert store.get_consent_granted_at("dev_counter_cam_01") == 1758500000000
