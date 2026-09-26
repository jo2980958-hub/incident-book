"""A refusal has to stay inside the book.

A mistyped record id dropped out of the dark app into Werkzeug's default
"Not Found" — bare white, Times, two words — and so did every `abort()` in
`app/`, which is how the two statutory refusals and the purge guard were
presented. There was no `@app.errorhandler` anywhere.

The purge guard also printed its deadline as epoch milliseconds.
"""

from datetime import datetime, timezone

import pytest
from factories import complete_incident

from app.retention import RetainedTooRecently, purge
from app.incident_fields import five_years_after

NOW = 2_000_000_000_000


def test_an_unknown_record_is_refused_on_the_book_s_own_page(client):
    response = client.get("/incidents/nope-123/edit")

    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "There is nothing in the book under that" in body
    assert "Incident Book" in body
    assert 'class="book"' in body


def test_an_unknown_page_lands_there_too_and_names_the_address(client):
    response = client.get("/no-such-page")

    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "Incident Book" in body
    assert "/no-such-page" in body
    assert "check your spelling" not in body


def test_the_error_page_carries_the_footer_that_names_the_statute(client):
    body = client.get("/incidents/nope-123/edit").get_data(as_text=True)

    assert "6401.9(f)(3)" in body


def test_the_error_page_says_nothing_was_written(client):
    body = client.get("/incidents/nope-123/edit").get_data(as_text=True)

    assert "Nothing was written." in body


def test_a_refusal_with_a_reason_prints_the_reason(client):
    response = client.post("/settings/device", data={"device_id": ""})

    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "a device id is required" in body
    assert "That request could not be acted on" in body


def test_the_purge_guard_names_a_date_and_not_epoch_milliseconds(store):
    incident = complete_incident("inc_recent")
    incident.created_at = NOW - 1000
    incident.retain_until = five_years_after(incident.created_at)
    store.save_incident(incident)

    with pytest.raises(RetainedTooRecently) as caught:
        purge(store, incident, actor_name="A. Owner", now_ms=NOW)

    message = str(caught.value)
    due = datetime.fromtimestamp(incident.earliest_deletion / 1000, tz=timezone.utc)
    assert due.strftime("%Y-%m-%d") in message
    assert str(incident.earliest_deletion) not in message
    assert "6401.9(f)(3)" in message


def test_every_export_route_the_readme_names_actually_answers(client):
    """`README.md` line 62 listed `/export/log`, `/export/pack` and
    `/export/pack.json` as top-level addresses. All three 404: the real ones
    are per record, plus two for the whole book."""
    import re
    from pathlib import Path

    readme = (Path(__file__).resolve().parent.parent / "README.md").read_text()
    body = client.post(
        "/incidents/tap", data={"device_id": "dev_counter_cam_01"}
    )
    incident_id = body.headers["Location"].split("/")[2]

    named = set(re.findall(r"`(/(?:incidents/<id>/)?export/[\w.]+)`", readme))
    assert named, "the README no longer names any export route"

    for route in named:
        url = route.replace("<id>", incident_id)
        assert client.get(url).status_code == 200, url
