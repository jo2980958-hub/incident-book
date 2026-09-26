"""The statute-shaped export: Labor Code 6401.9(d)(2), keyed by the statute's
own letters so the mapping to the law is checkable at a glance.

This is the machine-readable twin of the printed log, and it carries the same
obligation: the free text is de-identified per 6401.9(d)(1)(B) before it goes
anywhere, and the entry says so rather than leaving a reader to assume it.
Anyone who needs the unredacted words is looking for the evidence pack, which
is a different document with a different reader.
"""

from __future__ import annotations

from typing import Optional

from . import pii, timefmt
from .incident_fields import Incident
from .premises import Premises, resolve
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
    labels_for,
)

DEIDENTIFIED_NOTE = (
    "Free-text fields have had personal identifying information removed, as "
    "Labor Code 6401.9(d)(1)(B) requires of the violent incident log. Field "
    "(I) is kept in full because 6401.9(d)(2)(I) requires the name and job "
    "title of the person completing the log."
)


def build_violent_incident_log_entry(
    incident: Incident, premises: Optional[Premises] = None
) -> dict:
    site = resolve(premises)
    tz = site.timezone_name
    description, removed_c = pii.redact(incident.description)
    where, removed_f = pii.redact(incident.location_detail)
    response, removed_h1 = pii.redact(incident.consequences_response)
    actions, removed_h2 = pii.redact(incident.consequences_actions)
    removed = removed_c + removed_f + removed_h1 + removed_h2
    return {
        "incident_id": incident.incident_id,
        "document": "violent incident log entry",
        "statute": "California Labor Code 6401.9(d)(2)",
        "personal_identifying_information": {
            "status": "omitted",
            "citation": "6401.9(d)(1)(B)",
            "note": DEIDENTIFIED_NOTE,
            "removed": [
                {"kind": f.kind, "certain": f.certain, "field_letter": letter}
                for letter, group in (
                    ("C", removed_c),
                    ("F", removed_f),
                    ("H", removed_h1 + removed_h2),
                )
                for f in group
            ],
            "summary": pii.summarise(removed),
        },
        "premises": {
            "premises_id": site.premises_id,
            "name": site.name or None,
            "address": site.address_lines() or None,
            "establishment_id": site.establishment_id or None,
        },
        "A_date_time_location": {
            "occurred_at": timefmt.rfc3339(incident.occurred_at, tz),
            "occurred_at_display": timefmt.canonical(incident.occurred_at, tz),
            "tapped_at": timefmt.rfc3339(incident.tapped_at, tz),
            "location": incident.location,
        },
        "B_workplace_violence_type": labels_for(VIOLENCE_TYPES, incident.violence_types),
        "C_description": description,
        "D_perpetrator_classification": (
            labels_for(PERPETRATOR_CLASSES, [incident.perpetrator_class])[0]
            if incident.perpetrator_class
            else None
        ),
        "E_circumstances": labels_for(CIRCUMSTANCE_OPTIONS, incident.circumstances),
        "F_where_it_occurred": {
            "classification": (
                labels_for(LOCATION_CLASSES, [incident.location_class])[0]
                if incident.location_class
                else None
            ),
            "detail": where,
        },
        "G_incident_type": labels_for(INCIDENT_TYPES, incident.incident_types),
        "H_consequences": {
            "security_or_law_enforcement": response,
            "actions_to_protect_employees": actions,
        },
        "I_completed_by": {
            "name": incident.completed_by,
            "title": incident.completed_by_title,
            "date_completed": timefmt.rfc3339(incident.completed_at, tz) or None,
        },
        "evidence": {
            "clip_status": incident.clip_status,
            "clip_sha256": incident.clip_sha256,
            "clip_source": incident.clip_source,
            "snapshot_sha256": incident.snapshot_sha256,
            "snapshot_source": incident.snapshot_source,
        },
        "retention": {
            "created_at": timefmt.rfc3339(incident.created_at, tz),
            "retain_until": timefmt.rfc3339(incident.earliest_deletion, tz),
            "minimum_years": 5,
            "citation": "6401.9(f)(3)",
            "purged_at": timefmt.rfc3339(incident.purged_at, tz) or None,
        },
        "statute_complete": incident.is_statute_complete(),
        "missing_fields": [
            {"letter": letter, "what": what}
            for letter, what in incident.missing_statute_fields()
        ],
    }
