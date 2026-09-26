"""Signed Ring webhook verification and parsing.

The topic file documents this as: "Signed webhooks (HMAC-SHA256 in
X-Signature) for motion_detected (with attributes.sub_type, such as
human), button_press, device_added, ..." and nothing more: no worked
example, no canonicalisation rule, no replay-protection scheme. What
follows is this build's own decision, given that gap.

Signing scheme implemented: hex(HMAC-SHA256(shared_secret, raw_body_bytes)),
constant-time compared. If Ring's real scheme canonicalises differently
(e.g. sorts JSON keys, or signs a subset of headers), this is the one
function to change.
"""

from __future__ import annotations

import hashlib
import hmac
import json


class InvalidSignature(Exception):
    pass


def sign(secret: str, raw_body: bytes) -> str:
    """Produce the X-Signature value for a given body. Used by
    tools/replay_webhook.py to sign fixtures the same way the app verifies
    them, and by tests."""
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    """Constant-time comparison. Returns False rather than raising, so
    callers decide how to respond (the Flask route returns 401)."""
    if not signature:
        return False
    expected = sign(secret, raw_body)
    return hmac.compare_digest(expected, signature)


def parse_webhook(raw_body: bytes) -> dict:
    """Parses the verified body into a plain dict. Deliberately does not
    validate the full shape here -- app/server.py decides what fields it
    needs and fails loudly if they're missing, rather than this module
    silently defaulting them."""
    return json.loads(raw_body.decode("utf-8"))
