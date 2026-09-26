"""One formatter, because two date formats on one document is the commonest
reason a reader stops believing it.

The fixed shape used everywhere in this app's documents:

    2026-03-14 19:07:32 PDT (UTC-07:00)

ISO-ordered date, 24-hour clock, the zone abbreviation a reader recognises,
and the numeric offset in brackets because abbreviations are ambiguous. The
minus sign in the bracketed offset is a true minus, U+2212, not a hyphen.
Alongside it, in the machine record and the manifest, the RFC 3339 string.

Which zone. Ring timestamps are epoch milliseconds, which is an instant and
carries no local offset, so the premises supplies its own zone on the settings
screen. Where it has not, everything prints in UTC and the provenance block
says, in as many words, that the local offset at the premises was not recorded
and has not been assumed. Inventing a plausible local time is precisely the
kind of fabrication section 4.2 rule 3 is about.

Nothing else in this app formats a time. Every screen and both documents call
in here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

MINUS = "−"  # true minus, not a hyphen
UNKNOWN_ZONE_NOTE = (
    "Times are shown in UTC. The local offset at the premises is not recorded "
    "and has not been assumed."
)

# A short list rather than the whole tz database: these are the zones a
# California premises could plausibly be in, plus UTC. Anything else the owner
# types is accepted if zoneinfo knows it.
COMMON_ZONES = (
    ("", "Not recorded (show times in UTC)"),
    ("America/Los_Angeles", "Pacific time (America/Los_Angeles)"),
    ("America/Denver", "Mountain time (America/Denver)"),
    ("America/Phoenix", "Arizona (America/Phoenix)"),
    ("America/Chicago", "Central time (America/Chicago)"),
    ("America/New_York", "Eastern time (America/New_York)"),
    ("UTC", "UTC"),
)


def zone(name: str):
    """The zone, or UTC when the premises has not recorded one or has
    recorded one this machine's tz database does not know."""
    if not name:
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _at(ms: int, tz_name: str) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=zone(tz_name))


def canonical(ms: Optional[int], tz_name: str = "") -> str:
    """The one displayed form. ``None`` prints as the words, never as a
    blank, because a blank in a record looks like something fell out."""
    if ms is None:
        return "Not recorded"
    at = _at(ms, tz_name)
    return f"{at:%Y-%m-%d %H:%M:%S} {_abbrev(at)} ({_offset(at)})"


def clock(ms: Optional[int], tz_name: str = "") -> str:
    """Just the time of day, for the second and later mentions inside one
    window. Still never bare: the zone rides along."""
    if ms is None:
        return "Not recorded"
    at = _at(ms, tz_name)
    return f"{at:%H:%M:%S} {_abbrev(at)}"


def rfc3339(ms: Optional[int], tz_name: str = "") -> str:
    if ms is None:
        return ""
    return _at(ms, tz_name).isoformat(timespec="seconds")


def day(ms: Optional[int], tz_name: str = "") -> str:
    return "Not recorded" if ms is None else f"{_at(ms, tz_name):%Y-%m-%d}"


def prose(ms: Optional[int], tz_name: str = "") -> str:
    """For running sentences, where the month is spelled out to kill every
    possible reading of the digits."""
    if ms is None:
        return "not recorded"
    at = _at(ms, tz_name)
    return f"{at:%H:%M} on {at.day} {at:%B %Y} {_abbrev(at)}"


def window(start: Optional[int], end: Optional[int], tz_name: str = "") -> str:
    """Two endpoints and a duration, never one of the three."""
    if start is None or end is None:
        return "Not recorded"
    first, last = _at(start, tz_name), _at(end, tz_name)
    span = timedelta(milliseconds=end - start)
    minutes, seconds = divmod(int(span.total_seconds()), 60)
    return (
        f"{first:%Y-%m-%d %H:%M:%S} to {last:%H:%M:%S} {_abbrev(last)} "
        f"({_offset(last)}) ({minutes} min {seconds:02d} s)"
    )


def _abbrev(at: datetime) -> str:
    name = at.tzname() or "UTC"
    # zoneinfo returns a numeric string for zones with no abbreviation.
    return "UTC" if name in ("UTC", "+00:00") else name


def _offset(at: datetime) -> str:
    delta = at.utcoffset() or timedelta(0)
    total = int(delta.total_seconds())
    sign = MINUS if total < 0 else "+"
    hours, remainder = divmod(abs(total), 3600)
    return f"UTC{sign}{hours:02d}:{remainder // 60:02d}"


def zone_note(tz_name: str) -> str:
    if tz_name:
        return f"Times are shown in {tz_name}, the zone recorded for this premises."
    return UNKNOWN_ZONE_NOTE
