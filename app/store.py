"""SQLite persistence.

One table per thing the product has to remember: incidents, the premises they
belong to, what the shop knows about each camera, the model's drafts, the
amendment trail, the retention ledger, and the per-device consent timestamp.
Evidence bytes go to files on disk beside a SHA-256 the incident carries.

Two tables are append only and nothing in this app updates or deletes a row in
either. ``revisions`` is the amendment trail: a statutory log whose entries can
change without saying so is worth nothing to an inspector, and one that cannot
be corrected at all is wrong forever. ``retention_events`` is the purge ledger,
for the same reason in the other direction.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .drafting import Draft
from .incident_fields import Incident
from .premises import DeviceRegistration, Premises
from .search import Query, build_sql
from .store_serialize import SCHEMA, incident_from_dict, incident_to_dict


class IncidentStore:
    def __init__(self, db_path: str, evidence_dir: Optional[Path] = None):
        self.db_path = db_path
        self.evidence_dir = evidence_dir or Path(db_path).resolve().parent / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: Flask's dev server handles each request on
        # its own thread. A single small-premises kiosk has at most a couple
        # of concurrent taps, so one shared connection with SQLite's own
        # locking is enough. Found live, not by the test suite, which uses
        # Flask's single-threaded test client.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- incidents ------------------------------------------------------

    def save_incident(self, incident: Incident) -> None:
        self._conn.execute(
            "INSERT INTO incidents (incident_id, premises_id, occurred_at, "
            "created_at, completed, purged_at, data) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(incident_id) DO UPDATE SET premises_id = excluded.premises_id, "
            "occurred_at = excluded.occurred_at, completed = excluded.completed, "
            "purged_at = excluded.purged_at, data = excluded.data",
            (
                incident.incident_id,
                incident.premises_id,
                incident.occurred_at,
                incident.created_at,
                int(incident.completed),
                incident.purged_at,
                json.dumps(incident_to_dict(incident)),
            ),
        )
        self._conn.commit()

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        row = self._conn.execute(
            "SELECT data FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return incident_from_dict(json.loads(row[0])) if row else None

    def list_incidents(self, query: Optional[Query] = None) -> list[Incident]:
        where, params = build_sql(query or Query())
        rows = self._conn.execute(
            f"SELECT data FROM incidents WHERE {where} "
            "ORDER BY occurred_at DESC, created_at DESC",
            params,
        ).fetchall()
        return [incident_from_dict(json.loads(r[0])) for r in rows]

    def counts(self) -> dict:
        """The three numbers the list header shows, in one query rather than
        by loading every record to count them."""
        row = self._conn.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN completed = 0 AND purged_at IS NULL THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN purged_at IS NOT NULL THEN 1 ELSE 0 END), "
            "MIN(occurred_at) FROM incidents"
        ).fetchone()
        return {
            "total": row[0] or 0,
            "needs_finishing": row[1] or 0,
            "purged": row[2] or 0,
            "earliest_occurred_at": row[3],
        }

    # -- premises and devices --------------------------------------------

    def save_premises(self, record: Premises) -> None:
        self._conn.execute(
            "INSERT INTO premises (premises_id, data) VALUES (?, ?) "
            "ON CONFLICT(premises_id) DO UPDATE SET data = excluded.data",
            (record.premises_id, json.dumps(record.to_dict())),
        )
        self._conn.commit()

    def get_premises(self, premises_id: str) -> Optional[Premises]:
        row = self._conn.execute(
            "SELECT data FROM premises WHERE premises_id = ?", (premises_id,)
        ).fetchone()
        return Premises.from_dict(json.loads(row[0])) if row else None

    def list_premises(self) -> list[Premises]:
        rows = self._conn.execute("SELECT data FROM premises").fetchall()
        return sorted(
            (Premises.from_dict(json.loads(r[0])) for r in rows),
            key=lambda p: (p.name.lower(), p.created_at),
        )

    def save_device_registration(self, record: DeviceRegistration) -> None:
        self._conn.execute(
            "INSERT INTO device_registrations (device_id, data) VALUES (?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET data = excluded.data",
            (record.device_id, json.dumps(record.to_dict())),
        )
        self._conn.commit()

    def get_device_registration(self, device_id: str) -> Optional[DeviceRegistration]:
        row = self._conn.execute(
            "SELECT data FROM device_registrations WHERE device_id = ?", (device_id,)
        ).fetchone()
        return DeviceRegistration.from_dict(json.loads(row[0])) if row else None

    # -- model drafts -----------------------------------------------------

    def save_draft(self, draft: Draft) -> None:
        self._conn.execute(
            "INSERT INTO drafts (incident_id, data) VALUES (?, ?) "
            "ON CONFLICT(incident_id) DO UPDATE SET data = excluded.data",
            (draft.incident_id, json.dumps(draft.to_dict())),
        )
        self._conn.commit()

    def get_draft(self, incident_id: str) -> Optional[Draft]:
        row = self._conn.execute(
            "SELECT data FROM drafts WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return Draft.from_dict(json.loads(row[0])) if row else None

    def delete_draft(self, incident_id: str) -> bool:
        """Used only by retention.py. The draft holds the worker's raw words
        and the model's proposal, both unredacted, so it goes when the
        narrative goes. Returns whether there was one."""
        cursor = self._conn.execute(
            "DELETE FROM drafts WHERE incident_id = ?", (incident_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # -- the amendment trail (append only) --------------------------------

    def add_revision(
        self,
        incident_id: str,
        kind: str,
        changes: dict,
        actor_name: str = "",
        actor_title: str = "",
        note: str = "",
        at: Optional[int] = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO revisions (incident_id, at, actor_name, actor_title, "
            "kind, changes, note) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                incident_id,
                at if at is not None else int(time.time() * 1000),
                actor_name,
                actor_title,
                kind,
                json.dumps(changes),
                note,
            ),
        )
        self._conn.commit()

    def revisions(self, incident_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT seq, at, actor_name, actor_title, kind, changes, note "
            "FROM revisions WHERE incident_id = ? ORDER BY seq",
            (incident_id,),
        ).fetchall()
        return [
            {
                "seq": r[0],
                "at": r[1],
                "actor_name": r[2],
                "actor_title": r[3],
                "kind": r[4],
                "changes": json.loads(r[5]),
                "note": r[6],
            }
            for r in rows
        ]

    def revision_count(self, incident_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM revisions WHERE incident_id = ?", (incident_id,)
        ).fetchone()
        return row[0] or 0

    # -- the retention ledger (append only) -------------------------------

    def add_retention_event(
        self, incident_id: str, action: str, actor_name: str = "", note: str = ""
    ) -> None:
        self._conn.execute(
            "INSERT INTO retention_events (at, incident_id, action, actor_name, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (int(time.time() * 1000), incident_id, action, actor_name, note),
        )
        self._conn.commit()

    def retention_events(self, limit: int = 200) -> list[dict]:
        rows = self._conn.execute(
            "SELECT seq, at, incident_id, action, actor_name, note "
            "FROM retention_events ORDER BY seq DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "seq": r[0],
                "at": r[1],
                "incident_id": r[2],
                "action": r[3],
                "actor_name": r[4],
                "note": r[5],
            }
            for r in rows
        ]

    # -- evidence bytes ---------------------------------------------------

    def save_evidence(self, incident_id: str, kind: str, content: bytes) -> Path:
        """kind is 'clip' or 'snapshot'. Returns the path written."""
        path = self.evidence_dir / f"{incident_id}.{kind}.bin"
        path.write_bytes(content)
        return path

    def load_evidence(self, incident_id: str, kind: str) -> Optional[bytes]:
        path = self.evidence_dir / f"{incident_id}.{kind}.bin"
        return path.read_bytes() if path.exists() else None

    def delete_evidence(self, incident_id: str) -> list[str]:
        """Used only by retention.py, once the five years are up. Returns what
        it removed so the ledger can record it by name."""
        removed = []
        for kind in ("clip", "snapshot"):
            path = self.evidence_dir / f"{incident_id}.{kind}.bin"
            if path.exists():
                path.unlink()
                removed.append(path.name)
        return removed

    # -- consent time-gate -------------------------------------------------

    def record_consent_grant(self, device_id: str, granted_at: int) -> None:
        self._conn.execute(
            "INSERT INTO consent_grants (device_id, granted_at) VALUES (?, ?) "
            "ON CONFLICT(device_id) DO UPDATE SET granted_at = excluded.granted_at",
            (device_id, granted_at),
        )
        self._conn.commit()

    def get_consent_granted_at(self, device_id: str) -> Optional[int]:
        row = self._conn.execute(
            "SELECT granted_at FROM consent_grants WHERE device_id = ?", (device_id,)
        ).fetchone()
        return row[0] if row else None

    # -- settings ----------------------------------------------------------

    def set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default
