"""Incident <-> dict for the store's JSON column, and the schema.

``incident_from_dict`` reads records written by the first build of this app as
well as by this one. A violent incident log is kept five years, so a schema
change has to be a thing the record survives, not a thing that empties the
book. Where a field was singular and the statute says plural, the old single
value becomes a list of one; where an option value was a paraphrase, it maps
to the statute's own value through ``statute.migrate_value``.
"""

from __future__ import annotations

from .incident_fields import Incident
from .statute import migrate_value

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    premises_id TEXT NOT NULL DEFAULT '',
    occurred_at INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL DEFAULT 0,
    completed   INTEGER NOT NULL DEFAULT 0,
    purged_at   INTEGER,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_occurred ON incidents (occurred_at DESC);
CREATE INDEX IF NOT EXISTS incidents_premises ON incidents (premises_id);

CREATE TABLE IF NOT EXISTS consent_grants (
    device_id TEXT PRIMARY KEY,
    granted_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS premises (
    premises_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_registrations (
    device_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    incident_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

-- Append only. Nothing in the app updates or deletes a row here, which is the
-- point: a statutory log whose entries can change silently is worth nothing.
CREATE TABLE IF NOT EXISTS revisions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    at INTEGER NOT NULL,
    actor_name TEXT NOT NULL DEFAULT '',
    actor_title TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    changes TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS revisions_incident ON revisions (incident_id, seq);

CREATE TABLE IF NOT EXISTS retention_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at INTEGER NOT NULL,
    incident_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_name TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_LIST_FIELDS = ("event_ids", "violence_types", "circumstances", "incident_types")
_JSON_LIST_FIELDS = ("clip_attempts",)
_SIMPLE = (
    "incident_id", "premises_id", "device_id", "location", "occurred_at",
    "tapped_at", "event_summary", "clip_status", "clip_sha256", "clip_source",
    "clip_content_type", "clip_window_start", "clip_window_end",
    "snapshot_sha256", "snapshot_source", "snapshot_content_type",
    "description", "perpetrator_class",
    "location_class", "location_detail", "consequences_response",
    "consequences_actions", "completed_by", "completed_by_title",
    "completed_at", "created_at", "retain_until", "completed", "purged_at",
)


def incident_to_dict(incident: Incident) -> dict:
    out = {name: getattr(incident, name) for name in _SIMPLE}
    for name in _LIST_FIELDS + _JSON_LIST_FIELDS:
        out[name] = list(getattr(incident, name))
    return out


def incident_from_dict(d: dict) -> Incident:
    return Incident(
        incident_id=d["incident_id"],
        premises_id=d.get("premises_id", ""),
        device_id=d["device_id"],
        location=d["location"],
        occurred_at=d["occurred_at"],
        tapped_at=d.get("tapped_at", 0),
        event_ids=list(d.get("event_ids", [])),
        event_summary=d.get("event_summary", ""),
        clip_status=d.get("clip_status", "not_attempted"),
        clip_sha256=d.get("clip_sha256"),
        clip_source=d.get("clip_source"),
        clip_content_type=d.get("clip_content_type", ""),
        clip_window_start=d.get("clip_window_start"),
        clip_window_end=d.get("clip_window_end"),
        clip_attempts=list(d.get("clip_attempts", [])),
        snapshot_sha256=d.get("snapshot_sha256"),
        snapshot_source=d.get("snapshot_source"),
        snapshot_content_type=d.get("snapshot_content_type", ""),
        violence_types=_plural(d, "violence_types", "violence_type"),
        description=d.get("description", ""),
        perpetrator_class=_single(d, "perpetrator_class"),
        circumstances=_plural(d, "circumstances", None),
        location_class=d.get("location_class"),
        location_detail=d.get("location_detail", ""),
        incident_types=_plural(d, "incident_types", "incident_type"),
        consequences_response=d.get("consequences_response", d.get("consequences", "")),
        consequences_actions=d.get("consequences_actions", ""),
        completed_by=d.get("completed_by", ""),
        completed_by_title=d.get("completed_by_title", ""),
        completed_at=d.get("completed_at"),
        created_at=d["created_at"],
        retain_until=d["retain_until"],
        completed=bool(d.get("completed", False)),
        purged_at=d.get("purged_at"),
    )


def _plural(d: dict, plural_key: str, old_singular_key) -> list[str]:
    values = d.get(plural_key)
    if values is None and old_singular_key:
        one = d.get(old_singular_key)
        values = [one] if one else []
    return [migrate_value(plural_key, v) for v in (values or [])]


def _single(d: dict, key: str):
    value = d.get(key)
    return migrate_value(key, value) if value else None
