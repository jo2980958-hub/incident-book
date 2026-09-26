"""The review the statute asks the employer to do, and nobody does.

Labor Code 6401.9(d)(1)(B), last sentence: "The log shall be reviewed during
the periodic reviews of the plan required in subparagraph (L) of paragraph (2)
of subdivision (c)." And (c)(2)(L): "The plan shall be reviewed at least
annually, when a deficiency is observed or becomes apparent, and after a
workplace violence incident."

So the log is not a filing cabinet. Reading it is itself a statutory duty, the
trigger is every incident, and the thing the reader is looking for is in field
(E): the circumstances. The statute's own list of circumstances is a list of
hazards, with "working during a low staffing level" and "isolated or alone"
sitting in the middle of it. A shop whose records keep saying "alone" has been
told something by its own log.

Everything on this page is arithmetic over records a human wrote. No model
touches it, and it would be wrong if one did: a finding here is the employer's
own reading of their own log, and it has to be something they can check by
counting. Each finding prints the rule it applied and the numbers it applied it
to, so an owner can disagree with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .incident_fields import Incident
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    VIOLENCE_TYPES,
    label_for,
)

WEEKS_SHOWN = 12
HOUR_BANDS = (
    ("00:00 to 05:59", 0, 6),
    ("06:00 to 11:59", 6, 12),
    ("12:00 to 17:59", 12, 18),
    ("18:00 to 23:59", 18, 24),
)


@dataclass(frozen=True)
class Tally:
    label: str
    count: int
    of: int

    @property
    def percent(self) -> int:
        return round(100 * self.count / self.of) if self.of else 0


@dataclass(frozen=True)
class Finding:
    """A sentence an owner can check by counting. ``rule`` is printed beside
    it so nobody has to trust the arithmetic."""

    text: str
    rule: str


@dataclass(frozen=True)
class Review:
    total: int
    unfinished: int
    weeks: list[Tally]
    weeks_note: str
    hours: list[Tally]
    circumstances: list[Tally]
    incident_types: list[Tally]
    violence_types: list[Tally]
    findings: list[Finding]
    answered_circumstances: int
    window_from: Optional[int]
    window_to: Optional[int]


def build(incidents: list[Incident], now_ms: Optional[int] = None) -> Review:
    live = [i for i in incidents if not i.is_purged]
    now = now_ms if now_ms is not None else _now_ms()
    answered = [i for i in live if i.circumstances]
    window_start = now - WEEKS_SHOWN * 7 * 24 * 60 * 60 * 1000
    weeks = _weeks(live, now)
    return Review(
        total=len(live),
        unfinished=len([i for i in live if not i.completed]),
        weeks=weeks,
        weeks_note=_weeks_note(live, weeks, window_start),
        hours=_hours(live),
        circumstances=_tally_lists(answered, "circumstances", CIRCUMSTANCE_OPTIONS),
        incident_types=_tally_lists(live, "incident_types", INCIDENT_TYPES),
        violence_types=_tally_lists(live, "violence_types", VIOLENCE_TYPES),
        findings=_findings(live, answered),
        answered_circumstances=len(answered),
        window_from=window_start,
        window_to=now,
    )


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)


def _weeks(incidents: list[Incident], now: int) -> list[Tally]:
    """The last twelve weeks, oldest first, so the shape of the year reads
    left to right the way a person expects."""
    week_ms = 7 * 24 * 60 * 60 * 1000
    buckets: list[Tally] = []
    for back in range(WEEKS_SHOWN - 1, -1, -1):
        end = now - back * week_ms
        start = end - week_ms
        count = len([i for i in incidents if start < i.occurred_at <= end])
        label = datetime.fromtimestamp(
            (end - week_ms / 2) / 1000, tz=timezone.utc
        ).strftime("%d %b")
        buckets.append(Tally(label, count, len(incidents)))
    return buckets


def _weeks_note(incidents: list[Incident], weeks: list[Tally], window_start: int) -> str:
    """Why the twelve-week chart is empty, when it is.

    Drawn unconditionally, the chart is twelve rows of `0` directly beneath
    "10 records, of which 1 still needs finishing", and the page contradicts
    itself on screen. There are two honest reasons for an empty window and they
    are different things to tell a duty-holder, so it says which.
    """
    if not incidents or any(w.count for w in weeks):
        return ""
    older = [i for i in incidents if i.occurred_at <= window_start]
    if older:
        return (
            f"Nothing in the last {WEEKS_SHOWN} weeks. All "
            f"{len(incidents)} record{'s' if len(incidents) != 1 else ''} in "
            "the book are older than this window, so the chart below is empty "
            "and that is the finding."
        )
    return (
        f"Nothing in the last {WEEKS_SHOWN} weeks. The records in the book are "
        "dated after this window, which means their event times are in the "
        "future and one of them is wrong."
    )


def _hours(incidents: list[Incident]) -> list[Tally]:
    out = []
    for label, start, end in HOUR_BANDS:
        count = 0
        for i in incidents:
            hour = datetime.fromtimestamp(i.occurred_at / 1000, tz=timezone.utc).hour
            if start <= hour < end:
                count += 1
        out.append(Tally(label, count, len(incidents)))
    return out


def _tally_lists(incidents: list[Incident], field_name: str, vocabulary) -> list[Tally]:
    counts: dict[str, int] = {}
    for incident in incidents:
        for value in getattr(incident, field_name):
            counts[value] = counts.get(value, 0) + 1
    tallies = [
        Tally(label_for(vocabulary, value), count, len(incidents))
        for value, count in counts.items()
    ]
    return sorted(tallies, key=lambda t: (-t.count, t.label))


def _findings(live: list[Incident], answered: list[Incident]) -> list[Finding]:
    findings: list[Finding] = []
    alone = [
        i
        for i in answered
        if "isolated_or_alone" in i.circumstances or "low_staffing_level" in i.circumstances
    ]
    if answered and len(alone) * 2 >= len(answered):
        findings.append(
            Finding(
                f"{len(alone)} of the {len(answered)} records that answered (E) say the "
                "worker was isolated, alone, or working during a low staffing level.",
                "Half or more of the answered records carry one of the two "
                "staffing circumstances in 6401.9(d)(2)(E).",
            )
        )
    unfinished = [i for i in live if not i.completed]
    if unfinished:
        oldest = min(unfinished, key=lambda i: i.occurred_at)
        findings.append(
            Finding(
                f"{len(unfinished)} record{'s' if len(unfinished) > 1 else ''} "
                f"still need{'s' if len(unfinished) == 1 else ''} finishing. "
                f"The oldest is from {_day(oldest.occurred_at)}.",
                "Any record where a statutory field (B) to (I) is still empty.",
            )
        )
    no_clip = [i for i in live if i.clip_status != "attached"]
    if no_clip:
        findings.append(
            Finding(
                f"{len(no_clip)} of {len(live)} records have no clip attached.",
                "Clip status is anything other than 'attached'. A shop on "
                "event-only recording will see this on most records.",
            )
        )
    busiest = max(_hours(live), key=lambda t: t.count, default=None)
    if busiest and busiest.count and len(live) >= 3:
        findings.append(
            Finding(
                f"{busiest.count} of {len(live)} records fall between "
                f"{busiest.label}.",
                "The four six-hour bands, counted by the time the incident "
                "occurred, in UTC.",
            )
        )
    if not findings:
        findings.append(
            Finding(
                "Nothing stands out yet. There are too few records to read a "
                "pattern from.",
                "Fewer than the numbers any of the rules above need.",
            )
        )
    return findings


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def due_note(last_review_at: Optional[int], last_incident_at: Optional[int]) -> str:
    """One sentence saying whether a review is owed, since the statute gives
    three separate triggers and an owner will not remember them."""
    if last_review_at is None:
        return (
            "No review of this log has been recorded. 6401.9(c)(2)(L) asks for "
            "one at least annually and after every workplace violence incident."
        )
    if last_incident_at and last_incident_at > last_review_at:
        return (
            "An incident has been recorded since the last review. "
            "6401.9(c)(2)(L) asks for a review after every workplace violence "
            "incident."
        )
    year_ms = 365 * 24 * 60 * 60 * 1000
    if _now_ms() - last_review_at > year_ms:
        return (
            "The last recorded review is more than a year old. "
            "6401.9(c)(2)(L) asks for one at least annually."
        )
    return "No review is owed on the annual trigger or the per-incident trigger."
