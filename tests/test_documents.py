"""The two documents, against this app's own document-craft rules.

Two things are under test here. The split itself, which is a compliance
requirement rather than a preference: Labor Code 6401.9(d)(1)(B) puts the
de-identification duty on the violent incident log and not on the pack a
police officer reads, and one document trying to be both is the failure mode.
And the section 9 checklist, run as greps over the rendered HTML rather than
read off the template, because the template is not what anybody receives.
"""

import re

from factories import CLIP_BYTES, SNAPSHOT_BYTES, blank_incident, complete_incident

from app import document
from app.export import build_document

IDENTIFYING = (
    "John Smith called on 555-123-4567 from john@example.com, "
    "then waited at 1142 Telegraph Avenue."
)


def _render(kind, incident=None, **kwargs):
    incident = incident if incident is not None else complete_incident()
    html, manifest = build_document(kind, incident, CLIP_BYTES, SNAPSHOT_BYTES, **kwargs)
    return html, manifest


def _flat(html):
    """Template line breaks are not document line breaks."""
    return re.sub(r"\s+", " ", html)


def _basis_markers(html):
    return re.findall(r'class="basis">([^<]*)<', html)


def _gutter_rows(html):
    """Each marker with the source line that follows it, which is how the
    reader meets them: the word, then who said it or what rule produced it."""
    pattern = r'class="basis">([^<]*)</span>\s*(?:<span class="src">([^<]*)</span>)?'
    return re.findall(pattern, html)


# -- the split -------------------------------------------------------------


def test_the_log_omits_identifying_information_and_the_pack_keeps_it():
    incident = complete_incident(description=IDENTIFYING)
    log, _ = _render("log", incident)
    pack, _ = _render("pack", incident)

    for identifier in ("John Smith", "555-123-4567", "john@example.com", "1142 Telegraph"):
        assert identifier not in log, identifier
        assert identifier in pack, identifier
    assert "[name removed]" in log
    assert "[telephone number removed]" in log


def test_each_document_says_on_its_face_which_one_it_is():
    log, _ = _render("log")
    pack, _ = _render("pack")
    assert "Statutory log. Personal identifying information omitted per" in log
    assert "Labor Code 6401.9(d)(1)(B)." in log
    assert "Evidence pack. Contains personal identifying information" in pack
    assert "Handle accordingly." in pack
    # And each points at the other, by record number, so a reader holding one
    # knows the other exists.
    assert "the evidence pack for this same record number" in _flat(log)
    assert "the statutory log for this same record number" in _flat(pack)


def test_the_log_lists_what_it_removed_rather_than_substituting_silently():
    log, _ = _render("log", complete_incident(description=IDENTIFYING))
    assert "Removed:" in log
    assert "Each removal is shown in the text as a named placeholder" in _flat(log)


def test_all_four_free_text_fields_are_redacted_on_the_log():
    incident = complete_incident()
    incident.location_detail = "Beside Officer Diaz."
    incident.consequences_response = "Sgt. Alvarez took the report."
    incident.consequences_actions = "We called 555-123-4567 for a locksmith."
    log, _ = _render("log", incident)
    for identifier in ("Officer Diaz", "Sgt. Alvarez", "555-123-4567"):
        assert identifier not in log, identifier


def test_the_amendment_trail_is_redacted_on_the_log_too():
    """A name taken out of (C) and left sitting in the trail's "was" column
    is the same name, in the same document."""
    revisions = [
        {
            "seq": 1,
            "at": 1758500142000,
            "actor_name": "A. Owner",
            "actor_title": "Manager",
            "kind": "amended",
            "changes": {
                "description": {"from": "John Smith shouted.", "to": "A person shouted."}
            },
            "note": "",
        }
    ]
    log, _ = _render("log", revisions=revisions)
    pack, _ = _render("pack", revisions=revisions)
    assert "John Smith" not in log
    assert "[name removed]" in log
    assert "John Smith" in pack


def test_field_I_prints_in_full_on_both_because_the_statute_requires_it():
    log, _ = _render("log")
    pack, _ = _render("pack")
    for html in (log, pack):
        assert "A. Owner, Manager." in html
    assert "6401.9(d)(2)(I) expressly requires the name and" in log


def test_the_two_documents_agree_about_the_same_record():
    incident = complete_incident()
    log, log_manifest = _render("log", incident)
    pack, pack_manifest = _render("pack", incident)
    assert log_manifest["incident_id"] == pack_manifest["incident_id"]
    assert log_manifest["record_revision"] == pack_manifest["record_revision"]
    assert [e["sha256"] for e in log_manifest["exhibits"]] == [
        e["sha256"] for e in pack_manifest["exhibits"]
    ]
    # Different form identifiers, because they are different forms.
    assert log_manifest["form_id"] != pack_manifest["form_id"]


