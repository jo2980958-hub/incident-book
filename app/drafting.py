"""The one place this app asks a model for anything.

The situation it exists for. A member of staff has just been threatened across
the counter. They pressed the button, so the date, the time, the location and
the clip are already on the record. What is left is statute field (C), "a
detailed description of the incident", and field (H), the consequences and
whether law enforcement was contacted. Those are prose, they will be read years
later by an insurer or a Cal/OSHA inspector, and the person who has to write
them is shaking. So they say or type a few words, and the model turns those few
words into a first draft of those two fields.

What the model is not allowed to touch, and why. Every classification field --
(B) the violence type, (D) who committed it, (E) the circumstances, (F) where,
(G) the type of incident -- stays human-chosen. Those are the fields that make
the log an assertion about a person, Ring gives no identity beyond
``sub_type: human``, and its classifier has been documented calling a motorised
wheelchair a package. A model picking "stranger with criminal intent" off a
motion event is the accusation this product refuses to make.

What makes it defensible. Nothing the model writes is ever a saved field. It
becomes a proposal attached to the incident, the human opens it in the ordinary
completion form, edits it, and saves. The save is what files it, and the
amendment trail records who filed it, when, and whether they changed the
drafted words or accepted them unchanged. Both of those sentences print on the
document, in one of two fixed sentences:
"Drafted by software, edited by completer" or "Drafted by software, accepted
unchanged".

When Bedrock cannot be reached, the fallback is not an error page. The staff
member's own words go into the description field verbatim and the screen says
the drafting step was skipped. Losing what someone typed after being threatened
because a network was down is not an acceptable failure.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from . import draft_language, pii
from .bedrock import BedrockRunner, BedrockUnavailable
from .incident_language import DocumentLanguageError, assert_document_safe

_log = logging.getLogger(__name__)

# The letter each drafted field carries on the statutory form. The screen
# names the field by its letter rather than by its Python attribute, because
# the letter is the field's name in every conversation about it.
FIELD_LETTER = {
    "description": "C",
    "consequences_response": "H",
    "consequences_actions": "H",
}

MAX_WORDS_IN = 4000  # a few sentences typed at a counter, with room to spare

SYSTEM = """\
You help a worker in a small shop write two fields of a California violent \
incident log (Labor Code 6401.9(d)(2)) immediately after a violent incident. \
You are writing a first draft that the worker will read, edit and sign. You \
are not filing anything.

Rules, all of them absolute:

