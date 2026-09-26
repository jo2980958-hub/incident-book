"""The whole log, not one record.

The evidence pack answers one incident for one reader. The obligation is over
the book. Labor Code 6401.9(f)(5): all records required by that subdivision
"shall be made available to the division upon request for examination and
copying." And (f)(6): the same records go to employees and their
representatives "upon request and without cost, for examination and copying
within 15 calendar days of a request."

Neither of those is a request for one incident, and neither of them waits.
So the log exports whole, in the nine-field shape, de-identified the same way
every other copy of the log is, with a header block stating what the file is,
which premises and date range it covers, and that it was de-identified with the
citation. A CSV that opens in a spreadsheet with no idea what it is gets
forwarded once and then becomes a mystery file on somebody's desktop.

Also here because it is the same obligation from the other side: an owner
changing systems, or handing over on a sale, should be able to take the book
with them. A product that traps a five-year statutory record is not a product
anyone should install.
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from . import pii, timefmt
from .config import APP_VERSION, FORM_ID_LOG
from .incident_fields import Incident
from .premises import Premises
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
    labels_for,
)

COLUMNS = (
    "record_no",
    "A_occurred_at",
    "A_location",
    "B_violence_type",
    "C_description",
    "D_who_committed",
    "E_circumstances",
    "F_where_class",
    "F_where_detail",
    "G_incident_type",
    "H_security_or_law_enforcement",
    "H_actions_to_protect_employees",
    "I_completed_by",
    "I_job_title",
    "I_date_completed",
    "premises",
    "device_id",
    "clip_status",
    "clip_sha256",
    "created_at",
    "retain_until",
    "status",
    "amendments",
)


def build_log_csv(
    incidents: list[Incident],
    premises_by_id: dict,
    amendments_by_id: Optional[dict] = None,
    generated_at: Optional[int] = None,
    tz_name: str = "",
) -> str:
    amendments_by_id = amendments_by_id or {}
    generated_at = generated_at or _now_ms()
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for line in _header(incidents, generated_at, tz_name):
        writer.writerow([line])
    writer.writerow([])
    writer.writerow(COLUMNS)
    for incident in sorted(incidents, key=lambda i: i.occurred_at):
        writer.writerow(_row(incident, premises_by_id, amendments_by_id, tz_name))
    return buffer.getvalue()


def _header(incidents: list[Incident], generated_at: int, tz_name: str) -> list[str]:
    days = sorted(timefmt.day(i.occurred_at, tz_name) for i in incidents)
    span = f"{days[0]} to {days[-1]}" if days else "no records"
    return [
        "Violent incident log, California Labor Code 6401.9(d)(2)",
        f"Form {FORM_ID_LOG}. Produced by Incident Book {APP_VERSION}.",
        f"Prepared {timefmt.canonical(generated_at, tz_name)}",
        f"Records: {len(incidents)}. Incident dates covered: {span}.",
        timefmt.zone_note(tz_name),
        "Personal identifying information has been removed from the free-text "
        "columns as Labor Code 6401.9(d)(1)(B) requires. Column I is kept in "
        "full because 6401.9(d)(2)(I) requires it.",
        "Each record is retained a minimum of five years from creation, "
        "Labor Code 6401.9(f)(3).",
    ]


def _row(incident: Incident, premises_by_id: dict, amendments: dict, tz: str) -> list:
    site = premises_by_id.get(incident.premises_id)
    return [
        incident.incident_id,
        timefmt.rfc3339(incident.occurred_at, tz),
        _inert(incident.location),
        "; ".join(labels_for(VIOLENCE_TYPES, incident.violence_types)),
        _clean(incident.description),
        _one(PERPETRATOR_CLASSES, incident.perpetrator_class),
        "; ".join(labels_for(CIRCUMSTANCE_OPTIONS, incident.circumstances)),
        _one(LOCATION_CLASSES, incident.location_class),
        _clean(incident.location_detail),
        "; ".join(labels_for(INCIDENT_TYPES, incident.incident_types)),
        _clean(incident.consequences_response),
        _clean(incident.consequences_actions),
        # (I) is never redacted -- 6401.9(d)(2)(I) requires the name and job
        # title -- but it is still typed by a person, so it is still made
        # inert before a spreadsheet reads it.
        _inert(incident.completed_by),
        _inert(incident.completed_by_title),
        timefmt.rfc3339(incident.completed_at, tz),
        site.one_line() if isinstance(site, Premises) else "Not recorded",
        incident.device_id,
        incident.clip_status,
        incident.clip_sha256 or "",
        timefmt.rfc3339(incident.created_at, tz),
        timefmt.rfc3339(incident.earliest_deletion, tz),
        _status(incident),
        amendments.get(incident.incident_id, 0),
    ]


def _status(incident: Incident) -> str:
    if incident.is_purged:
        return "purged after five years"
    return "complete" if incident.completed else "needs finishing"


def _clean(text: str) -> str:
    """De-identified, and inert when the spreadsheet opens it.

    A description that begins ``=``, ``+``, ``-`` or ``@`` is a live formula
    in Excel, Numbers and LibreOffice, and this file is the one that goes to
    Cal/OSHA and to an employee's representative. The completer types the
    description under stress and a model may have drafted it, so neither end
    of that can be relied on to avoid a leading equals sign. Prefixing a
    single quote is the convention every one of those programs understands:
    the cell shows the text and the text is text.
    """
    return _inert(pii.redact(text or "")[0])


def _inert(text: str) -> str:
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _one(vocabulary, value) -> str:
    return labels_for(vocabulary, [value])[0] if value else ""


def _now_ms() -> int:
    import time

    return int(time.time() * 1000)