# -- the nine fields -------------------------------------------------------


def test_the_nine_fields_print_in_the_statutes_order_with_letters_and_citations():
    log, _ = _render("log")
    letters = re.findall(r'class="letter">\(([A-I])\)</span>', log)
    assert letters == list("ABCDEFGHI")
    cites = re.findall(r'class="cite">([^<]*)</span>', log)
    assert cites == [f"6401.9(d)(2)({letter})" for letter in "ABCDEFGHI"]


def test_every_statutory_field_prints_even_when_nobody_answered_it():
    log, _ = _render("log", blank_incident())
    letters = re.findall(r'class="letter">\(([A-I])\)</span>', log)
    assert letters == list("ABCDEFGHI")
    assert log.count("Not recorded.") >= 7
    assert "Nobody has put their name to this log." in log


def test_closed_vocabularies_print_every_option_with_the_selection_marked():
    log, _ = _render("log")
    options = re.findall(r"<li>(&#9746;|&#9744;) ", log)
    # (B) four, (D) nine, (E) nine, (F) three, (G) six.
    assert len(options) == 4 + 9 + 9 + 3 + 6
    assert options.count("&#9746;") == 1 + 1 + 2 + 1 + 1  # what was chosen
    assert "&#9744;" in log  # and what was not, which is information too


def test_the_statutory_quotation_sits_under_the_plain_english_question():
    log, _ = _render("log")
    asks = re.findall(r'class="ask">([^<]*)</p>\s*<p class="quote">', log)
    assert len(asks) == 9
    assert asks[0] == "When and where did it happen?"


# -- observed against inferred --------------------------------------------


def test_every_marker_is_one_of_the_three_printed_words():
    for kind in ("log", "pack"):
        for incident in (complete_incident(), blank_incident()):
            html, _ = _render(kind, incident)
            markers = set(_basis_markers(html))
            assert markers <= {document.RECORDED, document.REPORTED, document.INFERRED}
            assert markers  # and there is at least one on every document


def test_rings_own_classification_is_reported_and_never_recorded():
    """Section 7.5. Ring's classifier has been documented labelling a
    motorised wheelchair a package, so ``sub_type: human`` is the device's
    assertion, not a recording."""
    html, _ = _render("pack")
    rows = _gutter_rows(html)
    classification = [
        (basis, source) for basis, source in rows if source.startswith("The device")
    ]
    assert classification, rows
    for basis, _source in classification:
        assert basis == document.REPORTED
    assert "classified the event" in html
    assert "has not been checked by a person" in html


def test_an_absence_is_inferred_and_names_its_rule_and_the_cameras_coverage():
    html, _ = _render("pack", blank_incident())
    rows = _gutter_rows(html)
    inferred = [(b, s) for b, s in rows if b == document.INFERRED]
    assert len(inferred) == 1
    assert inferred[0][1].startswith("Rule:")
    assert "The camera covers" in html
    assert "missing entry is missing information rather" in html


def test_every_reported_row_names_who_said_it_and_when():
    html, _ = _render("pack")
    for basis, source in _gutter_rows(html):
        if basis == document.REPORTED:
            assert source.strip(), "an unattributed report reads as a fabrication"
    assert "A. Owner, Manager, entered " in html


def test_every_recorded_row_names_what_it_is_traceable_to():
    html, _ = _render("pack")
    for basis, source in _gutter_rows(html):
        if basis == document.RECORDED:
            assert source.strip()
    assert "Device event e1" in html


def test_the_markers_are_words_and_not_colours_or_icons():
    """Marked structurally, per section 7.1. A greyscale photocopy, a
    colour-blind reader and a 200% zoom all get the same information."""
    css = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "app" / "static" / "record.css"
    ).read_text()
    basis_rules = [line for line in css.splitlines() if ".basis" in line]
    assert basis_rules
    for line in basis_rules:
        assert "color" not in line and "background" not in line
    html, _ = _render("pack")
    assert f">{document.RECORDED}<" in html
    assert f">{document.REPORTED}<" in html


# -- what makes a document look fake (section 8) --------------------------


def test_only_one_date_format_appears_anywhere():
    """Section 9 item 1. The commonest tell, and the easiest to fix."""
    for kind in ("log", "pack"):
        html, _ = _render(kind)
        assert re.findall(r"\d{1,2}/\d{1,2}/\d", html) == []


