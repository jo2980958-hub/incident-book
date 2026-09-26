"""The amendment trail: what changed, when, and who changed it.

This app splits the tap from the form on purpose, which means every record is
written twice: once by the button, in the moment, and once by a person sitting
down with it afterwards. A record that changes is normal here. A record that
changes without saying so is worthless to an inspector, and CPR PD 32 22.1
puts it bluntly for witness statements: an alteration that is not initialled
makes the statement inadmissible without the court's permission.

So every save computes a field-by-field difference against what was already
stored, writes it to the append-only ``revisions`` table with the name and job
title of whoever pressed save, and never overwrites the original capture. The
completion form shows the history under each field it applies to, the document
prints a revision number and the words "supersedes rev. N minus 1", and the
first row of every trail is the capture itself.

It also answers the question a judge will ask about the Bedrock integration:
what stops someone filing a model-drafted narrative without reading it. The
answer is that the trail records, per field, whether the filed text matched
the drafted text character for character, and both the form and the document
say which it was. Accepting a draft unchanged is allowed. Doing it invisibly
is not.
"""

from __future__ import annotations

from typing import Optional

from .incident_fields import Incident
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
    labels_for,
)

# Only the fields a human can change. The capture fields (dates, device,
# hashes) are not editable anywhere in the app, so they are not in the diff.
TRACKED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("violence_types", "B", "Workplace violence type"),
    ("description", "C", "Description of the incident"),
    ("perpetrator_class", "D", "Who committed the violence"),
    ("circumstances", "E", "Circumstances at the time"),
    ("location_class", "F", "Where it occurred"),
    ("location_detail", "F", "Where it occurred, in detail"),
    ("incident_types", "G", "Type of incident"),
    ("consequences_response", "H", "Security or law enforcement, and their response"),
    ("consequences_actions", "H", "Actions taken to protect employees"),
    ("completed_by", "I", "Name of the person completing the log"),
    ("completed_by_title", "I", "Job title of the person completing the log"),
    ("premises_id", "A", "Premises"),
)

_VOCABULARIES = {
    "violence_types": VIOLENCE_TYPES,
    "perpetrator_class": PERPETRATOR_CLASSES,
    "circumstances": CIRCUMSTANCE_OPTIONS,
    "location_class": LOCATION_CLASSES,
    "incident_types": INCIDENT_TYPES,
}

FIELD_LETTER = {name: letter for name, letter, _ in TRACKED_FIELDS}
FIELD_LABEL = {name: label for name, _, label in TRACKED_FIELDS}


def diff(before: Optional[Incident], after: Incident) -> dict:
    """``{field: {"from": <readable>, "to": <readable>}}`` for everything a
    person changed. Empty when they pressed save without changing anything,
    and an empty diff writes no revision: a trail full of "nothing happened"
    rows is a trail nobody reads."""
    changes: dict[str, dict] = {}
    for name, _letter, _label in TRACKED_FIELDS:
        old = getattr(before, name, None) if before is not None else None
        new = getattr(after, name)
        if _normalise(old) == _normalise(new):
            continue
        changes[name] = {"from": readable(name, old), "to": readable(name, new)}
    return changes


def _normalise(value):
    if isinstance(value, list):
        return sorted(value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return value


def readable(field_name: str, value) -> str:
    """A field value as a person reads it, not as the database stores it.
    "Type 2: a customer, client or visitor", never "type_2"."""
    vocabulary = _VOCABULARIES.get(field_name)
    if value in (None, "", []):
        return "(empty)"
    if isinstance(value, list):
        labels = labels_for(vocabulary, value) if vocabulary else list(value)
        return ", ".join(labels)
    if vocabulary:
        return labels_for(vocabulary, [value])[0]
    return str(value)


def history_by_field(revisions: list[dict]) -> dict[str, list[dict]]:
    """The trail reorganised so the completion form can print
    "changed 14 October by A. Patel, was: Tuesday" under the field it happened
    to, which is where someone looks for it."""
    by_field: dict[str, list[dict]] = {}
    for revision in revisions:
        for name, change in (revision.get("changes") or {}).items():
            by_field.setdefault(name, []).append(
                {
                    "at": revision["at"],
                    "actor_name": revision.get("actor_name", ""),
                    "actor_title": revision.get("actor_title", ""),
                    "was": change.get("from", ""),
                    "became": change.get("to", ""),
                    "kind": revision.get("kind", ""),
                }
            )
    return by_field


def revision_number(revisions: list[dict]) -> int:
    """Revision 0 is the capture. Each later save that changed something is
    the next number. This is what prints in the document's masthead."""
    return max(0, len([r for r in revisions if r.get("kind") != "captured"]))
