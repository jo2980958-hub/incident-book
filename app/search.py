"""Finding a record again, which is the whole difference between a log and a
pile.

This app deliberately splits the tap from the form, so on any ordinary day the
book contains half-written records. That is a kindness to a shaking hand on day
one and a problem by day thirty, when there are forty of them and the one an
insurer is asking about happened in March. So: filter by premises, by date, by
what kind of incident it was, and by whether it still needs finishing, plus a
plain text search over what people wrote.

The SQL is built here rather than in the store so the store stays a place that
reads and writes rows. Every value is bound, never interpolated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

STATUSES = (
    ("any", "Any status"),
    ("needs_finishing", "Needs finishing"),
    ("complete", "Complete"),
    ("purged", "Purged after five years"),
)

_TEXT_COLUMNS = (
    "$.description",
    "$.consequences_response",
    "$.consequences_actions",
    "$.location",
    "$.location_detail",
    "$.completed_by",
    "$.incident_id",
)


@dataclass(frozen=True)
class Query:
    text: str = ""
    premises_id: str = ""
    device_id: str = ""
    status: str = "any"
    incident_type: str = ""
    violence_type: str = ""
    circumstance: str = ""
    date_from: str = ""  # YYYY-MM-DD, inclusive
    date_to: str = ""  # YYYY-MM-DD, inclusive

    @property
    def is_filtered(self) -> bool:
        return any(
            [
                self.text.strip(),
                self.premises_id,
                self.device_id,
                self.status not in ("", "any"),
                self.incident_type,
                self.violence_type,
                self.circumstance,
                self.date_from,
                self.date_to,
            ]
        )

    def without(self, field_name: str) -> "Query":
        """The same search minus one filter, so each active filter can be
        removed on its own from the screen."""
        values = self.__dict__.copy()
        values[field_name] = "any" if field_name == "status" else ""
        return Query(**values)


def build_sql(query: Query) -> tuple[str, list]:
    """Returns the WHERE fragment and its bound parameters."""
    clauses: list[str] = []
    params: list = []

    if query.premises_id:
        clauses.append("premises_id = ?")
        params.append(query.premises_id)
    if query.device_id:
        clauses.append("json_extract(data, '$.device_id') = ?")
        params.append(query.device_id)

    if query.status == "needs_finishing":
        clauses.append("completed = 0 AND purged_at IS NULL")
    elif query.status == "complete":
        clauses.append("completed = 1 AND purged_at IS NULL")
    elif query.status == "purged":
        clauses.append("purged_at IS NOT NULL")

    _add_list_filter(clauses, params, "incident_types", query.incident_type)
    _add_list_filter(clauses, params, "violence_types", query.violence_type)
    _add_list_filter(clauses, params, "circumstances", query.circumstance)

    start = _day_start_ms(query.date_from)
    if start is not None:
        clauses.append("occurred_at >= ?")
        params.append(start)
    end = _day_end_ms(query.date_to)
    if end is not None:
        clauses.append("occurred_at <= ?")
        params.append(end)

    text = query.text.strip()
    if text:
        ors = " OR ".join(
            f"json_extract(data, '{path}') LIKE ?" for path in _TEXT_COLUMNS
        )
        clauses.append(f"({ors})")
        params.extend([f"%{text}%"] * len(_TEXT_COLUMNS))

    where = " AND ".join(clauses) if clauses else "1 = 1"
    return where, params


def _add_list_filter(clauses: list, params: list, json_field: str, value: str) -> None:
    if not value:
        return
    clauses.append(
        f"EXISTS (SELECT 1 FROM json_each(data, '$.{json_field}') WHERE value = ?)"
    )
    params.append(value)


def _day_start_ms(day: str) -> Optional[int]:
    parsed = _parse_day(day)
    return int(parsed.timestamp() * 1000) if parsed else None


def _day_end_ms(day: str) -> Optional[int]:
    parsed = _parse_day(day)
    if parsed is None:
        return None
    return int((parsed + timedelta(days=1)).timestamp() * 1000) - 1


def _parse_day(day: str) -> Optional[datetime]:
    day = (day or "").strip()
    if not day:
        return None
    try:
        return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