def test_every_displayed_time_carries_a_zone_and_a_numeric_offset():
    """Section 4.2 rule 1. A window carries its zone once, on the closing
    endpoint, which is the form the reference itself prints; every other
    displayed time carries its own."""
    html, _ = _render("pack")
    stamps = list(re.finditer(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", html))
    assert stamps
    for stamp in stamps:
        tail = html[stamp.end() : stamp.end() + 40]
        opens_a_window = tail.startswith(" to ")
        assert opens_a_window or re.match(
            r" [A-Z]+ \(UTC[+−]\d{2}:\d{2}\)", tail
        ), tail


def test_the_document_never_prints_the_word_none():
    """A gap row has no file behind it and says so in words. "None" is a
    programming language's word, not a document's."""
    for kind in ("log", "pack"):
        incident = blank_incident()
        incident.clip_attempts = [
            {"at": 1758500142000, "outcome": "unavailable", "reason": "no footage held"}
        ]
        html, _ = build_document(kind, incident, None, None)
        assert re.findall(r"\bNone\b", html) == []
        assert "Not applicable" in html and "Nothing to hash" in html


def test_the_document_never_overclaims():
    """Section 7.4 and section 9 item 26: not "verified" beside a hash this
    software computed itself, five minutes ago, over a file it also wrote."""
    banned = r"\b(verified|confirmed|proven|proof of|tamper.proof|court.admissible|admissible|legally binding)\b"
    for kind in ("log", "pack"):
        html, _ = _render(kind)
        assert re.findall(banned, html, re.I) == []
    assert "computed by this software" in _render("pack")[0]


def test_the_print_stylesheet_has_no_fake_document_tells():
    """Section 9 item 17. Radius, shadow, gradient and centred text each make
    an official document read as a screenshot of a web app."""
    css = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "app" / "static" / "record.css"
    ).read_text()
    print_css = css.split("/* Screen preview only")[0]
    for tell in ("border-radius", "box-shadow", "linear-gradient", "text-align: center"):
        assert tell not in print_css, tell


def test_nothing_in_the_document_stylesheet_is_set_below_nine_point():
    css = (
        __import__("pathlib").Path(__file__).resolve().parent.parent
        / "app" / "static" / "record.css"
    ).read_text()
    sizes = [float(pt) for pt in re.findall(r"(\d+(?:\.\d+)?)pt(?![\w-])", css)]
    body_text = [pt for pt in sizes if pt >= 3]  # rule widths are under 3pt
    assert min(body_text) >= 8.5  # the furniture floor the scale table sets


def test_the_hash_prints_in_full_and_grouped_for_reading_aloud():
    """Section 5. A truncated hash is a UI affordance, not a record."""
    html, _ = _render("pack")
    grouped = re.findall(r'class="hash">([0-9a-f ]{8}[^<]*)</td>', html)
    assert grouped
    for block in grouped:
        assert len(re.sub(r"\s", "", block)) == 64
    assert "sha256sum -c manifest.sha256" in html


def test_the_manifest_says_what_its_hashes_do_not_cover():
    html, _ = _render("pack")
    assert "It is not evidence of what the" in html
    assert "it is not a signature by any third party" in html


def test_the_retention_obligation_and_deletion_date_print_on_the_document():
    for kind in ("log", "pack"):
        html, _ = _render(kind)
        assert "Minimum five years, Labor Code 6401.9(f)(3)" in html
        assert "Earliest deletion" in html


def test_the_signature_block_states_the_consequence_of_a_false_entry():
    """Section 9 item 37. A certification with nothing at stake certifies
    nothing."""
    for kind in ("log", "pack"):
        html, _ = _render(kind)
        assert "knowingly recording false" in html
        assert "Labor Code 6401.9(g)" in html


def test_the_masthead_carries_what_a_reader_photographs():
    html, manifest = _render("pack")
    for label in ("Record no.", "Form", "Exhibits", "Prepared", "Revision"):
        assert f"<dt>{label}</dt>" in html
    assert manifest["form_id"] in html
    assert "first issue" in html


def test_a_paragraph_carries_one_basis_and_not_two():
    """The device's event and the device's opinion of it rest on different
    things, so they are two paragraphs. One marker over both would let the
    classification borrow the recording's standing."""
    html, _ = _render("pack")
    rows = [(b, s) for b, s in _gutter_rows(html) if s]
    event_rows = [(b, s) for b, s in rows if "e1" in s]
    assert (document.RECORDED, "Device event e1") in event_rows
    assert any(b == document.REPORTED and s.startswith("The device, at") for b, s in rows)


def test_the_paragraphs_are_numbered_in_the_order_they_print():
    html, _ = _render("pack")
    numbers = [int(n.rstrip(".")) for n in re.findall(r'class="no">(\d+\.)</span>', html)]
    assert numbers == list(range(1, len(numbers) + 1))
