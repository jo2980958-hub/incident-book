"""The whole book as a CSV: what it says on its face, and what it must not do
when a spreadsheet opens it.
"""

import csv
import io

from factories import blank_incident, complete_incident

from app.export_csv import build_log_csv


def _rows(incidents, **kwargs):
    body = build_log_csv(incidents, premises_by_id={}, amendments_by_id={}, **kwargs)
    return body, list(csv.reader(io.StringIO(body)))


def test_the_file_says_what_it_is_before_the_first_row():
    body, _ = _rows([complete_incident()])
    assert "6401.9" in body
    assert "6401.9(d)(1)(B)" in body


def test_the_free_text_columns_are_de_identified_like_every_other_copy():
    incident = complete_incident(description="Call John Smith on 555-123-4567.")
    body, _ = _rows([incident])
    assert "John Smith" not in body
    assert "555-123-4567" not in body
    assert "[name removed]" in body


def test_a_description_beginning_with_an_equals_sign_is_not_a_live_formula():
    """This file goes to Cal/OSHA and to an employee's representative. A
    description that opens with =, +, - or @ is a formula in Excel, Numbers
    and LibreOffice alike."""
    for opener in ("=", "+", "-", "@"):
        incident = complete_incident(
            description=opener + 'HYPERLINK("http://example.com","click")'
        )
        incident.completed_by = opener + "cmd|' /c calc'!A1"
        body, rows = _rows([incident])
        data = [r for r in rows if r and r[0].startswith("inc_")]
        assert data, body
        for cell in data[0]:
            assert not cell.startswith(opener), cell


def test_a_purged_record_still_appears_as_a_row_with_its_dates():
    incident = blank_incident()
    incident.purged_at = 1758500142000
    _body, rows = _rows([incident])
    data = [r for r in rows if r and r[0].startswith("inc_")]
    assert len(data) == 1
    assert "purged after five years" in data[0]
