"""Renders the two documents.

A Jinja environment of its own, rather than Flask's, for two reasons. The
documents have to be buildable and testable without an application context,
because a test that can only reach the evidence pack through an HTTP route is
testing the route. And autoescaping matters more here than anywhere else in
the app: the free-text fields are typed by a person under stress, an ampersand
or an angle bracket in someone's account of being threatened must not break the
document a police officer is reading, and the first build of this pack
interpolated those fields straight into an f-string.
"""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import timefmt
from .amendments import FIELD_LABEL, FIELD_LETTER
from .config import APP_DIR
from .document import grouped_hash
from .incident_language import assert_document_safe

_env = Environment(
    loader=FileSystemLoader(str(APP_DIR / "templates")),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["canonical"] = timefmt.canonical
_env.filters["day"] = timefmt.day
_env.filters["clock"] = timefmt.clock
_env.globals["window"] = timefmt.window
_env.globals["grouped"] = grouped_hash
_env.globals["letter_for"] = lambda name: FIELD_LETTER.get(name, "")
_env.globals["label_for_field"] = lambda name: FIELD_LABEL.get(name, name)


def render_record(context: dict) -> str:
    """The statutory log or the evidence pack, as one HTML document.

    The language guard runs over everything the app wrote into this document
    before it leaves the building. It deliberately skips the free-text fields:
    a person who was there is entitled to write what they saw, including a
    conclusion, and the document prints those words attributed to them. What
    it checks is the app's own prose, which has no standing to conclude
    anything.
    """
    for block in context["blocks"]:
        assert_document_safe(block["text"])
    html = _env.get_template("documents/record.html").render(**context)
    return html
