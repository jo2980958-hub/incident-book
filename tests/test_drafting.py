"""The Bedrock drafting path, and the human edit step that makes it filable.

The question a judge asks about a model that writes a statutory field is:
what stops someone filing generated text unread? The answer this app gives is
in three parts, and all three are asserted here. Nothing the model writes is
ever a saved field. The save is a separate human action with a name attached.
And the document prints which of the three things happened to each drafted
field, so accepting a draft unchanged is allowed but never invisible.
"""

from factories import blank_incident, completion_form

from app.bedrock import BedrockUnavailable, StubRunner
from app.drafting import draft_narrative, provenance_marker

WORDS = "a man came over the counter shouting about the till, I called 911"
PROPOSED = (
    "A person came over the counter and shouted about the till. "
    "They left when the telephone was picked up."
)


def _reply(**fields):
    base = {
        "description": PROPOSED,
        "consequences_response": "The worker called 911.",
        "consequences_actions": "",
    }
    base.update(fields)
    return {"tool_input": base, "usage": {"inputTokens": 120, "outputTokens": 60}}


def test_a_proposal_comes_back_as_a_draft_and_not_as_a_field():
    incident = blank_incident()
    runner = StubRunner([_reply()])
    draft = draft_narrative(runner, incident, WORDS)

    assert draft.status == "proposed"
    assert draft.came_from_a_model is True
    assert draft.description == PROPOSED
    # The statutory fields on the record are untouched. This is the whole
    # argument: a draft is a proposal beside the record, never in it.
    assert incident.description == ""
    assert incident.consequences_response == ""
    assert incident.is_statute_complete() is False


def test_the_model_is_never_asked_to_classify_anybody():
    runner = StubRunner([_reply()])
    draft_narrative(runner, blank_incident(), WORDS)
    tool = runner.calls[0]["tool"]
    offered = set(tool["inputSchema"]["json"]["properties"])
    # Two prose fields, both statutory, and nothing else. An unconstrained
    # string the guard list was not written for undoes the whole argument, so
    # there is no fourth field to forget.
    assert offered == {
        "description",
        "consequences_response",
        "consequences_actions",
    }
    assert tool["inputSchema"]["json"]["additionalProperties"] is False
    # (B), (D), (E), (F) and (G) are the fields that make the log an assertion
    # about a person, and none of them is on the tool.
    for classification in ("violence_type", "perpetrator", "circumstance", "incident_type"):
        assert classification not in str(offered)


def test_offline_keeps_the_workers_words_verbatim():
    incident = blank_incident()
    draft = draft_narrative(StubRunner([]), incident, WORDS)  # empty queue = unreachable
    assert draft.status == "unavailable"
    assert draft.description == WORDS
    assert draft.source_words == WORDS
    assert "Bedrock could not be reached" in draft.note
    assert draft.came_from_a_model is False


def test_a_throttle_is_the_same_fallback_as_a_missing_account():
    draft = draft_narrative(
        StubRunner([BedrockUnavailable("ThrottlingException: slow down")]),
        blank_incident(),
        WORDS,
    )
    assert draft.status == "unavailable"
    assert draft.description == WORDS
    assert "slow down" in draft.note


def test_nothing_typed_means_nothing_drafted():
    runner = StubRunner([_reply()])
    draft = draft_narrative(runner, blank_incident(), "   ")
    assert draft.status == "unavailable"
    assert runner.calls == []  # the model was not called at all


def test_an_accusing_draft_is_discarded_whole():
    draft = draft_narrative(
        StubRunner([_reply(description="The suspect came over the counter.")]),
        blank_incident(),
        WORDS,
    )
    assert draft.status == "rejected"
    assert draft.description == WORDS  # the worker's own words, kept
    assert "no accusation" in draft.note
    assert draft.came_from_a_model is False


def test_an_overclaiming_draft_is_discarded_whole():
    draft = draft_narrative(
        StubRunner([_reply(consequences_response="The clip confirmed the account.")]),
        blank_incident(),
        WORDS,
    )
    assert draft.status == "rejected"
    assert "no overclaiming" in draft.note


def test_an_identifier_the_worker_never_typed_is_discarded_whole():
    """The guard that matters most: a model inventing a phone number is not a
    wording problem, it is a fabricated identifier in a statutory record."""
    draft = draft_narrative(
        StubRunner([_reply(description="A person called 555-867-5309 afterwards.")]),
        blank_incident(),
        WORDS,
    )
    assert draft.status == "rejected"
    assert "telephone number" in draft.note
    assert draft.description == WORDS


def test_an_identifier_the_worker_did_type_survives():
    words = WORDS + ". My number is 555-867-5309."
    draft = draft_narrative(
        StubRunner([_reply(description="A person came over the counter. 555-867-5309.")]),
        blank_incident(),
        words,
    )
    assert draft.status == "proposed"


def test_provenance_marker_says_which_of_the_three_things_happened():
    runner = StubRunner([_reply()])
    draft = draft_narrative(runner, blank_incident(), WORDS)

    assert provenance_marker(draft, PROPOSED, "description") == (
        "Drafted by software, accepted unchanged"
    )
    assert provenance_marker(draft, PROPOSED + " I was shaken.", "description") == (
        "Drafted by software, edited by completer"
    )
    assert provenance_marker(None, PROPOSED, "description") == "Written by completer"
    # A field the model left empty was written by the person, whatever else
    # the same draft proposed.
    assert provenance_marker(draft, "We locked up.", "consequences_actions") == (
        "Written by completer"
    )


# -- through the routes, where the edit step actually lives -----------------


