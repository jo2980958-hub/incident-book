"""Finding a record again, which is the difference between a log and a pile.

The case that matters most is the last one: a filter that matches nothing has
to return nothing. A filter that quietly returns everything is worse than no
filter, because the person believes the answer.
"""

from factories import complete_incident

from app.search import Query, build_sql


def _store_with(store):
    first = complete_incident("inc_first")
    first.occurred_at = 1_700_000_000_000
    first.premises_id = "prem_a"
    second = complete_incident("inc_second", description="Someone shouted at the door.")
    second.occurred_at = 1_800_000_000_000
    second.premises_id = "prem_b"
    second.incident_types = ["animal_attack"]
    second.circumstances = ["rushed"]
    second.violence_types = ["type_1"]
    second.completed = False
    third = complete_incident("inc_third")
    third.occurred_at = 1_750_000_000_000
    third.purged_at = 1_900_000_000_000
    for incident in (first, second, third):
        store.save_incident(incident)
    return store


def _ids(store, **kwargs):
    return {i.incident_id for i in store.list_incidents(Query(**kwargs))}


def test_no_query_returns_the_whole_book_newest_first(store):
    _store_with(store)
    ids = [i.incident_id for i in store.list_incidents()]
    assert ids == ["inc_second", "inc_third", "inc_first"]


def test_free_text_searches_what_people_wrote(store):
    _store_with(store)
    assert _ids(store, text="shouted at the door") == {"inc_second"}
    assert _ids(store, text="threatened the cashier") == {"inc_first", "inc_third"}


def test_free_text_finds_a_record_by_its_number(store):
    _store_with(store)
    assert _ids(store, text="inc_third") == {"inc_third"}


def test_each_status_filter_selects_only_its_own(store):
    _store_with(store)
    assert _ids(store, status="complete") == {"inc_first"}
    assert _ids(store, status="needs_finishing") == {"inc_second"}
    assert _ids(store, status="purged") == {"inc_third"}


def test_the_list_filters_match_a_value_inside_the_list(store):
    _store_with(store)
    assert _ids(store, incident_type="animal_attack") == {"inc_second"}
    assert _ids(store, violence_type="type_2") == {"inc_first", "inc_third"}
    assert _ids(store, circumstance="rushed") == {"inc_second"}


def test_the_premises_filter_selects_one_site(store):
    _store_with(store)
    assert _ids(store, premises_id="prem_b") == {"inc_second"}


def test_a_date_range_is_inclusive_at_both_ends(store):
    _store_with(store)
    assert _ids(store, date_from="2023-11-14", date_to="2023-11-15") == {"inc_first"}
    assert _ids(store, date_from="2026-01-01") == {"inc_second"}


def test_filters_combine_rather_than_replace_each_other(store):
    _store_with(store)
    assert _ids(store, status="complete", incident_type="animal_attack") == set()


def test_a_filter_that_matches_nothing_finds_nothing_rather_than_everything(store):
    _store_with(store)
    assert _ids(store, text="a phrase nobody wrote") == set()
    assert _ids(store, incident_type="sexual_assault_or_threat") == set()
    assert _ids(store, date_from="2030-01-01") == set()


def test_every_value_is_bound_and_never_interpolated():
    where, params = build_sql(Query(text="o'brien; drop table incidents--"))
    assert "drop table" not in where.lower()
    assert params.count("%o'brien; drop table incidents--%") == len(params)


def test_a_query_knows_whether_it_is_filtered_and_can_drop_one_filter():
    query = Query(text="till", status="complete", incident_type="threat")
    assert query.is_filtered is True
    assert Query().is_filtered is False
    assert query.without("status").status == "any"
    assert query.without("status").text == "till"
