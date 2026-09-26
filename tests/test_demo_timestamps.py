"""The demo's records were dated a year before they were captured.

Following the README, every record read

    Button pressed   2026-09-23 13:53:34 UTC
    Event time       2025-09-22 00:15:00 UTC

367 days apart, side by side, on the confirmation screen. The records list then
read `2025-09-22` on every row while the amendment trail read `2026-09-23`, and
the Review page's twelve-week chart was twelve zeros directly beneath "10
records, of which 1 still needs finishing".

`fixtures/webhook_motion_human.json` is not wrong: its own comment says the
timestamps are "not tied to a real calendar date", which was true a year ago.
The replay tool is what has to move them.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from replay_webhook import (  # noqa: E402
    DAY_MS,
    FIXTURE_FILES,
    anchor_ms,
    payload_for,
    shifted_to_today,
)

from app.incident_fields import Incident  # noqa: E402
from app.review import WEEKS_SHOWN, build  # noqa: E402

NOW = int(datetime(2026, 9, 23, 13, 53, tzinfo=timezone.utc).timestamp() * 1000)


def _fixture(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / FIXTURE_FILES[name]).read_text())


def _day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def test_the_replayed_event_lands_on_the_day_it_is_replayed():
    anchor = anchor_ms()
    shifted = shifted_to_today(_fixture("motion_human")["created_at"], anchor, NOW)

    assert _day(shifted) == "2026-09-23"


def test_the_tool_sends_the_moved_timestamp_and_not_the_fixture_s_own():
    sent = payload_for("motion_human", now_ms=NOW)

    assert _day(sent["created_at"]) == "2026-09-23"
    assert sent["created_at"] != _fixture("motion_human")["created_at"]
    assert sent["event_type"] == "motion_detected"
    assert "_comment" not in sent


def test_the_fixture_s_own_timestamp_is_still_available_on_request():
    sent = payload_for("motion_human", as_written=True, now_ms=NOW)

    assert sent["created_at"] == _fixture("motion_human")["created_at"]


def test_the_two_fixtures_keep_the_fifty_seconds_between_them():
    anchor = anchor_ms()
    a = shifted_to_today(_fixture("button_press")["created_at"], anchor, NOW)
    b = shifted_to_today(_fixture("motion_human")["created_at"], anchor, NOW)

    assert b - a == _fixture("motion_human")["created_at"] - _fixture("button_press")["created_at"]
    assert b - a == 50_000


def test_the_shift_is_whole_days_so_the_hour_of_day_survives():
    """The Review page charts records by time of day; a partial-day shift would
    move a small-hours incident into the afternoon."""
    original = _fixture("motion_human")["created_at"]
    shifted = shifted_to_today(original, anchor_ms(), NOW)

    assert (shifted - original) % DAY_MS == 0
    assert _day(original) != _day(shifted)


def test_a_replay_today_is_never_dated_in_the_future():
    now = int(time.time() * 1000)
    anchor = anchor_ms()

    for name in FIXTURE_FILES:
        assert shifted_to_today(_fixture(name)["created_at"], anchor, now) <= now


def _book(occurred_at: int, count: int = 10) -> list[Incident]:
    return [
        Incident(
            incident_id=f"inc_{n}", device_id="d", location="Front counter",
            occurred_at=occurred_at, created_at=NOW,
        )
        for n in range(count)
    ]


def test_a_record_replayed_today_lands_inside_the_twelve_week_window():
    occurred = shifted_to_today(_fixture("motion_human")["created_at"], anchor_ms(), NOW)

    review = build(_book(occurred), now_ms=NOW)

    assert review.weeks_note == ""
    assert sum(w.count for w in review.weeks) == 10


def test_the_stale_fixture_would_still_have_produced_twelve_zeros():
    """The precondition, so this file fails if the defect ever comes back."""
    review = build(_book(_fixture("motion_human")["created_at"]), now_ms=NOW)

    assert [w.count for w in review.weeks] == [0] * WEEKS_SHOWN


def test_an_empty_window_says_so_instead_of_drawing_twelve_empty_rows():
    review = build(_book(_fixture("motion_human")["created_at"]), now_ms=NOW)

    assert "Nothing in the last 12 weeks" in review.weeks_note
    assert "older than this window" in review.weeks_note
    assert "10 records" in review.weeks_note


def test_a_window_holding_records_dated_ahead_of_it_says_something_different():
    review = build(_book(NOW + 400 * DAY_MS), now_ms=NOW)

    assert "in the future" in review.weeks_note


def test_an_empty_book_gets_no_note_at_all():
    """It already has an empty state of its own, and two would be worse."""
    assert build([], now_ms=NOW).weeks_note == ""


def test_the_review_page_prints_the_note_in_place_of_the_chart():
    page = (ROOT / "app" / "templates" / "review.html").read_text()

    assert "{% if review.weeks_note %}" in page
    block = page[page.index("{% if review.weeks_note %}"):]
    block = block[: block.index("{% endif %}")]
    assert "review.weeks_note" in block
    assert "Records by week" in block


def test_the_unfinished_finding_agrees_with_itself_about_number():
    one = build(_book(NOW - DAY_MS, count=1), now_ms=NOW)
    three = build(_book(NOW - DAY_MS, count=3), now_ms=NOW)

    assert any("1 record still needs finishing" in f.text for f in one.findings)
    assert any("3 records still need finishing" in f.text for f in three.findings)
