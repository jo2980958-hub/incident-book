#!/usr/bin/env python3
"""Signs a fixture webhook payload the same way the app verifies it, and
posts it to a running Incident Book instance's /webhooks/ring endpoint.

This is what drives the demo, per SPEC.md: the app never knows or cares
that the signed webhook came from this script instead of Ring's servers.

Usage:
    python tools/replay_webhook.py motion_human
    python tools/replay_webhook.py button_press
    python tools/replay_webhook.py motion_human --url http://localhost:5057/webhooks/ring
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FIXTURE_FILES = {
    "motion_human": "webhook_motion_human.json",
    "button_press": "webhook_button_press.json",
}

DAY_MS = 24 * 60 * 60 * 1000

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.webhooks import sign  # noqa: E402


def anchor_ms() -> int:
    """The newest ``created_at`` across the fixtures, which is what "now" means
    to a set of timestamps that were written as a group."""
    return max(
        json.loads((FIXTURES_DIR / name).read_text())["created_at"]
        for name in FIXTURE_FILES.values()
    )


def shifted_to_today(created_at: int, anchor: int, now_ms: int) -> int:
    """The fixture's timestamp moved forward by whole days, so the newest of
    them lands today.

    The fixtures' own comment says their timestamps are "not tied to a real
    calendar date", which was true when they were written and is not the same
    as harmless. Left alone, every record the documented demo produces reads

        Button pressed   2026-09-23 13:53:34 UTC
        Event time       2025-09-22 00:15:00 UTC

    367 days apart, side by side, on the confirmation screen the README sends a
    judge to, and the Review page's twelve-week chart is twelve zeros beside
    "10 records".

    Whole days, never hours: the two fixtures are 50 seconds apart and the hour
    they happened at is what the Review page's time-of-day chart is about. A
    partial-day shift would move a small-hours incident into the afternoon.
    """
    return created_at + ((now_ms - anchor) // DAY_MS) * DAY_MS


def payload_for(fixture: str, as_written: bool = False, now_ms: int | None = None) -> dict:
    """The body this tool signs and posts, with its timestamp already moved."""
    payload = json.loads((FIXTURES_DIR / FIXTURE_FILES[fixture]).read_text())
    payload.pop("_comment", None)
    if not as_written:
        payload["created_at"] = shifted_to_today(
            payload["created_at"], anchor_ms(), now_ms or int(time.time() * 1000)
        )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", choices=sorted(FIXTURE_FILES))
    parser.add_argument("--url", default="http://localhost:5057/webhooks/ring")
    parser.add_argument(
        "--secret", default=os.environ.get("RING_WEBHOOK_SECRET", "demo-shared-secret")
    )
    parser.add_argument(
        "--as-written",
        action="store_true",
        help="Send the fixture's own timestamp instead of moving it to today",
    )
    args = parser.parse_args()

    payload = payload_for(args.fixture, as_written=args.as_written)
    raw_body = json.dumps(payload).encode("utf-8")
    signature = sign(args.secret, raw_body)

    req = urllib.request.Request(
        args.url,
        data=raw_body,
        headers={"Content-Type": "application/json", "X-Signature": signature},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        print(f"POST {args.url} -> {resp.status}")
        print(resp.read().decode())


if __name__ == "__main__":
    main()
