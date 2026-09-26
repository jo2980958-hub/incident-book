"""The two documents, built. Both go through document.py so they cannot
disagree, and both come back as HTML plus a JSON manifest.

The manifest states what its hashes cover and what they do not: a hash this
software computed itself over a file it also wrote is a checksum, not
verification by anybody, and calling it verification is the fastest way to
lose the reader whose job is to reject things.
"""

from __future__ import annotations

import time
from typing import Optional

from . import document
from .document import manifest_sha256_file
from .drafting import Draft
from .incident_fields import Incident
from .premises import DeviceRegistration, Premises
from .render import render_record

HASH_SCOPE = (
    "Each SHA-256 was computed by Incident Book over the bytes of the file "
    "exactly as written to disk at capture. It shows whether the file has "
    "changed since. It is not evidence of what the camera was pointed at, and "
    "it is not a signature by any third party."
)


def build_document(
    kind: str,
    incident: Incident,
    clip_bytes: Optional[bytes] = None,
    snapshot_bytes: Optional[bytes] = None,
    premises: Optional[Premises] = None,
    device: Optional[DeviceRegistration] = None,
    draft: Optional[Draft] = None,
    revisions: Optional[list[dict]] = None,
    generated_at: Optional[int] = None,
) -> tuple[str, dict]:
    """``kind`` is "log" for the de-identified statutory log, "pack" for the
    police and insurer copy. Returns the HTML and the manifest."""
    generated_at = generated_at or int(time.time() * 1000)
    context = document.build(
        kind=kind,
        incident=incident,
        premises=premises,
        device=device,
        draft=draft,
        revisions=revisions or [],
        clip_bytes=clip_bytes,
        snapshot_bytes=snapshot_bytes,
        generated_at=generated_at,
    )
    html = render_record(context)
    return html, _manifest(context)


def build_evidence_pack(
    incident: Incident,
    clip_bytes: Optional[bytes] = None,
    snapshot_bytes: Optional[bytes] = None,
    **kwargs,
) -> tuple[str, dict]:
    """The police and insurer copy. Kept as its own name because that is what
    the rest of the app and the tests call it."""
    return build_document("pack", incident, clip_bytes, snapshot_bytes, **kwargs)


def build_statutory_log_document(
    incident: Incident,
    clip_bytes: Optional[bytes] = None,
    snapshot_bytes: Optional[bytes] = None,
    **kwargs,
) -> tuple[str, dict]:
    return build_document("log", incident, clip_bytes, snapshot_bytes, **kwargs)


def _manifest(context: dict) -> dict:
    incident = context["incident"]
    return {
        "document": context["title"],
        "form_id": context["form_id"],
        "produced_by": f"Incident Book {context['app_version']}",
        "incident_id": incident.incident_id,
        "record_revision": context["revision"],
        "generated_at": context["generated_display"],
        "premises": context["premises"].one_line(),
        "hash_scope": HASH_SCOPE,
        "verification_command": "sha256sum -c manifest.sha256",
        "exhibits": [
            {
                "ref": e.ref,
                "file": e.name,
                "media_type": e.media_type,
                "bytes": e.size_bytes,
                "sha256": e.sha256,
                "description": e.description,
            }
            for e in context["exhibits"]
        ],
        "redactions": [
            {"kind": f.kind, "certain": f.certain} for f in context["redactions"]
        ],
        "missing_statute_fields": [
            {"letter": letter, "what": what} for letter, what in context["missing"]
        ],
        "manifest_sha256_file": manifest_sha256_file(context["exhibits"]),
    }