1. Use only what the worker told you and the recorded event details you are \
given. Invent nothing. If the worker did not say whether the police were \
called, leave that field empty rather than guessing.
2. Never name, identify or describe any person. No names, no physical \
description, no clothing, no vehicle, no race, no age. Write "a person" or \
"the individual". If the worker used a name, write "a person" instead.
3. The camera's own classification is the manufacturer's automatic \
classification, not a fact. Never write that the camera saw a person. If you \
mention the event at all, write that the device classified an event.
4. Never conclude, accuse or judge. Do not write that anyone stole, attacked, \
intended or lied. Describe only what the worker said happened.
5. Never use the words verified, confirmed, proven, proof, admissible or \
tamper-proof.
6. Plain English, past tense, short sentences, no adjectives that argue. \
Somewhere between two and eight sentences for the description. Keep the \
worker's own facts and their own order of events.
7. Write nothing about how the worker should feel and no reassurance. This is \
a record, not a message to them.
"""

TOOL = {
    "name": "draft_log_fields",
    "description": (
        "Return draft text for statute fields (C) and (H) of a California "
        "violent incident log. Every field may be empty if the worker did not "
        "give you the facts for it."
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "Field (C), a detailed description of the incident, "
                        "drawn only from what the worker said."
                    ),
                },
                "consequences_response": {
                    "type": "string",
                    "description": (
                        "Field (H)(i): whether security or law enforcement was "
                        "contacted and their response. Empty if not stated."
                    ),
                },
                "consequences_actions": {
                    "type": "string",
                    "description": (
                        "Field (H)(ii): actions taken to protect employees from "
                        "a continuing threat. Empty if not stated."
                    ),
                },
            },
            "required": ["description"],
            # No additional properties, and in particular no free-text field
            # beyond the two the statute asks for in prose. An earlier version
            # of this tool carried a ``not_said`` array of model-written
            # questions: an unvalidated string field that was rendered to the
            # completer in the app's own voice, above the statutory form, where
            # it could have steered the very classifications (B), (D), (E), (F)
            # and (G) that the whole design refuses to let a model touch. What
            # it was for is computed deterministically instead, by
            # ``Incident.missing_statute_fields()``, and printed on the same
            # screen. A field with nothing to validate is better than a field
            # with a validator.
            "additionalProperties": False,
        }
    },
}

DRAFTED_FIELDS = ("description", "consequences_response", "consequences_actions")


@dataclass
class Draft:
    """A proposal. Never a saved field until a human presses save."""

    incident_id: str
    source_words: str
    description: str = ""
    consequences_response: str = ""
    consequences_actions: str = ""
    model_id: str = ""
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    status: str = "proposed"  # proposed | unavailable | rejected
    note: str = ""

    @property
    def came_from_a_model(self) -> bool:
        return self.status == "proposed" and bool(self.model_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Draft":
        known = {k: v for k, v in d.items() if k in Draft.__dataclass_fields__}
        return Draft(**known)


def draft_narrative(
    runner: BedrockRunner,
    incident,
    words: str,
    premises_label: str = "",
) -> Draft:
    """Ask the model for fields (C) and (H). Always returns a Draft.

    Three ways this ends, and none of them loses the worker's words:
    a proposal, an ``unavailable`` draft carrying their words verbatim because
    Bedrock could not be reached, or a ``rejected`` draft carrying their words
    verbatim because what came back broke one of the language rules.
    """
    words = (words or "").strip()[:MAX_WORDS_IN]
    if not words:
        return Draft(
            incident_id=incident.incident_id,
            source_words="",
            status="unavailable",
            note="Nothing was typed, so there was nothing to draft from.",
        )
    try:
        result = runner.converse(
            system=SYSTEM, user_text=_user_text(incident, words, premises_label), tool=TOOL
        )
    except BedrockUnavailable as exc:
        return _fallback(incident, words, "unavailable", _offline_note(exc.reason))

    proposed = result.get("tool_input") or {}
    draft = Draft(
        incident_id=incident.incident_id,
        source_words=words,
        description=str(proposed.get("description", "")).strip(),
        consequences_response=str(proposed.get("consequences_response", "")).strip(),
        consequences_actions=str(proposed.get("consequences_actions", "")).strip(),
        model_id=result.get("model_id", ""),
        latency_seconds=result.get("latency_seconds", 0.0),
        input_tokens=result.get("usage", {}).get("inputTokens", 0),
        output_tokens=result.get("usage", {}).get("outputTokens", 0),
    )
    problem = _language_problem(draft, words, _recorded_details(incident, premises_label))
    if problem:
        rejected = _fallback(incident, words, "rejected", problem)
        rejected.model_id = draft.model_id
        return rejected
    return draft


def _recorded_details(incident, premises_label: str) -> str:
    """What this app put on the record before the model was called.

    Part of the allowlist the draft is checked against, alongside the worker's
    own words, because a draft that mentions the camera location or the device's
    own event classification is repeating something this repository computed.
    Nothing model-supplied is in here; see `draft_language.source_vocabulary`.
    """
    return " ".join(
        str(part or "")
        for part in (
            premises_label,
            incident.location,
            incident.event_summary,
            incident.clip_status,
        )
    )


def _user_text(incident, words: str, premises_label: str) -> str:
    lines = [
        "Recorded event details, already on the record:",
        f"  Premises: {premises_label or 'not recorded'}",
        f"  Camera location: {incident.location}",
        f"  Event: {incident.event_summary or 'no event was recorded on the camera'}",
        f"  Clip: {incident.clip_status}",
        "",
        "What the worker said happened, in their own words:",
        words,
    ]
    return "\n".join(lines)


def _language_problem(draft: Draft, words: str, recorded: str = "") -> Optional[str]:
    """Every rule the model was given, checked rather than trusted.

    **A hazardous word has to come from the worker.** The thirteen phrases in
    ``incident_language.py`` are a denylist, and a denylist is a list of the
    sentences its author imagined. It is correct on those and silent on
    everything else, and "attempted to rob the register and threatened to kill
    the clerk" is everything else: it passed, into statute field (C) of a
    five-year record. ``draft_language.py`` replaces the hope with a rule --
    a criminal characterisation, a physical description or a claim about intent
    may appear in the draft only if the worker put it in what they typed. The
    model still rewrites freely everywhere else, which is the job it is here to
    do. See GUARD-STANDARD.md §1 and §3.

    Two more things are deliberate here and both were wrong in an earlier build.

    **An uncertain finding is a reason to refuse, not a reason to allow.**
    ``pii.Finding.certain`` is True for a matched shape and False for the
    capitalised-run name heuristic, and the earlier version of this check
    skipped the uncertain ones. That is exactly backwards. The certain shapes
    are phone numbers and email addresses; the uncertain ones are plain names,
    which is the single thing a model should never introduce into a statutory
    record. Worse, the redaction that would have caught it downstream runs only
    on the statutory log: the evidence pack is unredacted by design, so an
    invented name would have reached a police officer with a gutter note
    reading "Drafted by software, accepted unchanged". So: any identifier-
    shaped span that is not in what the worker typed discards the whole draft,
    certain or not. A false refusal costs one person one convenience and they
    keep their own words; a false pass costs somebody their name in a police
    document.

    **Nothing the guard refused is quoted back to a person.** The refusal is
    model output with a frame around it, not metadata, and printing it on the
    completion form would be a second output path around the guard. The rule
    that fired and the field it fired on go on the screen; the text itself goes
    to the log, where a developer is and the completer is not.
    """
    typed = words.casefold()
    vocabulary = draft_language.source_vocabulary(words, recorded)
    stated_numbers = draft_language.source_numbers(words, recorded)
    for name in DRAFTED_FIELDS:
        text = getattr(draft, name)
        if not text:
            continue
        try:
            assert_document_safe(text)
        except DocumentLanguageError as exc:
            _log.warning(
                "draft for %s discarded: %s rule fired on field %s: %s",
                draft.incident_id, exc.rule, FIELD_LETTER[name], exc,
            )
            return (
                f"The drafted wording broke this app's {exc.rule} rule in field "
                f"({FIELD_LETTER[name]}), so the whole draft was discarded and "
                "your own words were kept. The wording itself is in the "
                "application log and is not repeated here."
            )
        for finding in pii.find(text):
            if finding.text.casefold() not in typed:
                _log.warning(
                    "draft for %s discarded: %s in field %s was not in what the "
                    "worker typed", draft.incident_id, finding.kind,
                    FIELD_LETTER[name],
                )
                return (
                    "The drafted text put something that looks like a "
                    f"{finding.kind} into field ({FIELD_LETTER[name]}) that was "
                    "not in what you typed, so the whole draft was discarded "
                    "and your own words were kept."
                )
        for finding in draft_language.findings(text, vocabulary, stated_numbers):
            _log.warning(
                "draft for %s discarded: %s in field %s (%r was not in what the "
                "worker typed)",
                draft.incident_id, finding.rule, FIELD_LETTER[name], finding.word,
            )
            return finding.public_reason(FIELD_LETTER[name])
        if draft_language.has_age_claim(text):
            _log.warning(
                "draft for %s discarded: an age claim in field %s",
                draft.incident_id, FIELD_LETTER[name],
            )
            return draft_language.DraftFinding(
                draft_language.DESCRIPTION, ""
            ).public_reason(FIELD_LETTER[name])
    return None


def _fallback(incident, words: str, status: str, note: str) -> Draft:
    return Draft(
        incident_id=incident.incident_id,
        source_words=words,
        description=words,
        status=status,
        note=note,
    )


def _offline_note(reason: str) -> str:
    return (
        "Bedrock could not be reached, so nothing was drafted and your own "
        f"words were kept exactly as you typed them. Reason: {reason}"
    )


def provenance_marker(draft: Optional[Draft], filed_text: str, field_name: str) -> str:
    """The sentence that prints in the document's gutter beside a drafted
    field, in this app's fixed provenance wording.

    An inspector reading a suspiciously fluent incident description is
    entitled to know where the fluency came from, and whether a human changed
    a word of it.
    """
    if draft is None or not draft.came_from_a_model:
        return "Written by completer"
    proposed = (getattr(draft, field_name, "") or "").strip()
    if not proposed:
        return "Written by completer"
    if filed_text.strip() == proposed:
        return "Drafted by software, accepted unchanged"
    return "Drafted by software, edited by completer"
