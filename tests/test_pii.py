"""De-identification, which Labor Code 6401.9(d)(1)(B) makes a duty on the
violent incident log and on nothing else.

These tests hold two things apart on purpose: what the module finds, and what
it honestly cannot. The name detector is a reading aid, the screen says so,
and a test that pretended otherwise would be the most dangerous test in the
suite.
"""

import pytest

from app import pii


@pytest.mark.parametrize(
    "text, kind",
    [
        ("Call me on 555-123-4567 tomorrow.", "telephone number"),
        ("Reach her at rowan.shop@example.com.", "electronic mail address"),
        ("He gave 123-45-6789 as his number.", "social security number"),
        ("They live at 1142 Telegraph Avenue.", "address"),
        ("Their plate AB-1234 was in the lot.", "vehicle registration"),
        ("Posted at https://example.com/clip.", "web address"),
        ("Officer Diaz took the report.", "name"),
    ],
)
def test_the_shapes_the_statute_names_are_found_with_certainty(text, kind):
    findings = pii.find(text)
    assert [f.kind for f in findings] == [kind]
    assert findings[0].certain is True


def test_a_name_at_the_start_of_a_sentence_keeps_its_surname():
    """The naive two-capitalised-words version reads "Call John Smith" as the
    name "Call John" and leaves the surname sitting in the statutory log."""
    clean, findings = pii.redact("Call John Smith on 555-123-4567.")
    assert clean == "Call [name removed] on [telephone number removed]."
    assert {f.text for f in findings} == {"John Smith", "555-123-4567"}


def test_the_name_heuristic_is_marked_uncertain():
    findings = pii.find("John Smith was at the counter.")
    assert [f.kind for f in findings] == ["name"]
    assert findings[0].certain is False


def test_ordinary_capitalised_english_is_not_read_as_a_person():
    for text in (
        "The counter was busy.",
        "He said no.",
        "They went out the front door.",
        "On Monday the shop was quiet.",
    ):
        assert pii.find(text) == [], text


def test_a_certain_match_wins_over_the_name_heuristic_for_the_same_words():
    findings = pii.find("Officer Diaz attended.")
    assert len(findings) == 1
    assert findings[0].text == "Officer Diaz"


def test_redaction_names_what_it_removed_rather_than_leaving_a_gap():
    clean, findings = pii.redact("Email rowan.shop@example.com or call 555-123-4567.")
    assert "[electronic mail address removed]" in clean
    assert "[telephone number removed]" in clean
    assert pii.summarise(findings) == (
        "Removed: 1 electronic mail address, 1 telephone number."
    )


def test_an_empty_removal_list_says_so_rather_than_printing_nothing():
    assert pii.summarise([]) == "No personal identifying information was found to remove."


def test_redaction_leaves_text_with_nothing_to_remove_exactly_as_written():
    original = "A customer leaned over the counter and shouted."
    clean, findings = pii.redact(original)
    assert clean == original
    assert findings == []
