import pytest
from factories import fixture_clip, fixture_snapshot, human_motion_event

from datetime import datetime, timezone

from app.incident import (
    five_years_after,
    AccusatoryLanguageError,
    Incident,
    OverclaimError,
    assert_no_accusatory_language,
    assert_no_overclaiming,
    compose_event_summary,
    draft_from_event,
)


def test_assert_no_accusatory_language_passes_neutral_text():
    assert_no_accusatory_language("Motion event recorded at the counter camera.")


@pytest.mark.parametrize(
    "text",
    [
        "The thief left through the back door.",
        "The suspect was seen on camera.",
        "He stole three trays of meat.",
        "The intruder tripped the sensor.",
        "The perpetrator fled north.",
    ],
)
def test_assert_no_accusatory_language_rejects_banned_phrases(text):
    with pytest.raises(AccusatoryLanguageError):
        assert_no_accusatory_language(text)


@pytest.mark.parametrize(
    "text",
    [
        "The clip was verified against the original.",
        "This pack is court-admissible.",
        "The hash confirmed the file.",
        "Storage is tamper-proof.",
    ],
)
def test_assert_no_overclaiming_rejects_the_words_that_lose_a_reader(text):
    with pytest.raises(OverclaimError):
        assert_no_overclaiming(text)


def test_compose_event_summary_neutral_for_human_motion():
    summary = compose_event_summary(human_motion_event())
    assert "human" in summary
    assert "thief" not in summary.lower()
    assert "suspect" not in summary.lower()
    # The sentence is the device's assertion, not the app's finding.
    assert "classified" in summary
    assert "has not been checked by a person" in summary


def test_compose_event_summary_carries_no_timestamp_of_its_own():
    """The sentence is stored on the record and read years later, so a time
    baked into it at capture would still be in UTC on a document whose every
    other time is local. The document prefixes the canonical time itself."""
    summary = compose_event_summary(human_motion_event())
    assert str(human_motion_event().created_at) not in summary
    assert "20" not in summary  # no year, no clock, nothing date-shaped


def test_compose_event_summary_neutral_for_no_event():
    """Wording changed with the timestamp removal. What the test holds on to
    is the meaning: an absence, stated as an absence, naming the camera it is
    an absence on, and never as a finding about anybody."""
    summary = compose_event_summary(None)
    assert "no event was recorded" in summary.lower()
    assert "camera" in summary.lower()
    assert_no_accusatory_language(summary)


def test_draft_from_event_fills_only_date_time_location_and_evidence():
    incident = draft_from_event(
        device_id="dev_counter_cam_01",
        location="Front counter, facing till and door",
        event=human_motion_event(),
        clip=fixture_clip(),
        clip_attempt={
            "at": 1758500142000,
            "outcome": "attached",
            "reason": "the clip was returned",
        },
        snapshot=fixture_snapshot(),
        tapped_at=1758500142000,
        premises_id="prem_1",
    )

    # (A) auto-filled, and the tap is kept distinct from the event.
    assert incident.occurred_at == 1758500100000
    assert incident.tapped_at == 1758500142000
    assert incident.location == "Front counter, facing till and door"
    assert incident.premises_id == "prem_1"
    assert incident.clip_status == "attached"
    assert incident.clip_sha256 is not None
    assert incident.snapshot_sha256 is not None

    # (B)-(I) deliberately left for a human.
    assert incident.violence_types == []
    assert incident.description == ""
    assert incident.perpetrator_class is None
    assert incident.circumstances == []
    assert incident.location_class is None
    assert incident.incident_types == []
    assert incident.completed_by == ""
    assert incident.is_statute_complete() is False


def test_draft_from_event_records_named_clip_gap_not_silence():
    attempt = {
        "at": 1758500442000,
        "outcome": "unavailable",
        "reason": "continuous recording not enabled",
    }
    incident = draft_from_event(
        device_id="dev_backdoor_cam_01",
        location="Service entrance",
        event=human_motion_event("dev_backdoor_cam_01"),
        clip=None,
        clip_attempt=attempt,
        snapshot=None,
    )
    assert incident.clip_status == "unavailable: continuous recording not enabled"
    assert incident.clip_sha256 is None
    # The failed attempt stays on the record so the manifest can print it.
    assert incident.clip_attempts == [attempt]


def test_retain_until_is_five_calendar_years_after_created_at():
    """Calendar years, not 5*365 days.

    2023-11-14 -> 2028-11-14. The span contains one leap day (2024-02-29), so
    the constant this replaced put the date on 2028-11-13, a day inside the
    minimum 6401.9(f)(3) sets.
    """
    incident = Incident(
        incident_id="inc_1", device_id="d", location="loc", occurred_at=1000,
        created_at=1_700_000_000_000,  # 2023-11-14 22:13:20 UTC
    )

    assert incident.retain_until == five_years_after(1_700_000_000_000)
    assert _utc_day(incident.retain_until) == "2028-11-14"
    assert incident.retain_until > 1_700_000_000_000 + 5 * 365 * 86_400_000


def test_is_statute_complete_requires_every_field():
    incident = Incident(incident_id="inc_1", device_id="d", location="loc", occurred_at=1000)
    assert incident.is_statute_complete() is False

    incident.violence_types = ["type_2"]
    incident.description = "A customer threatened the cashier."
    incident.perpetrator_class = "client_or_customer"
    incident.circumstances = ["isolated_or_alone"]
    incident.location_class = "in_the_workplace"
    incident.location_detail = "At the till"
    incident.incident_types = ["threat"]
    incident.consequences_response = "Police were called and took a report."
    incident.completed_by = "A. Owner"
    incident.completed_by_title = "Manager"
    assert incident.is_statute_complete() is True


def test_missing_statute_fields_names_the_letters_that_are_empty():
    incident = Incident(incident_id="inc_1", device_id="d", location="loc", occurred_at=1000)
    incident.violence_types = ["type_2"]
    incident.description = "A customer threatened the cashier."
    letters = [letter for letter, _what in incident.missing_statute_fields()]
    assert letters == ["D", "E", "F", "G", "H", "I"]


def _utc_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def test_a_leap_day_record_is_kept_until_march_the_first():
    """2028-02-29 has no fifth anniversary. March 1 is later; February 28 is not."""
    born = int(datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc).timestamp() * 1000)

    assert _utc_day(five_years_after(born)) == "2033-03-01"


def test_the_stored_date_is_never_printed_when_it_is_short_of_the_minimum():
    """A book written before the arithmetic was corrected still holds short
    values, and they are stored. The printed date recomputes."""
    incident = Incident(
        incident_id="inc_1", device_id="d", location="loc", occurred_at=1000,
        created_at=1_700_000_000_000,
        retain_until=1_700_000_000_000 + 5 * 365 * 86_400_000,  # the old formula
    )

    assert incident.earliest_deletion == five_years_after(1_700_000_000_000)
    assert _utc_day(incident.earliest_deletion) == "2028-11-14"


def test_a_premises_that_chose_to_keep_a_record_longer_keeps_it_longer():
    incident = Incident(
        incident_id="inc_1", device_id="d", location="loc", occurred_at=1000,
        created_at=1_700_000_000_000,
        retain_until=2_500_000_000_000,
    )

    assert incident.earliest_deletion == 2_500_000_000_000
