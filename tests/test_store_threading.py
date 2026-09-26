"""Regression test for a bug the main test suite did not catch: Flask's
dev server (and any real deployment) handles each request on its own
thread, but Flask's test client does not, so a naive sqlite3 connection
worked in tests and crashed with 'SQLite objects created in a thread can
only be used in that same thread' the first time it was run live.
"""

import threading

from app.incident import Incident
from app.store import IncidentStore


def test_save_and_get_incident_works_from_a_different_thread(tmp_path):
    store = IncidentStore(str(tmp_path / "threaded.db"), evidence_dir=tmp_path / "evidence")
    errors = []

    def worker():
        try:
            incident = Incident(
                incident_id="inc_thread", device_id="d", location="loc", occurred_at=1000
            )
            store.save_incident(incident)
            loaded = store.get_incident("inc_thread")
            assert loaded is not None
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)

    assert not errors, f"cross-thread sqlite access failed: {errors}"
    store.close()
