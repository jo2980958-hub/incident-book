"""What a model is allowed to introduce into statute field (C).

The thing this module stops
---------------------------
Field (C) of a California violent incident log is "a detailed description of
the incident". It is kept for five years, it is read by an insurer or a Cal/OSHA
inspector, and it goes into the evidence pack that reaches a police officer
unredacted. Until this file existed, the only check on the model's draft was
thirteen phrases in ``incident_language.py`` -- ``the thief``, ``the suspect``,
``the camera saw`` and ten more. The audit ran this through it:

    "The individual attempted to rob the register and threatened to kill the
    clerk. A man in his forties in a red jacket with a neck tattoo came over
    the counter."

and it passed, because no sentence in it contains any of the thirteen. A
model-authored allegation of armed robbery against a described person, in a
statutory record, is a real-world harm and not a scoring problem, so a denylist
of thirteen phrases is not a defence anybody should have been relying on.

The shape, and why it is not another denylist
--------------------------------------------
The guiding rule here is to pick the strongest shape the field
can stand on, and (C) is genuinely prose: it is a worker's account of what
happened, rewritten into plainer sentences. It cannot be an enum and it cannot
be an index. What it *can* be is **bounded by its source**.

So the rule is not "these words are banned". It is:

    A word from a hazardous class may appear in the draft only if the worker
    put it there.

The classes are the three the system prompt already forbids and nothing
validated: a criminal characterisation, a physical description of a person, and
an assertion about somebody's intent. Within those classes the allowlist is the
worker's own vocabulary plus the event details this app supplied. Outside them
the model rewrites freely, which is the job it is there to do.

That distinction matters and it is deliberate. A worker who types "he tried to
rob me and said he'd kill me" is entitled to have their account written up in
those words -- they were there. A model that reaches for "attempted to rob"
over "came over the counter shouting" has invented the most serious sentence in
the document. The same word, two different provenances, and provenance is the
only thing that separates them.

Race and ethnicity are the one unconditional refusal. They identify a person
under subdivision (d)(1)(B), the redaction in ``pii.py`` does not find them, and
the evidence pack is unredacted by design. If the worker wrote one, their own
words are kept verbatim by the fallback in ``drafting.py``, which is the
witness's account rather than this software's.

Nothing here is rendered. A refusal names the class and the field; the text goes
to the log. See GUARD-STANDARD.md §6.
"""

from __future__ import annotations

import re

from .draft_classes import (
    CLASSES,
    CRIME,
    DESCRIPTION,
    ETHNICITY,
    ETHNICITY_WORDS,
    FIGURE,
    INTENT,
)
from .draft_findings import DraftFinding
from .grounding import numbers_in
from .matching import normalise, prepare

_SUFFIXES = ("ing", "ed", "es", "s", "d", "e")


def _stems(token: str) -> set[str]:
    """A token and the shorter forms an inflection could have been built on.

    Crude on purpose. "shouting" and "shouted" both have to reach "shout", and a
    real stemmer is a dependency and a behaviour nobody in this repository can
    read off the page.
    """
    out = {token}
    for suffix in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            out.add(token[: -len(suffix)])
    if token.endswith("ies") and len(token) > 4:
        out.add(token[:-3] + "y")
    if len(token) > 4 and token[-1] == token[-2]:
        out.add(token[:-1])
    return out


def source_vocabulary(*sources: str) -> frozenset[str]:
    """Every word the worker typed and every word this app put on the record.

    Stems included, so a draft may inflect what the worker wrote. Nothing
    model-supplied is ever passed in here: an allowlist widened by the thing it
    constrains is not an allowlist.
    """
    vocabulary: set[str] = set()
    for source in sources:
        for token in prepare(source or "").tokens:
            vocabulary |= _stems(token)
    return frozenset(vocabulary)


def source_numbers(*sources: str) -> frozenset[str]:
    """Every figure the source stated, in any spelling.

    Read off the raw source rather than off the token set in
    `source_vocabulary`: tokens have lost the boundaries between them, and
    "555", "867" and "5309" rejoined with spaces read back as one ten-digit
    figure, which grounds nothing and un-grounds all three.
    """
    return frozenset(numbers_in("\n".join(s or "" for s in sources)))


def findings(
    draft_text: str, vocabulary: frozenset[str], numbers: frozenset[str] = frozenset()
) -> list[DraftFinding]:
    """Every hazardous word in the draft that the vocabulary does not contain."""
    if not draft_text.strip():
        return []
    folded = prepare(draft_text)
    found: list[DraftFinding] = []

    foreign = folded.foreign_letters()
    if foreign:
        found.append(DraftFinding("letters outside the alphabet this check reads", "".join(foreign)))

    for token in sorted(folded.tokens):
        if token in ETHNICITY_WORDS:
            # Unconditional: see the module docstring. The worker's own words
            # survive on the fallback path; this software does not retype them
            # into a field it signs as drafted.
            found.append(DraftFinding(ETHNICITY, token))
            continue
        if _stems(token) & vocabulary:
            continue
        for rule, words in CLASSES:
            if token in words:
                found.append(DraftFinding(rule, token))
                break

    for figure in sorted(numbers_in(draft_text) - set(numbers)):
        found.append(DraftFinding(FIGURE, figure))
    return found


_AGE_PHRASE = re.compile(
    r"\b(?:aged|age)\s+\d{1,3}\b|\b\d{1,3}\s*(?:years?\s*old|yo)\b|\bin\s+(?:his|her|their)\s+\d{2}s\b"
)


def has_age_claim(text: str) -> bool:
    """An age written as a figure rather than as a decade word.

    ``forties`` is in the description class above. ``in his 40s`` and ``aged 42``
    are the same claim spelled around the list, which is the whole reason a
    class is checked rather than a token.
    """
    return bool(_AGE_PHRASE.search(normalise(text)))
