"""Five years, enforced in both directions.

Labor Code 6401.9(f)(3) sets a minimum, so the interesting cases are the two
refusals: nothing inside its five years can be deleted, and nothing outside
them is deleted unless a named person asks.
"""

import pytest
from factories import complete_incident

from app.drafting import Draft
from app.retention import (
    RetainedTooRecently,
    eligible_for_purge,
    five_years_after,
    position,
    purge,
)

NOW = 2_000_000_000_000
# Comfortably past five years, whichever way the leap days fall. It used to be
# `FIVE_YEARS_MS`, a constant that was itself a day short of five years, so a
# record aged by exactly that much was not actually eligible for purge.
PAST_FIVE_YEARS = 6 * 366 * 24 * 60 * 60 * 1000


def _aged(store, created_at, incident_id="inc_old"):
    incident = complete_incident(incident_id)
    incident.created_at = created_at
    incident.retain_until = five_years_after(created_at)
    store.save_incident(incident)
    return incident


def test_a_record_inside_its_five_years_cannot_be_purged_and_has_no_override(store):
    incident = _aged(store, NOW - 1000)
    with pytest.raises(RetainedTooRecently):
        purge(store, incident, actor_name="A. Owner", now_ms=NOW)
    assert store.get_incident(incident.incident_id).is_purged is False


def test_only_records_past_five_years_are_offered(store):
    _aged(store, NOW - PAST_FIVE_YEARS, "inc_ready")
    _aged(store, NOW - 1000, "inc_recent")
    offered = [i.incident_id for i in eligible_for_purge(store, now_ms=NOW)]
    assert offered == ["inc_ready"]


def test_a_purge_leaves_a_stump_and_not_a_hole(store):
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    store.save_evidence(incident.incident_id, "clip", b"FIXTURE")
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)

    after = store.get_incident(incident.incident_id)
    assert after.is_purged is True
    assert after.description == ""
    assert after.completed_by == ""
    # What survives is what makes the book honest about its own past.
    assert after.occurred_at == incident.occurred_at
    assert after.clip_sha256 == incident.clip_sha256
    assert after.device_id == incident.device_id
    assert store.load_evidence(incident.incident_id, "clip") is None


def test_the_software_draft_goes_with_the_narrative_it_drafted(store):
    """The draft holds the model's proposal and the worker's own raw,
    unredacted words, and it lives in its own table. A purge that empties the
    record and leaves the first version of it on disk is not a purge."""
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    store.save_draft(
        Draft(
            incident_id=incident.incident_id,
            source_words="John Smith came over the counter",
            description="A person came over the counter.",
            model_id="stub-model",
        )
    )
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)
    assert store.get_draft(incident.incident_id) is None


def test_a_purge_that_had_nothing_to_draft_says_so_rather_than_implying_it_did(store):
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)
    note = store.retention_events()[0]["note"]
    assert "There was no software draft on this record." in note


def test_the_ledger_records_who_purged_what_and_when(store):
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    store.save_evidence(incident.incident_id, "clip", b"FIXTURE")
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)

    events = store.retention_events()
    assert len(events) == 1
    assert events[0]["action"] == "purged"
    assert events[0]["actor_name"] == "A. Owner"
    assert events[0]["incident_id"] == incident.incident_id
    assert "6401.9(f)(3)" in events[0]["note"]
    assert ".clip.bin" in events[0]["note"]


def test_purging_twice_is_not_a_second_purge(store):
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)
    purge(store, store.get_incident(incident.incident_id), "A. Owner", now_ms=NOW)
    assert len(store.retention_events()) == 1


def test_the_position_counts_what_is_held_eligible_and_already_purged(store):
    _aged(store, NOW - PAST_FIVE_YEARS, "inc_ready")
    _aged(store, NOW - 1000, "inc_recent")
    done = _aged(store, NOW - PAST_FIVE_YEARS - 1000, "inc_done")
    purge(store, done, actor_name="A. Owner", now_ms=NOW)

    where = position(store, now_ms=NOW)
    assert where.held == 2  # "held" is what is still held, so a purge leaves it
    assert where.purged == 1
    assert where.eligible == 1
    assert where.next_eligible_at is not None


def test_a_purged_record_cannot_be_edited_through_the_form(client, app):
    store = app.config["STORE"]
    incident = _aged(store, NOW - PAST_FIVE_YEARS)
    purge(store, incident, actor_name="A. Owner", now_ms=NOW)

    assert client.post(f"/incidents/{incident.incident_id}/edit", data={}).status_code == 409
    assert (
        client.post(f"/incidents/{incident.incident_id}/draft", data={"words": "hi"})
    ).status_code == 409
    page = client.get(f"/incidents/{incident.incident_id}/edit").get_data(as_text=True)
    assert "passed its five years and was purged" in page
    assert "Draft the wording" not in page
