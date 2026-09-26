"""Numeric grounding: is this figure one the source actually stated?

Split from `matching.py` on the seam the project's internal guard standard
draws between the two jobs: folding a string so a list can be compared
against it, versus deciding whether a number is allowed. They share the fold
and nothing else, and the rule below is the whole of the second job in one
sentence:

> **A number is allowed because it appears in the source. Never because it is
> small, common, or plausible.**

A grounding check that allowlists `{str(n) for n in range(0, 8)}`
unconditionally is that failure in one line. Every integer 0-7 was grounded
with no check at all, and every number this
product argues about -- visits scheduled, visits without arrival, quiet days,
door count, days covered -- lives in that range. The anti-hallucination check
was inoperative for exactly the figures an accusation rides on.

Digits are not the only way to write a number, so the allowlist is built from
the source with every spelling folded to one canonical form, and the candidate
is folded the same way. If a figure is hard to ground, that is a signal the
field wants a stronger shape from §1, not a reason to widen the allowlist.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .matching import normalise

_UNITS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
          "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
          "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
        "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "once": 1, "twice": 2,
        "half": Decimal("0.5")}

_NUM_RE = re.compile(r"\d[\d,_ ]*(?:\.\d+)?|\.\d+")
_CLOCK_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def canon(value) -> str:
    """One spelling per quantity: 2.50, 2.5 and "two point five" all give "2.5"."""
    try:
        d = Decimal(str(value)).normalize()
    except InvalidOperation:
        return ""
    if d == d.to_integral_value():
        d = d.quantize(Decimal(1))
    return format(d, "f")


def _digit_numbers(text: str) -> set[str]:
    out = set()
    for m in _NUM_RE.finditer(text):
        cleaned = re.sub(r"[,_ ](?=\d{3}\b)", "", m.group(0))
        cleaned = cleaned.replace(",", "").replace("_", "").replace(" ", "")
        if c := canon(cleaned):
            out.add(c)
    return out


def _word_numbers(text: str) -> set[str]:
    out: set[str] = set()
    toks = re.findall(r"[a-z]+", text)
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in _UNITS or t in _TENS:
            val = Decimal(_UNITS.get(t, _TENS.get(t, 0)))
            j = i + 1
            if t in _TENS and j < len(toks) and toks[j] in _UNITS:
                val += _UNITS[toks[j]]
                j += 1
            if j < len(toks) and toks[j] == "point":
                frac, k = "", j + 1
                while k < len(toks) and toks[k] in _UNITS and _UNITS[toks[k]] < 10:
                    frac += str(_UNITS[toks[k]])
                    k += 1
                if frac:
                    val, j = Decimal(f"{val}.{frac}"), k
            if j < len(toks) and toks[j] in ("hundred", "thousand"):
                val *= 100 if toks[j] == "hundred" else 1000
                j += 1
            out.add(canon(val))
            i = j
            continue
        if t in _ORD:
            out.add(canon(_ORD[t]))
        i += 1
    return out


def numbers_in(text: str) -> set[str]:
    """Every quantity `text` states, however it is spelled.

    Digits, digits with separators, decimals, word numbers and their compounds,
    ordinals in both forms, `once`/`twice`/`half`, and both halves of a clock
    time. Unicode digits are handled by the NFKC step in `normalise`.
    """
    t = normalise(text)                      # hyphens folded, so "twenty-three" splits
    found = _digit_numbers(t) | _word_numbers(t)
    for m in _CLOCK_RE.finditer(t):
        found |= {canon(m.group(1)), canon(m.group(2))}
    return found


def ungrounded_numbers(candidate: str, source: str) -> list[str]:
    """Every number in the candidate the source does not contain. Empty == grounded."""
    allowed = numbers_in(source)
    return sorted(n for n in numbers_in(candidate) if n not in allowed)