def _record_with_a_draft(client, bedrock, reply=None):
    bedrock.replies.append(reply or _reply())
    resp = client.post("/incidents/tap", data={"device_id": "dev_counter_cam_01"})
    incident_id = resp.headers["Location"].rsplit("/", 2)[-2]
    client.post(f"/incidents/{incident_id}/draft", data={"words": WORDS})
    return incident_id


def test_drafting_writes_no_statutory_field(client, bedrock, app):
    incident_id = _record_with_a_draft(client, bedrock)
    store = app.config["STORE"]
    incident = store.get_incident(incident_id)
    assert incident.description == ""
    assert incident.completed is False
    assert store.get_draft(incident_id).description == PROPOSED


def test_the_form_opens_with_the_draft_in_the_box_and_says_it_is_not_filed(
    client, bedrock
):
    incident_id = _record_with_a_draft(client, bedrock)
    page = client.get(f"/incidents/{incident_id}/edit").get_data(as_text=True)
    assert PROPOSED in page
    assert "It is not part" in page and "of the log until you press save" in page
    assert "Drafted by software, not filed." in page


def test_saving_unchanged_is_allowed_and_recorded_as_unchanged(client, bedrock, app):
    incident_id = _record_with_a_draft(client, bedrock)
    client.post(
        f"/incidents/{incident_id}/edit", data=completion_form(description=PROPOSED)
    )

    store = app.config["STORE"]
    assert store.get_incident(incident_id).description == PROPOSED
    note = store.revisions(incident_id)[-1]["note"]
    assert "accepted unchanged" in note
    assert "stub-model" in note

    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "Drafted by software, accepted unchanged" in pack


def test_saving_an_edited_draft_is_recorded_as_edited(client, bedrock, app):
    incident_id = _record_with_a_draft(client, bedrock)
    client.post(
        f"/incidents/{incident_id}/edit",
        data=completion_form(description=PROPOSED + " I was shaken afterwards."),
    )

    note = app.config["STORE"].revisions(incident_id)[-1]["note"]
    assert "edited by the completer" in note

    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "Drafted by software, edited by completer" in pack


def test_the_document_names_which_fields_were_drafted(client, bedrock):
    incident_id = _record_with_a_draft(client, bedrock)
    client.post(
        f"/incidents/{incident_id}/edit", data=completion_form(description=PROPOSED)
    )
    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "drafted by software from" in pack
    assert "(C)" in pack


def test_a_record_with_no_draft_says_so_on_the_document(client):
    resp = client.post("/incidents/tap", data={"device_id": "dev_counter_cam_01"})
    incident_id = resp.headers["Location"].rsplit("/", 2)[-2]
    client.post(f"/incidents/{incident_id}/edit", data=completion_form())
    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "No field on this record was drafted by software." in pack
    assert "Written by completer" in pack


# -- the three findings of docs/FREE-TEXT-AUDIT.md --------------------------


def test_a_name_the_model_invented_is_refused_even_though_it_is_only_a_guess():
    """Audit A4. ``pii.Finding.certain`` is True for a matched shape and False
    for the capitalised-run name heuristic, and an earlier build skipped the
    uncertain ones, which is exactly backwards: the certain shapes are phone
    numbers, the uncertain ones are plain names, and a plain name is the one
    thing a model must never add to a statutory record."""
    draft = draft_narrative(
        StubRunner([_reply(description="John Reyes came in at about nine.")]),
        blank_incident(),
        WORDS,
    )
    assert draft.status == "rejected"
    assert "name" in draft.note
    assert "John Reyes" not in draft.note  # and it is not quoted back either
    assert draft.description == WORDS


def test_an_invented_name_never_reaches_the_unredacted_police_pack(
    client, bedrock, app
):
    """The redaction that would have caught it runs on the statutory log
    only. The pack is unredacted by design and is the document a police
    officer reads, so the refusal has to happen before it is ever stored."""
    incident_id = _record_with_a_draft(
        client, bedrock, _reply(description="John Reyes came in at about nine.")
    )
    stored = app.config["STORE"].get_draft(incident_id)
    assert stored.status == "rejected"
    assert "John Reyes" not in stored.description

    client.post(f"/incidents/{incident_id}/edit", data=completion_form())
    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "John Reyes" not in pack


def test_the_refused_wording_is_never_quoted_back_to_a_person(client, bedrock, app):
    """Audit C7. A rejection is model output with a frame around it, not
    metadata. The rule that fired and the field it fired on go on the screen;
    the wording goes to the log."""
    banned = "The suspect came over the counter."
    incident_id = _record_with_a_draft(client, bedrock, _reply(description=banned))

    stored = app.config["STORE"].get_draft(incident_id)
    assert "the suspect" not in stored.note.lower()
    assert "the suspect" not in stored.description.lower()
    assert "no accusation" in stored.note
    assert "(C)" in stored.note

    page = client.get(f"/incidents/{incident_id}/edit").get_data(as_text=True)
    assert "the suspect" not in page.lower()
    assert "no accusation" in page


def test_the_refusal_reason_reaches_the_log_for_whoever_has_to_debug_it(caplog):
    with caplog.at_level("WARNING"):
        draft_narrative(
            StubRunner([_reply(description="The suspect came over the counter.")]),
            blank_incident(),
            WORDS,
        )
    assert "the suspect" in caplog.text.lower()
    assert "no accusation" in caplog.text


def test_what_the_log_still_wants_is_computed_and_not_asked_of_the_model(
    client, bedrock
):
    """Audit A5. The model is given no field in which to write a question,
    so there is nothing to validate; the same list is computed from the
    record and printed in the app's own words."""
    incident_id = _record_with_a_draft(client, bedrock)
    page = client.get(f"/incidents/{incident_id}/edit").get_data(as_text=True)
    assert "The log still wants these" in page
    for letter in "BDEFGHI":
        assert f"({letter})" in page
