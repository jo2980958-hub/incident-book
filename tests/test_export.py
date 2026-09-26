"""The two machine-readable exports: the statute-shaped log entry and the
evidence pack's manifest.
"""

import hashlib
import re

from factories import (
    CLIP_BYTES,
    SNAPSHOT_BYTES,
    blank_incident,
    complete_incident,
)

from app.export import build_evidence_pack, build_violent_incident_log_entry


def test_log_entry_covers_all_nine_statute_fields():
    entry = build_violent_incident_log_entry(complete_incident())
    expected_keys = {
        "A_date_time_location", "B_workplace_violence_type", "C_description",
        "D_perpetrator_classification", "E_circumstances", "F_where_it_occurred",
        "G_incident_type", "H_consequences", "I_completed_by",
    }
    assert expected_keys.issubset(entry.keys())
    assert entry["A_date_time_location"]["location"] == "Front counter"
    # (B) and (G) are lists: the statute says "type or types" and "any of the
    # following", so a single value would be the wrong shape for both.
    assert entry["B_workplace_violence_type"] == ["Type 2: a customer, client or visitor"]
    assert entry["G_incident_type"] == ["Threat of physical force or of a weapon"]
    # (F) and (H) each carry two limbs the statute names separately.
    assert entry["F_where_it_occurred"]["classification"] == "In the workplace"
    assert entry["F_where_it_occurred"]["detail"].startswith("At the till")
    assert entry["H_consequences"]["security_or_law_enforcement"].startswith("Police")
    assert entry["H_consequences"]["actions_to_protect_employees"]
    assert entry["I_completed_by"]["name"] == "A. Owner"
    assert entry["I_completed_by"]["title"] == "Manager"
    assert entry["statute_complete"] is True


def test_log_entry_marks_draft_incomplete():
    entry = build_violent_incident_log_entry(blank_incident("inc_2"))
    assert entry["statute_complete"] is False
    assert {m["letter"] for m in entry["missing_fields"]} == set("BCDEFGHI")


def test_log_entry_retention_is_five_years():
    entry = build_violent_incident_log_entry(complete_incident())
    assert entry["retention"]["minimum_years"] == 5
    assert entry["retention"]["citation"] == "6401.9(f)(3)"


def test_log_entry_states_that_it_is_de_identified():
    """The JSON twin of the printed log carries the same duty as the paper."""
    entry = build_violent_incident_log_entry(
        complete_incident(description="Call John Smith on 555-123-4567 about this.")
    )
    pii_block = entry["personal_identifying_information"]
    assert pii_block["status"] == "omitted"
    assert pii_block["citation"] == "6401.9(d)(1)(B)"
    assert "John Smith" not in entry["C_description"]
    assert "555-123-4567" not in entry["C_description"]
    assert {f["field_letter"] for f in pii_block["removed"]} == {"C"}


def test_evidence_pack_manifest_hashes_match_content_sha256():
    incident = complete_incident()
    _html, manifest = build_evidence_pack(incident, CLIP_BYTES, SNAPSHOT_BYTES)

    exhibits = {e["ref"]: e for e in manifest["exhibits"]}
    assert exhibits["E1"]["sha256"] == hashlib.sha256(CLIP_BYTES).hexdigest()
    assert exhibits["E2"]["sha256"] == hashlib.sha256(SNAPSHOT_BYTES).hexdigest()
    assert exhibits["E1"]["bytes"] == len(CLIP_BYTES)
    assert "fixture" in exhibits["E1"]["description"]


def test_evidence_pack_manifest_sha256_file_is_coreutils_format():
    """The command printed on the document has to work against this file."""
    incident = complete_incident()
    _html, manifest = build_evidence_pack(incident, CLIP_BYTES, SNAPSHOT_BYTES)
    lines = manifest["manifest_sha256_file"].splitlines()
    assert len(lines) == 2
    for line in lines:
        digest, sep, name = line.partition("  ")
        assert sep == "  "
        assert len(digest) == 64
        assert name.startswith(incident.incident_id)
    assert manifest["verification_command"] == "sha256sum -c manifest.sha256"


def test_evidence_pack_manifest_handles_missing_clip():
    incident = blank_incident("inc_3")
    html, manifest = build_evidence_pack(incident, None, None)
    assert manifest["exhibits"] == []
    assert manifest["manifest_sha256_file"] == ""
    assert "No clip is attached to this record" in html


def test_a_failed_clip_fetch_is_a_manifest_row_not_an_absence():
    incident = blank_incident("inc_4")
    incident.clip_attempts = [
        {
            "at": 1758500142000,
            "outcome": "unavailable",
            "reason": "the camera was not recording at that timestamp",
        }
    ]
    _html, manifest = build_evidence_pack(incident, None, None)
    gaps = [e for e in manifest["exhibits"] if e["ref"] == "Gap"]
    assert len(gaps) == 1
    assert "not recording at that timestamp" in gaps[0]["description"]
    assert gaps[0]["sha256"] is None


def test_evidence_pack_html_never_contains_banned_phrases():
    """The ban is on prose this app wrote, which is what the guard covers.

    It is not on a verbatim quotation of the statute, and subdivision
    (d)(2)(D) says "including whether the perpetrator was" in so many words.
    Printing a paraphrase instead is how a statutory form gets rejected, so
    the quotation stays and this test reads around it, the same boundary
    ``incident_language`` draws.
    """
    html, _ = build_evidence_pack(complete_incident(), CLIP_BYTES, SNAPSHOT_BYTES)
    prose = re.sub(r'<p class="quote">.*?</p>', "", html, flags=re.S).lower()
    for banned in ("the thief", "the suspect", "the intruder", "the perpetrator"):
        assert banned not in prose


def test_the_statutory_wording_is_quoted_rather_than_paraphrased():
    html, _ = build_evidence_pack(complete_incident(), CLIP_BYTES, SNAPSHOT_BYTES)
    quotes = re.findall(r'<p class="quote">(.*?)</p>', html, flags=re.S)
    assert len(quotes) == 9
    assert quotes[0] == "The date, time, and location of the incident."
    assert quotes[2] == "A detailed description of the incident."
    assert "including whether the perpetrator was" in quotes[3]
    assert quotes[8].startswith("Information about the person completing the log")
