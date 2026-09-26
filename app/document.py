"""Everything both documents need, computed once, so the log and the pack
cannot disagree with each other about the same record.

There are two documents, and that is a compliance requirement rather than a
design preference. Labor Code 6401.9(d)(1)(B) makes de-identification a duty on
the violent incident log specifically; the pack that goes to a police officer or
an insurer is a different document with a different reader and is not subject to
it. The failure mode to avoid is blunt: shipping one document that tries to
be both. So:

- **Statutory log.** Free text redacted through ``pii.py``, a masthead line
  saying so with the citation, and a list of what was removed rather than a
  silent substitution.
- **Evidence pack.** Not redacted, and a masthead line saying it carries
  identifying detail and should be handled accordingly.

Both print all nine fields in the statute's order, with the letters, the
citations, the plain-English question the app actually asked and the statutory
wording underneath it, every closed vocabulary in full with the selection
marked, and ``Not recorded`` in any field nobody answered. Both carry the same
record number, the same revision number and the same exhibit references.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

from . import pii, timefmt
from .amendments import revision_number
from .config import APP_VERSION, FORM_ID_LOG, FORM_ID_PACK
from .drafting import Draft, provenance_marker
from .incident_fields import Incident
from .premises import DeviceRegistration, Premises, resolve
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    STATUTE_URL,
    VIOLENCE_TYPES,
)

NOT_RECORDED = "Not recorded"
NOT_ANSWERED = "Nobody has answered this field"
UNTICKED = "Not recorded. No option here has been ticked by anyone."

# The three bases every assertion in either document is marked with, in this
# app's fixed vocabulary for the gutter marker. The word
# prints in the gutter in the label face: a reader photocopying this in
# greyscale, or colour-blind, or at 200%, gets the same information, which is
# why nothing here is carried by a colour or an icon.
#
# RECORDED came from the device or from this software's own event record and
# is traceable to an event or exhibit reference. REPORTED was asserted by a
# person or by a third-party system, and names who and when. INFERRED was
# computed by this software, and names the rule, the window and the coverage.
#
# Section 7.5 settles the one that matters: Ring's classifier has been
# documented labelling a motorised wheelchair a package, so ``sub_type: human``
# is REPORTED, by the device, and never RECORDED.
RECORDED = "RECORDED"
REPORTED = "REPORTED"
INFERRED = "INFERRED"

LOG_HANDLING = (
    "Statutory log. Personal identifying information omitted per "
    "Labor Code 6401.9(d)(1)(B)."
)
PACK_HANDLING = (
    "Evidence pack. Contains personal identifying information as written by the "
    "person completing the log. Handle accordingly."
)


@dataclass
class FieldRow:
    letter: str
    cite: str
    ask: str
    quote: str
    value: str = ""
    options: list[tuple[str, bool]] = field(default_factory=list)
    basis: str = REPORTED
    # Who said it and when, for REPORTED; the reference, for RECORDED. An
    # unattributed report reads to the document's reader as a fabrication.
    source: str = ""
    provenance: str = ""
    empty: bool = False
    # What prints in the field's box when nobody answered it. Every statutory
    # field appears even when empty, and a form with a missing row looks
    # altered, so the row says which kind of nothing this is.
    empty_note: str = ""


@dataclass
class Exhibit:
    ref: str
    name: str
    media_type: str
    size_bytes: Optional[int]
    description: str
    sha256: Optional[str]


def grouped_hash(digest: Optional[str]) -> str:
    """Sixty-four characters, eights, with a wider gap every thirty-two and a
    line break in the middle. Two people comparing a hash over the phone is
    the real use, and a truncated hash proves nothing."""
    if not digest:
        return ""
    eights = [digest[i : i + 8] for i in range(0, len(digest), 8)]
    first = " ".join(eights[0:2]) + "  " + " ".join(eights[2:4])
    second = " ".join(eights[4:6]) + "  " + " ".join(eights[6:8])
    return f"{first}\n{second}"


def build(
    kind: str,
    incident: Incident,
    premises: Optional[Premises],
    device: Optional[DeviceRegistration],
    draft: Optional[Draft],
    revisions: list[dict],
    clip_bytes: Optional[bytes],
    snapshot_bytes: Optional[bytes],
    generated_at: int,
) -> dict:
    """``kind`` is "log" or "pack"."""
    site = resolve(premises)
    tz = site.timezone_name
    redacting = kind == "log"
    text, removed = _narrative(incident, redacting)
    fields = _fields(incident, text, draft, tz, site)
    exhibits = _exhibits(incident, clip_bytes, snapshot_bytes, tz)
    revision = revision_number(revisions)
    return {
        "kind": kind,
        "title": "Violent incident log" if redacting else "Incident evidence pack",
        "handling": LOG_HANDLING if redacting else PACK_HANDLING,
        "statute_url": STATUTE_URL,
        "form_id": FORM_ID_LOG if redacting else FORM_ID_PACK,
        "app_version": APP_VERSION,
        "premises": site,
        "device": device or DeviceRegistration(device_id=incident.device_id),
        "incident": incident,
        "tz": tz,
        "zone_note": timefmt.zone_note(tz),
        "generated_at": generated_at,
        "generated_display": timefmt.canonical(generated_at, tz),
        "revision": revision,
        "supersedes": f"supersedes rev. {revision - 1}" if revision else "first issue",
        "fields": fields,
        "drafted_letters": [
            f.letter for f in fields if f.provenance.startswith("Drafted")
        ],
        "exhibits": exhibits,
        "exhibit_range": _exhibit_range(exhibits),
        "redactions": removed,
        "redaction_summary": pii.summarise(removed) if redacting else "",
        "blocks": _blocks(incident, tz, device),
        "revisions": _revisions(revisions, redacting),
        "missing": incident.missing_statute_fields(),
    }


def _revisions(revisions: list[dict], redacting: bool) -> list[dict]:
    """The amendment trail keeps the old value of every field, so on the
    statutory log it has to be redacted exactly like the fields themselves.
    A name removed from field (C) and left sitting in the "was:" column is
    the same name, in the same document."""
    if not redacting:
        return revisions
    cleaned = []
    for revision in revisions:
        changes = {
            name: {
                "from": pii.redact(str(change.get("from", "")))[0],
                "to": pii.redact(str(change.get("to", "")))[0],
            }
            for name, change in (revision.get("changes") or {}).items()
        }
        cleaned.append({**revision, "changes": changes,
                        "note": pii.redact(revision.get("note", ""))[0]})
    return cleaned


def _narrative(incident: Incident, redacting: bool) -> tuple[dict, list]:
    """The four free-text fields, redacted or not, plus everything that was
    taken out so the document can list it rather than hide it."""
    names = (
        "description",
        "location_detail",
        "consequences_response",
        "consequences_actions",
    )
    out, removed = {}, []
    for name in names:
        raw = getattr(incident, name) or ""
        if redacting and raw:
            clean, found = pii.redact(raw)
            out[name] = clean
            removed.extend(found)
        else:
            out[name] = raw
    return out, removed


def _fields(
    incident: Incident, text: dict, draft: Optional[Draft], tz: str, site: Premises
) -> list[FieldRow]:
    """The nine subdivisions of 6401.9(d)(2), in the statute's order.

    The order is the statute's and cannot be improved on, grouped or
    rearranged for visual balance: an inspector reads down the letters. The
    quoted wording under each plain-English question is the section text, with
    the enumerations printed as the option list below rather than repeated in
    the quote, which is what ``DOCUMENT-CRAFT.md`` section 6 rule 6 asks for.

    (A) is RECORDED, from the device. Every other field is a person's answer,
    so it is REPORTED and names them.
    """
    where = [site.name] + site.address_lines()
    said_by = _reported_by(incident, tz)
    return [
        FieldRow(
            "A",
            "6401.9(d)(2)(A)",
            "When and where did it happen?",
            "The date, time, and location of the incident.",
            value=(
                f"{timefmt.canonical(incident.occurred_at, tz)}, at "
                f"{incident.location or NOT_RECORDED}"
                + (f", {', '.join(p for p in where if p)}" if any(where) else "")
            ),
            basis=RECORDED,
            source=_event_reference(incident),
            provenance=(
                "Taken from the device event when the button was pressed"
                if incident.event_ids
                else "Taken from the button press; no device event was held"
            ),
        ),
        FieldRow(
            "B",
            "6401.9(d)(2)(B)",
            "What type of workplace violence was this?",
            "The workplace violence type or types, as described in subparagraph "
            "(B) of paragraph (6) of subdivision (a), involved in the incident.",
            options=_options(VIOLENCE_TYPES, incident.violence_types),
            source=said_by if incident.violence_types else NOT_ANSWERED,
            empty=not incident.violence_types,
            empty_note=UNTICKED,
        ),
        FieldRow(
            "C",
            "6401.9(d)(2)(C)",
            "What happened, in your own words?",
            "A detailed description of the incident.",
            value=text["description"],
            source=said_by if text["description"].strip() else NOT_ANSWERED,
            empty=not text["description"].strip(),
            empty_note="Not recorded. Nobody has written a description yet.",
            provenance=provenance_marker(draft, incident.description, "description"),
        ),
        FieldRow(
            "D",
            "6401.9(d)(2)(D)",
            "Who committed the violence, if known?",
            "A classification of who committed the violence, including whether "
            "the perpetrator was any of the following:",
            options=_options(
                PERPETRATOR_CLASSES,
                [incident.perpetrator_class] if incident.perpetrator_class else [],
            ),
            source=said_by if incident.perpetrator_class else NOT_ANSWERED,
            empty=not incident.perpetrator_class,
            empty_note=UNTICKED,
        ),
        FieldRow(
            "E",
            "6401.9(d)(2)(E)",
            "What were the circumstances at the time?",
            "A classification of circumstances at the time of the incident, "
            "including, but not limited to, whether the employee was any of the "
            "following:",
            options=_options(CIRCUMSTANCE_OPTIONS, incident.circumstances),
            source=said_by if incident.circumstances else NOT_ANSWERED,
            empty=not incident.circumstances,
            empty_note=UNTICKED,
        ),
        FieldRow(
            "F",
            "6401.9(d)(2)(F)",
            "Where exactly did it happen?",
            "A classification of where the incident occurred, such as any of "
            "the following:",
            options=_options(
                LOCATION_CLASSES,
                [incident.location_class] if incident.location_class else [],
            ),
            value=_where_detail(text["location_detail"]),
            source=said_by if incident.location_class else NOT_ANSWERED,
            empty=not incident.location_class,
            empty_note=UNTICKED,
        ),
        FieldRow(
            "G",
            "6401.9(d)(2)(G)",
            "What kind of incident was it?",
            "The type of incident, including, but not limited to, whether it "
            "involved any of the following:",
            options=_options(INCIDENT_TYPES, incident.incident_types),
            source=said_by if incident.incident_types else NOT_ANSWERED,
            empty=not incident.incident_types,
            empty_note=UNTICKED,
        ),
        FieldRow(
            "H",
            "6401.9(d)(2)(H)",
            "What happened next, and were the police called?",
            "Consequences of the incident, including, but not limited to, "
            "whether security or law enforcement was contacted and their "
            "response, and actions taken to protect employees from a continuing "
            "threat or from any other threats or consequences of the incident.",
            value=_two_limbs(text),
            source=said_by if _any_consequence(text) else NOT_ANSWERED,
            empty=not _any_consequence(text),
            provenance=provenance_marker(
                draft, incident.consequences_response, "consequences_response"
            ),
        ),
        FieldRow(
            "I",
            "6401.9(d)(2)(I)",
            "Who completed this log?",
            "Information about the person completing the log, including their "
            "name, job title, and the date completed.",
            value=_completer(incident, tz),
            source=said_by if incident.completed_by.strip() else NOT_ANSWERED,
            empty=not incident.completed_by.strip(),
            empty_note="Not recorded. Nobody has put their name to this log.",
        ),
    ]


def _reported_by(incident: Incident, tz: str) -> str:
    """Who asserted the answers on this record, and when they filed them.

    DOCUMENT-CRAFT section 7.2: an unattributed report is the same thing as a
    fabrication as far as the reader is concerned.
    """
    who = incident.completed_by.strip()
    if not who:
        return "Entered on this record; the completer is not yet named"
    title = incident.completed_by_title.strip()
    when = (
        timefmt.canonical(incident.completed_at, tz)
        if incident.completed_at
        else "date completed not recorded"
    )
    return f"{who}{', ' + title if title else ''}, entered {when}"


def _event_reference(incident: Incident) -> str:
    if incident.event_ids:
        return "Device event " + ", ".join(incident.event_ids)
    return "Button press on this record; no device event was held"


def _any_consequence(text: dict) -> bool:
    return bool(
        text["consequences_response"].strip() or text["consequences_actions"].strip()
    )


def _two_limbs(text: dict) -> str:
    """Both limbs of (H) print, always, each named. The statute lists them
    separately, so a limb nobody answered is a row that says so rather than a
    row that is not there."""
    response = text["consequences_response"].strip()
    actions = text["consequences_actions"].strip()
    return "\n".join(
        [
            "Security or law enforcement, and their response: "
            + (response or NOT_RECORDED + "."),
            "Actions taken to protect employees: " + (actions or NOT_RECORDED + "."),
        ]
    )


def _where_detail(detail: str) -> str:
    detail = detail.strip()
    if detail:
        return "In the completer's own words: " + detail
    return "No further detail about where this happened was recorded."


def _completer(incident: Incident, tz: str) -> str:
    if not incident.completed_by.strip():
        return ""
    title = incident.completed_by_title.strip() or "job title not recorded"
    when = (
        timefmt.canonical(incident.completed_at, tz)
        if incident.completed_at
        else NOT_RECORDED
    )
    return f"{incident.completed_by.strip()}, {title}. Completed {when}."


def _options(vocabulary, chosen: list[str]) -> list[tuple[str, bool]]:
    """Every option in the statute's list, with the selection marked, because
    what was not chosen is information too."""
    picked = set(chosen or [])
    return [(label, value in picked) for value, label, _quote in vocabulary]


def _blocks(incident: Incident, tz: str, device) -> list[dict]:
    """The narrative paragraphs, each with the basis it rests on printed in
    the gutter as a word, and the source or the rule printed beneath it.

    Ring's classification is REPORTED, by the device, and never RECORDED: its
    classifier has been documented calling a motorised wheelchair a package.
    An absence finding is INFERRED and carries its rule, its window and the
    camera's coverage in the same paragraph, in the same size, because a
    disclaimer set smaller than the claim it qualifies is one the author hoped
    would not be read.
    """
    coverage = (
        device.covers if device and device.covers else incident.location
    ) or NOT_RECORDED
    blocks = [
        {
            "no": 0,
            "basis": RECORDED,
            "source": "Capture event on this record",
            "exhibit": "",
            "text": (
                f"The button was pressed at {timefmt.canonical(incident.tapped_at, tz)}. "
                "That is the time a person acted, not the time anything was seen."
            ),
        }
    ]
    if incident.event_summary:
        # Two paragraphs, because they rest on two different things. That an
        # event exists at that instant is recorded and has an event id. What
        # the device decided the event was is the device's assertion, and
        # putting both under one marker would let the weaker one borrow the
        # stronger one's standing.
        blocks.append(
            {
                "no": 0,
                "basis": RECORDED,
                "source": "Device event " + ", ".join(incident.event_ids),
                "exhibit": ", ".join(incident.event_ids),
                "text": (
                    "An event was recorded on the device at "
                    f"{timefmt.canonical(incident.occurred_at, tz)}."
                ),
            }
        )
        blocks.append(
            {
                "no": 0,
                "basis": REPORTED,
                "source": (
                    "The device, at "
                    f"{timefmt.canonical(incident.occurred_at, tz)}"
                ),
                "exhibit": ", ".join(incident.event_ids),
                "text": incident.event_summary,
            }
        )
    else:
        blocks.append(
            {
                "no": 0,
                "basis": INFERRED,
                "source": (
                    "Rule: no device event for this camera was held at the "
                    "moment of the button press"
                ),
                "exhibit": "",
                "text": (
                    "No event from this device was held when the button was "
                    "pressed at "
                    f"{timefmt.canonical(incident.tapped_at, tz)}, so no device "
                    "event is attached to this record. The camera covers "
                    f"{coverage}. Activity outside that view would not appear "
                    "here, and a missing entry is missing information rather "
                    "than a finding that nothing happened."
                ),
            }
        )
    window = timefmt.window(incident.clip_window_start, incident.clip_window_end, tz)
    if incident.clip_status == "attached":
        blocks.append(
            {
                "no": 0,
                "basis": RECORDED,
                "source": "Clip request made by this software",
                "exhibit": "E1",
                "text": (
                    f"A clip covering {window} was requested from the device and "
                    "written to disk. Its SHA-256 is on the manifest sheet."
                ),
            }
        )
    else:
        failed = [a for a in incident.clip_attempts if a.get("outcome") != "attached"]
        blocks.append(
            {
                "no": 0,
                "basis": RECORDED,
                "source": "Clip request made by this software",
                "exhibit": "Gap" if failed else "",
                "text": (
                    f"No clip is attached to this record. Clip status: "
                    f"{incident.clip_status}. Every request for one, including "
                    "the ones that returned nothing, is a row on the manifest "
                    "sheet. A camera on event-only recording may never hold "
                    "footage for a past window; that is a property of the "
                    "recording plan, not of this record. The camera covers "
                    f"{coverage}."
                ),
            }
        )
    # PD 32 19.1(5): numbered paragraphs, numbered here rather than by hand so
    # the numbers cannot disagree with the order they print in.
    for number, block in enumerate(blocks, start=1):
        block["no"] = number
    return blocks


def _exhibits(
    incident: Incident, clip_bytes, snapshot_bytes, tz: str
) -> list[Exhibit]:
    exhibits: list[Exhibit] = []
    if clip_bytes is not None:
        exhibits.append(
            Exhibit(
                "E1",
                f"{incident.incident_id}.clip.bin",
                incident.clip_content_type or "application/octet-stream",
                len(clip_bytes),
                "Clip requested from the device for "
                + timefmt.window(incident.clip_window_start, incident.clip_window_end, tz)
                + f". Source: {incident.clip_source or NOT_RECORDED}.",
                hashlib.sha256(clip_bytes).hexdigest(),
            )
        )
    if snapshot_bytes is not None:
        exhibits.append(
            Exhibit(
                "E2",
                f"{incident.incident_id}.snapshot.bin",
                incident.snapshot_content_type or "application/octet-stream",
                len(snapshot_bytes),
                "Still requested from the device's image endpoint at "
                + timefmt.canonical(incident.occurred_at, tz)
                + ". Requested separately from the clip, not cut out of it. "
                + f"Source: {incident.snapshot_source or NOT_RECORDED}.",
                hashlib.sha256(snapshot_bytes).hexdigest(),
            )
        )
    for attempt in incident.clip_attempts:
        if attempt.get("outcome") == "attached":
            continue
        exhibits.append(
            Exhibit(
                "Gap",
                "no file",
                "",
                None,
                "Clip request at "
                + timefmt.canonical(attempt.get("at"), tz)
                + f" did not return a file. Reason: {attempt.get('reason', 'not recorded')}.",
                None,
            )
        )
    return exhibits


def _exhibit_range(exhibits: list[Exhibit]) -> str:
    refs = [e.ref for e in exhibits if e.ref.startswith("E")]
    if not refs:
        return "none"
    return refs[0] if len(refs) == 1 else f"{refs[0]} to {refs[-1]}"


def manifest_sha256_file(exhibits: list[Exhibit]) -> str:
    """Written in the exact layout `sha256sum -c` expects. A statutory record
    that tells its reader to run a command has to have that command succeed
    on the first try, on whatever machine an auditor or officer happens to
    be holding, without them first reading a spec for this employer's log."""
    lines = [f"{e.sha256}  {e.name}" for e in exhibits if e.sha256]
    return "\n".join(lines) + ("\n" if lines else "")
