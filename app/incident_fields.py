"""The Incident record: the nine fields California Labor Code 6401.9(d)(2)
requires in a violent incident log, plus the retention metadata (f)(3)
requires. The option vocabularies live in statute.py, in the statute's own
words. See SPEC.md for the full field-to-statute table.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

RETENTION_YEARS = 5  # subdivision (f)(3)


def five_years_after(created_at: int) -> int:
    """The instant subdivision (f)(3)'s minimum is first satisfied, in epoch ms.

    Calendar years, not ``5 * 365`` days. The constant this replaced was short
    by the leap days in the span — one for most records, two for a record
    created just after a February 29 — so every purge-eligibility date the app
    printed, on ``/retention``, in the JSON log, in the CSV and on the statutory
    log document, fell *inside* the five years the statute sets as a minimum.
    A date that invites a duty-holder to destroy evidence a day early is not a
    rounding error.

    The arithmetic is done in UTC, which is where ``created_at`` is anchored. A
    premises whose zone changes its DST status between the two dates sees the
    anniversary land an hour either side of its local creation time; the printed
    day is unaffected except for a record created within that hour of local
    midnight, and the direction of the statute's "minimum" is why the rounding
    below is up rather than down.

    February 29 has no fifth anniversary. Such a record is kept until March 1,
    which is later than the statute asks and never earlier.
    """
    born = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc)
    try:
        due = born.replace(year=born.year + RETENTION_YEARS)
    except ValueError:  # February 29
        due = born.replace(year=born.year + RETENTION_YEARS, month=3, day=1)
    # Round up, so a sub-millisecond truncation can never land inside the five
    # years. `int()` truncates towards zero, which for a positive epoch is down.
    return -(-int(due.timestamp() * 1000000) // 1000)

# Re-exported so callers that only want the option lists do not have to know
# statute.py exists.
from .statute import (  # noqa: E402,F401
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
)


@dataclass
class Incident:
    incident_id: str
    device_id: str
    location: str

    # (A) date, time, location -- occurred_at filled from the Ring event
    occurred_at: int  # epoch ms

    # Which premises this belongs to. One install can hold several, because
    # 6401.9(d)(1)(C) contemplates more than one site and a small owner with
    # two shops needs one book, not two.
    premises_id: str = ""

    # When the button was pressed, which is not when the incident happened.
    # The evidence pack prints both and never lets them be confused.
    tapped_at: int = 0

    # Evidence, attached automatically
    event_ids: list[str] = field(default_factory=list)
    event_summary: str = ""
    clip_status: str = "not_attempted"  # "attached" | "unavailable: ..."
    clip_sha256: Optional[str] = None
    clip_source: Optional[str] = None
    clip_content_type: str = ""
    clip_window_start: Optional[int] = None
    clip_window_end: Optional[int] = None
    snapshot_sha256: Optional[str] = None
    snapshot_source: Optional[str] = None
    snapshot_content_type: str = ""
    # Every attempt at the clip, including the failures, because a failed
    # fetch is an entry in the manifest and not an absence. Each is
    # {"at": ms, "outcome": "attached"|"unavailable", "reason": str}.
    clip_attempts: list[dict] = field(default_factory=list)

    # (B)-(I): left blank until a human on the floor completes them
    violence_types: list[str] = field(default_factory=list)  # (B), plural per statute
    description: str = ""  # (C)
    perpetrator_class: Optional[str] = None  # (D)
    circumstances: list[str] = field(default_factory=list)  # (E)
    location_class: Optional[str] = None  # (F) classification
    location_detail: str = ""  # (F) free text
    incident_types: list[str] = field(default_factory=list)  # (G), plural per statute
    consequences_response: str = ""  # (H)(i) security or law enforcement
    consequences_actions: str = ""  # (H)(ii) actions to protect employees
    completed_by: str = ""  # (I) name
    completed_by_title: str = ""  # (I) job title
    completed_at: Optional[int] = None  # (I) date completed

    # Retention, per subdivision (f)(3): kept for a minimum of five years
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    retain_until: int = 0
    completed: bool = False

    # Set only by retention.py, once the five years are up and a human asked
    # for the purge. A purged record keeps its dates and its hashes and loses
    # its narrative, so the book still shows that an incident happened.
    purged_at: Optional[int] = None

    def __post_init__(self):
        if not self.retain_until:
            self.retain_until = five_years_after(self.created_at)
        if not self.tapped_at:
            self.tapped_at = self.created_at

    @staticmethod
    def new_id() -> str:
        return f"inc_{uuid.uuid4().hex[:12]}"

    @property
    def earliest_deletion(self) -> int:
        """The date every screen and every export prints, never the stored one.

        ``retain_until`` is persisted, so a book written before
        ``five_years_after`` was corrected still holds a value one or two days
        short of the statutory minimum. The later of the stored value and the
        recomputed one is the only number this app is entitled to print: a
        premises that chose to keep a record longer keeps it longer, and a
        record shortened by an arithmetic bug is not shortened by it twice.
        """
        return max(self.retain_until, five_years_after(self.created_at))

    @property
    def is_purged(self) -> bool:
        return self.purged_at is not None

    def is_statute_complete(self) -> bool:
        """True once every field the statute lists as mandatory has a value.
        Used to decide whether the export is a draft or a finished violent
        incident log entry."""
        return all(
            [
                self.occurred_at,
                self.location,
                self.violence_types,
                self.description,
                self.perpetrator_class,
                self.circumstances,
                self.location_class,
                self.location_detail,
                self.incident_types,
                self.consequences_response,
                self.completed_by,
                self.completed_by_title,
            ]
        )

    def missing_statute_fields(self) -> list[tuple[str, str]]:
        """Which lettered subdivisions are still empty, so the list, the form
        and the evidence pack can all say the same thing about the same
        record instead of each deciding for itself."""
        checks = [
            ("A", "date, time and location", bool(self.occurred_at and self.location)),
            ("B", "workplace violence type", bool(self.violence_types)),
            ("C", "description of the incident", bool(self.description.strip())),
            ("D", "who committed the violence", bool(self.perpetrator_class)),
            ("E", "circumstances at the time", bool(self.circumstances)),
            ("F", "where it occurred", bool(self.location_class and self.location_detail.strip())),
            ("G", "type of incident", bool(self.incident_types)),
            (
                "H",
                "consequences, and whether law enforcement was contacted",
                bool(self.consequences_response.strip()),
            ),
            (
                "I",
                "name and job title of the person completing the log",
                bool(self.completed_by.strip() and self.completed_by_title.strip()),
            ),
        ]
        return [(letter, what) for letter, what, ok in checks if not ok]
