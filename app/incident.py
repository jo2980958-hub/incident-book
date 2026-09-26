"""Builds the half-written incident the moment staff taps the button.

The record shape lives in incident_fields.py, the statutory vocabulary in
statute.py and the language guard in incident_language.py; this module is where
they meet, plus the entry point the rest of the app imports from.
"""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from .incident_fields import (  # noqa: F401  (re-exported for callers)
    CIRCUMSTANCE_OPTIONS,
    RETENTION_YEARS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
    Incident,
    five_years_after,
)
from .incident_language import (  # noqa: F401  (re-exported for callers)
    AccusatoryLanguageError,
    DocumentLanguageError,
    OverclaimError,
    assert_document_safe,
    assert_no_accusatory_language,
    assert_no_overclaiming,
    compose_event_summary,
)
from .ring_types import RingClip, RingEvent, RingSnapshot


def draft_from_event(
    device_id: str,
    location: str,
    event: Optional[RingEvent],
    clip: Optional[RingClip],
    clip_attempt: Optional[dict],
    snapshot: Optional[RingSnapshot],
    tapped_at: Optional[int] = None,
    premises_id: str = "",
) -> Incident:
    """Fills only what the statute calls (A), date, time and location, plus
    the evidence. Every other field is left for the human, deliberately: the
    app has no basis to classify who did what."""
    tapped_at = tapped_at or _now_ms()
    occurred_at = event.created_at if event is not None else tapped_at
    incident = Incident(
        incident_id=Incident.new_id(),
        premises_id=premises_id,
        device_id=device_id,
        location=location,
        occurred_at=occurred_at,
        tapped_at=tapped_at,
        event_ids=[event.event_id] if event is not None else [],
        event_summary=compose_event_summary(event),
    )
    if clip_attempt is not None:
        incident.clip_attempts = [clip_attempt]
        if clip_attempt["outcome"] == "not attempted":
            incident.clip_status = "not attempted: " + clip_attempt["reason"]
        elif clip_attempt["outcome"] == "unavailable":
            incident.clip_status = "unavailable: " + clip_attempt["reason"]

    if clip is not None:
        incident.clip_status = "attached"
        incident.clip_sha256 = hashlib.sha256(clip.content).hexdigest()
        incident.clip_source = clip.source
        incident.clip_content_type = clip.content_type
        incident.clip_window_start = clip.timestamp_ms
        incident.clip_window_end = clip.timestamp_ms + clip.duration_ms

    if snapshot is not None:
        incident.snapshot_sha256 = hashlib.sha256(snapshot.content).hexdigest()
        incident.snapshot_source = snapshot.source
        incident.snapshot_content_type = snapshot.content_type

    return incident


def _now_ms() -> int:
    return int(time.time() * 1000)
