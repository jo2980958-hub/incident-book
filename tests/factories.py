"""Record shapes the tests share.

Kept out of the individual test files because the statutory vocabulary is
long, it changed once already when the option lists were transcribed from
leginfo, and a second change should touch one file rather than eight.
"""

from __future__ import annotations

from app.incident import Incident, compose_event_summary
from app.ring_client import RingClip, RingEvent, RingSnapshot

OCCURRED_AT = 1758500100000
TAPPED_AT = 1758500142000

CLIP_BYTES = b"FIXTURE_CLIP_NOT_REAL_RING_FOOTAGE"
SNAPSHOT_BYTES = b"FIXTURE_SNAPSHOT_NOT_REAL_RING_FOOTAGE"


def human_motion_event(device_id: str = "dev_counter_cam_01") -> RingEvent:
    return RingEvent(
        event_id="e1",
        device_id=device_id,
        event_type="motion.human",
        created_at=OCCURRED_AT,
        sub_type="human",
    )


def fixture_clip(device_id: str = "dev_counter_cam_01") -> RingClip:
    return RingClip(
        device_id=device_id,
        timestamp_ms=OCCURRED_AT - 90_000,
        duration_ms=180_000,
        content=CLIP_BYTES,
        content_type="video/mp4",
        source="fixture",
    )


def fixture_snapshot(device_id: str = "dev_counter_cam_01") -> RingSnapshot:
    return RingSnapshot(
        device_id=device_id,
        timestamp_ms=OCCURRED_AT,
        content=SNAPSHOT_BYTES,
        content_type="image/jpeg",
        source="fixture",
    )


def blank_incident(incident_id: str = "inc_blank") -> Incident:
    """A record as the button leaves it: (A) and the evidence, nothing else."""
    return Incident(
        incident_id=incident_id,
        device_id="dev_counter_cam_01",
        location="Front counter",
        occurred_at=OCCURRED_AT,
        tapped_at=TAPPED_AT,
    )


def complete_incident(
    incident_id: str = "inc_1",
    description: str = "A customer leaned over the counter and threatened the cashier.",
) -> Incident:
    """Every field Labor Code 6401.9(d)(2) lists, answered.

    The vocabularies are the statute's own values, not the first build's
    paraphrases: (B) and (G) are lists because the statute says "type or
    types" and "any of the following", and (F) and (H) each have two limbs.
    """
    incident = Incident(
        incident_id=incident_id,
        device_id="dev_counter_cam_01",
        location="Front counter",
        occurred_at=OCCURRED_AT,
        tapped_at=TAPPED_AT,
        event_ids=["e1"],
        event_summary=compose_event_summary(human_motion_event()),
        clip_status="attached",
        clip_sha256="deadbeef",
        clip_source="fixture",
        clip_content_type="video/mp4",
        clip_window_start=OCCURRED_AT - 90_000,
        clip_window_end=OCCURRED_AT + 90_000,
        snapshot_sha256="cafebabe",
        snapshot_source="fixture",
        snapshot_content_type="image/jpeg",
    )
    incident.violence_types = ["type_2"]
    incident.description = description
    incident.perpetrator_class = "client_or_customer"
    incident.circumstances = ["isolated_or_alone", "low_staffing_level"]
    incident.location_class = "in_the_workplace"
    incident.location_detail = "At the till, on the shop side of the counter."
    incident.incident_types = ["threat"]
    incident.consequences_response = "Police were called and took a report."
    incident.consequences_actions = "The shop closed early and two staff walked out together."
    incident.completed_by = "A. Owner"
    incident.completed_by_title = "Manager"
    incident.completed_at = TAPPED_AT + 3_600_000
    incident.completed = True
    return incident


# The form field names POST /incidents/<id>/edit accepts, in the statute's
# vocabulary. A dict rather than nine keyword arguments because two of them
# are repeated keys and Flask's form parser wants a list for those.
def completion_form(**overrides) -> dict:
    form = {
        "violence_types": ["type_2"],
        "description": "A customer threatened the cashier over a refused sale.",
        "perpetrator_class": "client_or_customer",
        "circumstances": ["isolated_or_alone"],
        "location_class": "in_the_workplace",
        "location_detail": "At the till",
        "incident_types": ["threat"],
        "consequences_response": "Police were called; report taken.",
        "consequences_actions": "Two staff walked out together at closing.",
        "completed_by": "A. Owner",
        "completed_by_title": "Manager",
    }
    form.update(overrides)
    return form
