"""Personal identifying information, which this particular document is
required by statute to leave out.

Labor Code 6401.9(d)(1)(B), read from the section text at leginfo:

    The employer shall omit any element of personal identifying information
    sufficient to allow identification of any person involved in a violent
    incident, such as the person's name, address, electronic mail address,
    telephone number, social security number, or other information that, alone
    or in combination with other publicly available information, reveals the
    person's identity.

That is a duty on the log, not a preference of ours, and it happens to line up
exactly with the reason this app never names anyone off a Ring classification.
So the rule is enforced in one place and applied twice:

- the **statutory log export** is redacted, every time, and says on its face
  that it was, with the citation and a list of what was removed;
- the **evidence pack** for the police or the insurer is a different document,
  is not redacted, and says on its face that it carries identifying detail and
  should be handled accordingly.

Shipping one document that tries to be both is the failure mode here.

What this module is not. It is a reading aid, not a guarantee. It finds the
shapes a regular expression can find and it flags runs of capitalised words
that look like names, which will sometimes be a street or a brand. The person
completing the log is told that plainly on the screen, because a tool that
claims to have removed all identifying information and has not is worse than
no tool. Nothing here ever edits a stored record: the raw words the human
wrote are kept exactly as written, and redaction happens when the log document
is produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Words that start a sentence or are simply capitalised in ordinary English.
# Without this list every "He Said" and "The Counter" reads as a person.
_COMMON = {
    "a", "about", "after", "an", "and", "as", "at", "back", "before", "but",
    "by", "counter", "did", "door", "for", "from", "front", "he", "her",
    "him", "his", "i", "if", "in", "into", "it", "its", "later", "me", "my",
    "no", "not", "of", "on", "one", "or", "our", "out", "over", "police",
    "said", "she", "shop", "so", "store", "street", "the", "their", "them",
    "then", "there", "they", "this", "to", "told", "two", "up", "us", "we",
    "went", "when", "which", "who", "with", "you", "your", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}

_PATTERNS: tuple[tuple[str, str, str], ...] = (
    (
        "social security number",
        r"\b\d{3}-\d{2}-\d{4}\b",
        "social security number",
    ),
    (
        "electronic mail address",
        r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
        "electronic mail address",
    ),
    (
        "telephone number",
        r"(?<![\d-])(?:\+1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?![\d-])",
        "telephone number",
    ),
    (
        "address",
        r"\b\d{1,5}\s+(?:[A-Z][\w'-]*\s+){0,3}"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct)\b",
        "address",
    ),
    (
        "vehicle registration",
        r"\b(?:plate|licence plate|license plate|reg)\s+[A-Z0-9]{2,3}[ -]?[A-Z0-9]{3,4}\b",
        "vehicle registration",
    ),
    (
        "web address",
        r"\bhttps?://\S+\b",
        "web address",
    ),
    (
        "name",
        r"\b(?:Mr|Mrs|Ms|Miss|Dr|Sgt|Officer|Detective)\.?\s+[A-Z][a-z]+\b",
        "name",
    ),
)

_CAP_RUN = re.compile(r"\b[A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,})*\b")
_SENTENCE_END = re.compile(r"[.!?\n]\s*$")


def _name_runs(text: str) -> list[tuple[int, int, str]]:
    """Capitalised word runs that look like somebody's name.

    The naive version of this, two capitalised words in a row, reads "Call
    John Smith" as the name "Call John" and leaves the surname in the log.
    So: strip leading words that are capitalised because English capitalises
    them, drop the first word of a run that begins a sentence when the run is
    long enough to survive it, and only then call what is left a name.
    """
    out = []
    for match in _CAP_RUN.finditer(text):
        words = match.group().split()
        starts = _word_starts(text, match.start(), words)
        while words and words[0].lower() in _COMMON:
            words, starts = words[1:], starts[1:]
        if words and len(words) >= 3 and _starts_a_sentence(text, starts[0]):
            words, starts = words[1:], starts[1:]
        if len(words) < 2:
            continue
        begin = starts[0]
        end = starts[-1] + len(words[-1])
        out.append((begin, end, text[begin:end]))
    return out


def _word_starts(text: str, offset: int, words: list[str]) -> list[int]:
    starts, cursor = [], offset
    for word in words:
        cursor = text.index(word, cursor)
        starts.append(cursor)
        cursor += len(word)
    return starts


def _starts_a_sentence(text: str, index: int) -> bool:
    return index == 0 or bool(_SENTENCE_END.search(text[:index]))


@dataclass(frozen=True)
class Finding:
    kind: str  # the statute's own word for it, where the statute has one
    text: str
    start: int
    end: int
    certain: bool  # False for the name heuristic, True for a matched shape

    @property
    def placeholder(self) -> str:
        return f"[{self.kind} removed]"


def find(text: str) -> list[Finding]:
    """Everything in this text that looks like personal identifying
    information, earliest first, without overlaps."""
    found: list[Finding] = []
    for kind, pattern, _ in _PATTERNS:
        for m in re.finditer(pattern, text):
            found.append(Finding(kind, m.group(), m.start(), m.end(), True))
    for start, end, span in _name_runs(text):
        found.append(Finding("name", span, start, end, False))
    return _without_overlaps(found)


def _without_overlaps(found: list[Finding]) -> list[Finding]:
    """A certain match wins over the name heuristic when they cover the same
    words, so "Officer Diaz" is reported once as a name and not twice."""
    found.sort(key=lambda f: (f.start, not f.certain, -(f.end - f.start)))
    kept: list[Finding] = []
    for f in found:
        if kept and f.start < kept[-1].end:
            continue
        kept.append(f)
    return kept


def redact(text: str) -> tuple[str, list[Finding]]:
    """The text with each finding replaced by a named placeholder, and the
    list of what was taken out. The list is what gets printed on the log so
    the removal is stated rather than silent."""
    findings = find(text)
    out, cursor = [], 0
    for f in findings:
        out.append(text[cursor : f.start])
        out.append(f.placeholder)
        cursor = f.end
    out.append(text[cursor:])
    return "".join(out), findings


def summarise(findings: list[Finding]) -> str:
    """One line for the face of the log: what kinds were removed and how many
    of each, in the order the statute lists them."""
    if not findings:
        return "No personal identifying information was found to remove."
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    parts = [f"{n} {kind}{'s' if n > 1 else ''}" for kind, n in counts.items()]
    return "Removed: " + ", ".join(parts) + "."
