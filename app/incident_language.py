"""Two language rules, enforced at one choke point.

**No accusation.** The app itself never names or accuses a person. Ring gives
no identity beyond ``sub_type: human`` and its classifier has been documented
labelling a motorised wheelchair a package.

**No overclaiming.** This app maintains a fixed list of the
words that lose a document its reader: verified, confirmed, proven, proof of,
tamper-proof, court-admissible, legally binding. Admissibility is a judge's
ruling under FRE 901, not a property a file can have, and "verified" beside a
hash this software computed itself, five minutes ago, over a file it also
wrote, is a checksum being sold as something it is not. The app writes
"checked" and "computed", and says what it computed the hash over.

Both rules apply to text this app composes: the event summary, the evidence
pack, the log export, and anything a model drafts. They do not apply to a free
text field a human typed. A person who was there is entitled to write what
they saw in their own words, including a conclusion, and it is not this app's
place to censor a witness. What the app does with such a field is print it as
what it is: the completer's own account, attributed to them, in the document's
own gutter.

They do not apply to a verbatim quotation of the statute either, and that is
not a loophole, it is the point. Subdivision (d)(2)(D) reads "including
whether the perpetrator was", which trips the accusation rule word for word.
``DOCUMENT-CRAFT.md`` section 6 rule 5 is the tie-breaker: paraphrasing the
statute and printing only the paraphrase is how a form gets rejected. So the
statutory wording prints as written, marked as a quotation, and the guard runs
over the sentences this app wrote for itself.
"""

from __future__ import annotations

import re
from typing import Optional

from .ring_types import RingEvent

BANNED_ACCUSATIONS = (
    r"\bthe thief\b",
    r"\bthe suspect\b",
    r"\bthe intruder\b",
    r"\bthe offender\b",
    r"\bhe stole\b",
    r"\bshe stole\b",
    r"\bthey stole\b",
    r"\bthe perpetrator\b",
    r"\bthe attacker\b",
    r"\bthe assailant\b",
    r"\bthe criminal\b",
    r"\bdetected a person\b",
    r"\bthe camera saw\b",
)

BANNED_OVERCLAIMS = (
    r"\bverified\b",
    r"\bverifies\b",
    r"\bverification of\b",
    r"\bconfirmed\b",
    r"\bconfirms\b",
    r"\bproven\b",
    r"\bproof of\b",
    r"\btamper[- ]proof\b",
    r"\btamper[- ]evident\b",
    r"\bcourt[- ]admissible\b",
    r"\badmissible\b",
    r"\blegally binding\b",
    r"\bAI[- ]generated\b",
)

_ACCUSATION_RE = re.compile("|".join(BANNED_ACCUSATIONS), re.IGNORECASE)
_OVERCLAIM_RE = re.compile("|".join(BANNED_OVERCLAIMS), re.IGNORECASE)


class DocumentLanguageError(Exception):
    """A rule about what this app is allowed to say was broken. Callers that
    treat both rules the same way catch this.

    ``rule`` names the rule in words a person can read. The exception's own
    message quotes the phrase that fired it, which is what a developer reading
    a log needs and is exactly what must not reach a screen: text the guard
    refused is model output with a frame around it, not metadata, and printing
    it is a second output path around the guard. Callers show ``rule``; the
    message goes to the log.
    """

    rule = "language"


class AccusatoryLanguageError(DocumentLanguageError):
    """Raised when app-generated text would name or accuse a person."""

    rule = "no accusation"


class OverclaimError(DocumentLanguageError):
    """Raised when app-generated text claims more than it can support."""

    rule = "no overclaiming"


def assert_no_accusatory_language(text: str) -> None:
    match = _ACCUSATION_RE.search(text)
    if match:
        raise AccusatoryLanguageError(
            f"app-generated text contains banned phrase {match.group()!r}"
        )


def assert_no_overclaiming(text: str) -> None:
    match = _OVERCLAIM_RE.search(text)
    if match:
        raise OverclaimError(
            f"app-generated text overclaims with {match.group()!r}; "
            "say what was computed or checked instead"
        )


def assert_document_safe(text: str) -> None:
    """Both rules, in the order a reader would notice them."""
    assert_no_accusatory_language(text)
    assert_no_overclaiming(text)


def compose_event_summary(event: Optional[RingEvent]) -> str:
    """The only narrative sentence the app writes on its own.

    It is phrased as the device's assertion rather than as a fact, because
    that is what it is: ``sub_type`` is the manufacturer's automatic
    classification, it has not been checked by a person, and it is not a
    statement that a person was present.

    It carries no timestamp. The time is on the record as a number, and every
    screen and both documents print it through ``timefmt`` in the premises's
    own zone. A sentence with a time baked into it at capture would still be
    in UTC years later, on a document whose every other time was local, and
    two time formats on one page is the commonest reason a reader stops
    believing a document."""
    if event is None:
        summary = "No event was recorded on this camera around the time of the tap."
    elif event.sub_type:
        summary = (
            f"The device classified the event {event.sub_type!r}. That "
            "classification is the manufacturer's automatic one, it has not "
            "been checked by a person, and it is not a statement that a "
            f"person was present. Device {event.device_id}."
        )
    else:
        summary = (
            f"The device recorded an event of type {event.event_type!r}. "
            f"Device {event.device_id}."
        )
    assert_document_safe(summary)
    return summary
