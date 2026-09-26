"""What a refusal is, and how it explains itself to the person who caused it.

The third file in the split `guard.py` / `guard_rules.py` / `guard_findings.py`
already uses one package over, for the reason Doorstep gives there: a finding
has a job the scanner does not. It has to be readable by somebody who has just
had their draft discarded and wants to know why, standing at a counter, shortly
after being threatened.

The two payloads are the point, and GUARD-STANDARD.md §6 is why. ``rule`` is
app-authored and goes on the screen. ``word`` is model output and goes to the
log. A rejection is model output with a frame around it, not metadata, and a
refusal that reprints what it refused is a second output path around the guard
-- the drafted sentence shown one paragraph lower with a label on it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DraftFinding:
    """One class the draft entered that its source did not.

    ``rule`` is app-authored and safe to render. ``word`` is model output and
    goes to the log only -- a refusal that reprints the refused text is a second
    output path around the guard.
    """

    rule: str
    word: str

    def public_reason(self, field_letter: str) -> str:
        return (
            f"The drafted wording put {self.rule} into field ({field_letter}) that was "
            "not in what you typed, so the whole draft was discarded and your own "
            "words were kept. The wording itself is in the application log."
        )
