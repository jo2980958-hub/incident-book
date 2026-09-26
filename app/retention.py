"""Five years, and what happens on the day after.

Labor Code 6401.9(f)(3): "Violent incident logs required by subdivision (d)
shall be maintained for a minimum of five years." The first build of this app
computed ``retain_until`` and stored it and then did nothing with it, and said
so in its own spec. That is the one compliance promise the product makes out
loud, so it is now the one screen an owner can point an inspector at.

What is enforced here, in both directions:

- **Nothing inside five years can be deleted.** ``purge`` refuses a record
  whose ``retain_until`` has not passed, and the screen has no control that
  offers it. A log that can be emptied early is the liability this product
  exists to remove.
- **A record past five years is not deleted either, unless a person asks.**
  There is no timer, no cron, no silent sweep. Purging is an action a named
  human takes, and it writes a ledger row saying who, when, which record, and
  what files were removed.
- **A purged record leaves a stump, not a hole.** The dates, the premises, the
  device, the hashes and the amendment trail stay. The narrative fields, the
  names and the evidence bytes go. The book still shows that an incident
  happened on that date at that shop, which is what makes the book honest
  about its own past, and anyone auditing the purge can see the hashes of what
  was removed.

Nothing in the app runs this automatically. That is a deliberate choice, not a
missing feature: an unattended job that deletes statutory records on a timer
is a worse bug than a full disk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from . import timefmt
from .incident_fields import Incident, five_years_after
from .store import IncidentStore

# Wiped on purge. Everything not in this list survives, because everything not
# in this list is a date, an identifier or a hash.
NARRATIVE_FIELDS = (
    "description",
    "consequences_response",
    "consequences_actions",
    "completed_by",
    "completed_by_title",
    "location_detail",
)


@dataclass(frozen=True)
class RetentionPosition:
    """What the retention screen shows. All of it computed, none of it
    stored, so it cannot drift from the records it describes."""

    held: int
    purged: int
    eligible: int
    earliest_created_at: Optional[int]
    next_eligible_at: Optional[int]
    minimum_years: int = 5

    @property
    def nothing_is_eligible(self) -> bool:
        return self.eligible == 0


def position(store: IncidentStore, now_ms: Optional[int] = None) -> RetentionPosition:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    held = purged = eligible = 0
    earliest: Optional[int] = None
    next_eligible: Optional[int] = None
    for incident in store.list_incidents():
        if incident.is_purged:
            purged += 1
            continue
        held += 1
        earliest = min(earliest, incident.created_at) if earliest else incident.created_at
        if earliest_deletion(incident) <= now:
            eligible += 1
        elif next_eligible is None or earliest_deletion(incident) < next_eligible:
            next_eligible = earliest_deletion(incident)
    return RetentionPosition(held, purged, eligible, earliest, next_eligible)


def eligible_for_purge(store: IncidentStore, now_ms: Optional[int] = None) -> list[Incident]:
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    return [
        incident
        for incident in store.list_incidents()
        if not incident.is_purged and earliest_deletion(incident) <= now
    ]


class RetainedTooRecently(Exception):
    """Raised when something asks to delete a record inside its five years.
    There is no override and no force flag."""


def purge(
    store: IncidentStore,
    incident: Incident,
    actor_name: str,
    now_ms: Optional[int] = None,
) -> Incident:
    """Remove the narrative and the evidence from one record past its five
    years, keeping the stump and writing the ledger row."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    due = earliest_deletion(incident)
    if due > now:
        # A date, not epoch milliseconds. This string is rendered: it is what
        # the Retention screen prints when a purge is refused, and `1857776000000`
        # tells the person holding the book nothing about when they may act.
        raise RetainedTooRecently(
            f"{incident.incident_id} must be kept until "
            f"{timefmt.day(due)}; the statutory minimum is five years from "
            "creation, Labor Code 6401.9(f)(3)"
        )
    if incident.is_purged:
        return incident

    removed_files = store.delete_evidence(incident.incident_id)
    for field_name in NARRATIVE_FIELDS:
        setattr(incident, field_name, "")
    # The model's proposal and the worker's own raw, unredacted words live in
    # the drafts table, not on the incident, so an earlier version of this
    # purge left them behind: the narrative was gone from the record and the
    # first draft of it was still on disk and still on the completion screen.
    # A purge that leaves the narrative somewhere else is not a purge.
    draft_removed = store.delete_draft(incident.incident_id)
    incident.purged_at = now
    store.save_incident(incident)
    store.add_retention_event(
        incident.incident_id,
        action="purged",
        actor_name=actor_name,
        note=(
            "Narrative fields and evidence removed after the five-year minimum "
            f"in Labor Code 6401.9(f)(3). Files removed: "
            f"{', '.join(removed_files) if removed_files else 'none on disk'}. "
            + (
                "The software draft and the words it was drafted from were "
                "removed with them. "
                if draft_removed
                else "There was no software draft on this record. "
            )
            + "Dates, device, hashes and the amendment trail were kept."
        ),
    )
    return incident


def earliest_deletion(incident: Incident) -> int:
    """The instant this record may be purged. See ``Incident.earliest_deletion``."""
    return incident.earliest_deletion
