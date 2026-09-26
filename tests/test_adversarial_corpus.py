"""The shared adversarial corpus, driven through the real drafting path.

`tests/fixtures/adversarial.jsonl` is shared, copied rather than imported,
across several related projects, so a defect found in one is checked in all.
Nothing in it was written from this app's lists.

Each row is given to a stubbed model and pushed through `draft_narrative`, the
function the web route calls, and the assertion is on the draft that comes back
-- not on a helper two layers up. A row this app does not claim carries its
reason in `NOT_OURS`, and the reason is reviewed like any other line of code.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from factories import blank_incident

from app.bedrock import StubRunner
from app.drafting import draft_narrative

ROWS = [
    json.loads(line)
    for line in (pathlib.Path(__file__).parent / "fixtures/adversarial.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
]

# What the worker typed. Everything the model may write has to come from here,
# from the recorded event details, or from outside the hazardous classes.
WORDS = "a man came over the counter shouting about the till, I called 911"

NOT_OURS = {
    "apos-01": "pronouns are not this app's rule: the draft is told to write 'a person'",
    "apos-02": "no carer, no booked visit, and 'carer's' is not a hazardous class here",
    "apos-03": "same",
    "para-02": "a courier at an address is another app's subject; no class and no figure",
    "para-03": "an inference about a door; this app's model never writes about a door",
    "advice-01": "no clinical field anywhere in a violent incident log",
    "advice-02": "same",
    "advice-03": "same -- and 999 would be caught as a figure, which is not the row's point",
    "health-01": "no clinical field; a fabricated fall names no class and states no figure",
    "health-02": "same",
    "health-03": "same",
    "inject-01": "no markdown destination: this app writes HTML, PDF and CSV",
    "inject-02": "a draft is a proposal a human edits, never an instruction anything executes",
    "inject-03": "Jinja autoescaping owns the attribute boundary; see tests/test_server.py",
    "inject-04": "same boundary, same owner",
    "inject-05": "control characters are dropped before matching; the CSV and PDF boundaries own them",
    "inject-06": "the CSV boundary owns formula injection; see tests/test_export_csv.py",
    "uni-01": "the word being hidden is 'not' in 'did not come', which is a different app's word-hiding class, not one of ours",
    "uni-02": "a zero-width space inside 'carer' hides no word this app's classes hold",
    "uni-04": "same: 'carer' is not a class this app holds, so there is nothing for the fold to protect",
    "uni-05": "same. uni-03 is the row that tests this app's fold, and it is claimed",
    "clean-05": '"proof of" is on this app\'s overclaim list on purpose -- see incident_language.py',
    "clean-07": "this app grounds a figure in the worker's own words, and 08:15 is not in them",
}


def _blocked(text: str) -> bool:
    draft = draft_narrative(
        StubRunner([{"tool_input": {"description": text}, "usage": {}}]),
        blank_incident(),
        WORDS,
    )
    return draft.status == "rejected"


@pytest.mark.parametrize("row", ROWS, ids=[r["id"] for r in ROWS])
def test_the_shared_adversarial_corpus(row):
    if row["id"] in NOT_OURS:
        pytest.skip(NOT_OURS[row["id"]])
    blocked = _blocked(row["text"])
    if row["expect"] == "blocked":
        assert blocked, f'{row["id"]} reached statute field (C): {row["why"]}'
    else:
        assert not blocked, f'{row["id"]} was a false positive: {row["why"]}'


def test_the_corpus_is_loaded_and_more_than_half_of_it_is_claimed():
    """Non-vacuity, per GUARD-STANDARD.md §7 class 6: proof the search ran, and
    proof that what it searched for is there to find."""
    assert len(ROWS) >= 40
    claimed = [r for r in ROWS if r["id"] not in NOT_OURS]
    assert len(claimed) >= 15
    assert {r["expect"] for r in claimed} == {"blocked", "clean"}
    # The rows in this app's own hazard areas are not skippable. A guard that
    # could opt out of the statutory and identifying rows would be claiming
    # nothing while the file still looked wired in.
    ours = {"accusation", "statutory", "pii"}
    for row in ROWS:
        if ours & set(row["tags"]):
            assert row["id"] not in NOT_OURS, f'{row["id"]} is exactly what this app guards'
    assert sum(1 for r in ROWS if ours & set(r["tags"])) >= 6
    assert set(NOT_OURS) <= {r["id"] for r in ROWS}, "a skip names a row that is not in the file"
    assert all(reason.strip() for reason in NOT_OURS.values())
