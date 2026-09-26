"""Who kept this record, and where.

The design review left one High item unfixed because it needed a product
decision rather than a template change: the evidence pack states the incident
id, the spot inside the shop and the device id, and never the name or address
of the business. A police officer or an adjuster handed that pack cannot tell
which shop it came from. Put more sharply: a letterhead is the issuer's name,
legal entity, address and a document identifier, in text, and a document
without one is not a document.

The decision, and why it went this way.

**A premises is a record in its own right, not a config constant, and an
install can hold more than one.** The obvious cheap answer was two lines in a
settings file. It was rejected for three reasons. Labor Code 6401.9(d)(1)(C)
already contemplates more than one employer at a worksite and requires the log
to be handed to the controlling employer, so the premises identity has to be a
value on the record and not an ambient fact about the server. An owner with a
shop and a unit round the corner has one Ring account, and asking them to run
two copies of a compliance book is how the second shop's log ends up empty.
And a record is retained five years: if the business is renamed, moved or
sold, the pack for an incident in 2026 has to keep printing the name and
address that were true in 2026, which a single mutable config value cannot do.
So each incident stores the ``premises_id`` it belonged to, and a premises is
never edited in place once incidents point at it: an edit writes a new revision
and old records keep resolving to the old one.

**A device's coverage belongs here too.** The provenance block on the pack has
to say what the camera could see and what it could not. Ring supplies a
``location`` string and nothing about blind spots, so the shop supplies it
once, on the settings screen, and every pack from that camera carries it.

**Capture is never blocked on any of this.** If nobody has filled the premises
in yet, the button still works, the record still saves, and every document
prints ``Not recorded`` in the premises rows rather than inventing a name. An
empty statutory field is a fact about the record. A guessed one is a lie.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass
class Premises:
    premises_id: str
    name: str = ""
    legal_entity: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    establishment_id: str = ""
    # Ring timestamps are epoch milliseconds and carry no local offset, so
    # the shop tells us its zone once and every document prints the right
    # local time. Left empty, everything prints in UTC and says so.
    timezone_name: str = ""
    revision: int = 1
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))

    @staticmethod
    def new_id() -> str:
        return f"prem_{uuid.uuid4().hex[:10]}"

    @property
    def is_named(self) -> bool:
        return bool(self.name.strip())

    def address_lines(self) -> list[str]:
        """Address as a reader would write it on an envelope, skipping the
        lines that are empty rather than printing blanks."""
        lines = [self.address_line1, self.address_line2]
        town = " ".join(p for p in (self.city, self.state) if p).strip()
        if town or self.postal_code:
            lines.append(" ".join(p for p in (town, self.postal_code) if p))
        return [line for line in (s.strip() for s in lines) if line]

    def one_line(self) -> str:
        parts = [self.name] + self.address_lines()
        return ", ".join(p for p in parts if p) or "Not recorded"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Premises":
        known = {k: v for k, v in d.items() if k in Premises.__dataclass_fields__}
        return Premises(**known)


@dataclass
class DeviceRegistration:
    """What the shop knows about one camera that Ring does not tell us.

    ``covers`` and ``does_not_cover`` print in the evidence pack's provenance
    block, beside the clip and the clock, because what the camera cannot see
    is a fact about how the record was produced.
    """

    device_id: str
    premises_id: str = ""
    covers: str = ""
    does_not_cover: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "DeviceRegistration":
        known = {
            k: v for k, v in d.items() if k in DeviceRegistration.__dataclass_fields__
        }
        return DeviceRegistration(**known)


UNRECORDED = Premises(premises_id="", name="")


def resolve(premises: Optional[Premises]) -> Premises:
    """Never return None to a template. A missing premises is a premises with
    nothing in it, and every document knows how to print that."""
    return premises or UNRECORDED
