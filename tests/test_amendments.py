"""The amendment trail. A record that changes without saying so is worth
nothing to an inspector, and CPR PD 32 22.1 makes the same point about a
witness statement: an uninitialled alteration is inadmissible without the
court's permission.
"""

from factories import blank_incident, complete_incident, completion_form

from app.amendments import diff, history_by_field, readable, revision_number


def test_a_save_that_changed_nothing_writes_no_row():
    incident = complete_incident()
    assert diff(incident, complete_incident()) == {}


def test_the_diff_reads_in_the_statutes_words_and_not_the_databases():
    before = blank_incident()
    after = complete_incident("inc_blank")
    changes = diff(before, after)
    assert changes["violence_types"]["from"] == "(empty)"
    assert changes["violence_types"]["to"] == "Type 2: a customer, client or visitor"
    assert changes["perpetrator_class"]["to"] == "Client or customer"


def test_only_the_fields_a_person_can_change_are_tracked():
    before = complete_incident()
    after = complete_incident()
    after.clip_sha256 = "something else"
    after.occurred_at = 1
    assert diff(before, after) == {}


def test_readable_turns_a_stored_value_into_the_label_a_person_sees():
    assert readable("incident_types", ["threat"]) == "Threat of physical force or of a weapon"
    assert readable("description", "") == "(empty)"
    assert readable("completed_by", "A. Owner") == "A. Owner"


def test_the_capture_is_revision_zero_and_each_later_save_is_the_next_number():
    assert revision_number([]) == 0
    assert revision_number([{"kind": "captured"}]) == 0
    assert revision_number([{"kind": "captured"}, {"kind": "completed"}]) == 1
    trail = [{"kind": "captured"}, {"kind": "completed"}, {"kind": "amended"}]
    assert revision_number(trail) == 2


def test_history_is_reorganised_under_the_field_it_happened_to():
    trail = [
        {
            "at": 1,
            "actor_name": "A. Owner",
            "actor_title": "Manager",
            "kind": "completed",
            "changes": {"description": {"from": "(empty)", "to": "It happened."}},
        }
    ]
    by_field = history_by_field(trail)
    assert list(by_field) == ["description"]
    assert by_field["description"][0]["was"] == "(empty)"
    assert by_field["description"][0]["actor_name"] == "A. Owner"


# -- through the routes ----------------------------------------------------


def _saved(client, **overrides):
    resp = client.post("/incidents/tap", data={"device_id": "dev_counter_cam_01"})
    incident_id = resp.headers["Location"].rsplit("/", 2)[-2]
    client.post(f"/incidents/{incident_id}/edit", data=completion_form(**overrides))
    return incident_id


def test_the_first_row_of_every_trail_is_the_capture_itself(client, app):
    incident_id = _saved(client)
    trail = app.config["STORE"].revisions(incident_id)
    assert trail[0]["kind"] == "captured"
    assert "No statutory field was answered" in trail[0]["note"]


def test_a_save_names_who_made_it_and_keeps_the_old_value(client, app):
    incident_id = _saved(client)
    client.post(
        f"/incidents/{incident_id}/edit",
        data=completion_form(description="A different account of it."),
    )
    trail = app.config["STORE"].revisions(incident_id)
    assert [r["kind"] for r in trail] == ["captured", "completed", "amended"]
    assert trail[-1]["actor_name"] == "A. Owner"
    assert trail[-1]["actor_title"] == "Manager"
    assert trail[-1]["changes"]["description"]["from"].startswith("A customer threatened")


def test_the_trail_is_append_only_and_prints_on_the_document(client, app):
    incident_id = _saved(client)
    client.post(
        f"/incidents/{incident_id}/edit",
        data=completion_form(description="A different account of it."),
    )
    pack = client.get(f"/incidents/{incident_id}/export/pack").get_data(as_text=True)
    assert "Amendments to this record" in pack
    assert "supersedes rev. 1" in pack
    assert "A different account of it." in pack
    assert "A customer threatened the cashier over a refused sale." in pack
