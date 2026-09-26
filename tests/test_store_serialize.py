"""A record written by the first build has to open in this one.

A violent incident log is kept five years, so a schema change is a thing the
record survives, not a thing that empties the book.
"""

from app.store_serialize import incident_from_dict, incident_to_dict

OLD_SHAPE = {
    "incident_id": "inc_old",
    "device_id": "dev_counter_cam_01",
    "location": "Front counter",
    "occurred_at": 1_700_000_000_000,
    "created_at": 1_700_000_000_000,
    "retain_until": 1_857_776_000_000,
    "event_ids": ["e1"],
    "event_summary": "Motion event recorded (human).",
    "clip_status": "attached",
    "clip_sha256": "deadbeef",
    # The first build's singular fields and its own paraphrased vocabulary.
    "violence_type": "client_or_customer",
    "description": "A customer threatened the cashier.",
    "perpetrator_class": "stranger",
    "circumstances": ["isolated_or_alone"],
    "location_detail": "At the till",
    "incident_type": "physical_attack_with_weapon",
    "consequences": "Police were called.",
    "completed_by": "A. Owner",
    "completed_by_title": "Manager",
    "completed": True,
}


def test_an_old_record_opens_with_its_singular_fields_made_plural():
    incident = incident_from_dict(OLD_SHAPE)
    assert incident.violence_types == ["type_2"]
    assert incident.incident_types == ["attack_with_weapon_or_object"]
    assert incident.circumstances == ["isolated_or_alone"]


def test_an_old_option_value_maps_to_the_statutes_own_word():
    incident = incident_from_dict(OLD_SHAPE)
    assert incident.perpetrator_class == "stranger_with_criminal_intent"


def test_the_old_single_consequences_field_becomes_the_first_limb_of_H():
    incident = incident_from_dict(OLD_SHAPE)
    assert incident.consequences_response == "Police were called."
    assert incident.consequences_actions == ""


def test_nothing_the_old_record_held_is_lost():
    incident = incident_from_dict(OLD_SHAPE)
    assert incident.description == OLD_SHAPE["description"]
    assert incident.clip_sha256 == "deadbeef"
    assert incident.event_ids == ["e1"]
    assert incident.completed is True
    assert incident.retain_until == OLD_SHAPE["retain_until"]


def test_a_field_the_old_build_never_had_opens_empty_rather_than_missing():
    incident = incident_from_dict(OLD_SHAPE)
    assert incident.location_class is None
    assert incident.clip_attempts == []
    assert incident.premises_id == ""
    # tapped_at defaulted to created_at rather than to zero, so the document
    # never prints an epoch-zero timestamp for a record that predates it.
    assert incident.tapped_at == OLD_SHAPE["created_at"]


def test_a_record_survives_a_round_trip_through_this_build():
    once = incident_from_dict(OLD_SHAPE)
    twice = incident_from_dict(incident_to_dict(once))
    assert incident_to_dict(once) == incident_to_dict(twice)


def test_an_old_record_can_still_be_finished_and_exported(store):
    from app.export import build_violent_incident_log_entry

    incident = incident_from_dict(OLD_SHAPE)
    store.save_incident(incident)
    reopened = store.get_incident("inc_old")
    entry = build_violent_incident_log_entry(reopened)
    assert entry["B_workplace_violence_type"] == ["Type 2: a customer, client or visitor"]
    # (F)'s classification was never asked for by the old build, so the entry
    # says so rather than guessing one.
    assert entry["F_where_it_occurred"]["classification"] is None
    assert [m["letter"] for m in entry["missing_fields"]] == ["F"]
