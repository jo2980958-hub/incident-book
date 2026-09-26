"""Small shared constants, kept out of server.py so create_app() stays
readable and the blueprint modules can import these without importing each
other.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = APP_DIR.parent / "instance" / "incident_book.db"
WEBHOOK_SECRET = os.environ.get("RING_WEBHOOK_SECRET", "demo-shared-secret")
CLIP_WINDOW_MS = 90_000  # ninety seconds either side, per SPEC.md

# Printed on every document. A reader has to be able to say which version of
# the software produced the thing in their hand, and which version of the form
# it is, the way OSHA's own forms carry "Form 300 (Rev. 04/2004)".
APP_VERSION = "2.0.0"
FORM_ID_LOG = "IB-VIL Rev. 2026-09"
FORM_ID_PACK = "IB-PACK Rev. 2026-09"
