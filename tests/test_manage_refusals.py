"""Two buttons that used to record something on an empty click.

Both are on the owner's side of the app, both write permanently, and neither
had a required field:

- "Record this review" wrote a row reading "Not recorded / No note was written"
  and flipped the compliance line at the top of the page to "No review is owed
  on the annual trigger or the per-incident trigger". An empty click declared
  the 6401.9(c)(2)(L) duty discharged.
- "Save this premises" minted a premises with a fresh id and no name, which
  then sat in the Editing dropdown forever labelled "Not recorded". Nothing in
  this app deletes a premises.
"""


def _reviews(client):
    page = client.get("/review")
    return page.get_data(as_text=True)


def test_an_empty_review_submit_records_nothing(client):
    before = _reviews(client)

    response = client.post("/review/record", data={"by": "", "title": "", "note": ""})

    assert response.status_code == 400
    after = _reviews(client)
    assert "No review has been recorded yet." in after
    assert "No note was written." not in after
    assert before == after


def test_the_empty_review_submit_does_not_discharge_the_duty(client):
    client.post("/review/record", data={"by": "", "title": "", "note": ""})

    page = client.get("/review").get_data(as_text=True)
    assert "No review is owed" not in page


def test_the_refusal_says_which_fields_are_missing_and_keeps_what_was_typed(client):
    response = client.post(
        "/review/record", data={"by": "A. Owner", "title": "Owner", "note": ""}
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "what came of it" in body
    assert "who did the review" not in body.split("form-refusal")[1].split("</p>")[0]
    assert 'value="A. Owner"' in body


def test_a_review_with_both_fields_is_still_recorded(client):
    response = client.post(
        "/review/record",
        data={"by": "A. Owner", "title": "Owner", "note": "Two of three on one shift."},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "A. Owner" in body
    assert "Two of three on one shift." in body
    assert "No review has been recorded yet." not in body


def test_an_empty_premises_submit_mints_nothing(client, app):
    response = client.post("/settings/premises", data={"premises_id": "", "name": ""})

    assert response.status_code == 400
    assert app.config["STORE"].list_premises() == []
    # The phantom would show as an unnamed option in the Editing dropdown; the
    # zone select has a legitimate "Not recorded" of its own, so look at the
    # premises list instead.
    assert "No premises has been recorded." in client.get("/settings").get_data(as_text=True)


def test_a_whitespace_only_premises_name_is_refused_too(client, app):
    response = client.post("/settings/premises", data={"name": "   "})

    assert response.status_code == 400
    assert app.config["STORE"].list_premises() == []


def test_the_premises_refusal_keeps_the_address_the_owner_typed(client):
    body = client.post(
        "/settings/premises",
        data={"name": "", "address_line1": "1200 Mission Street", "city": "San Francisco"},
    ).get_data(as_text=True)

    assert "needs a name" in body
    assert 'value="1200 Mission Street"' in body
    assert 'value="San Francisco"' in body


def test_a_named_premises_is_still_saved(client, app):
    client.post(
        "/settings/premises",
        data={"name": "Mission Market", "city": "San Francisco", "state": "CA"},
        follow_redirects=True,
    )

    saved = app.config["STORE"].list_premises()
    assert [s.name for s in saved] == ["Mission Market"]


def test_neither_form_offers_a_submit_the_server_would_refuse(client):
    """The browser stops it before the round trip; the server refuses anyway."""
    review = client.get("/review").get_data(as_text=True)
    settings = client.get("/settings").get_data(as_text=True)

    assert 'id="by" name="by" required' in review
    assert 'name="note" rows="3" required' in review
    assert 'id="name" name="name" required' in settings
