"""The Flask app factory. Routes live in four blueprints named after the flow
they serve: capture (the button), admin (completing a record), manage (the
owner's screens) and exports (everything handed to somebody else). This file
wires them to shared state, the Ring client, the store, the Bedrock runner and
the in-memory latest-webhook table, and does nothing else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask, render_template, request

from . import timefmt
from .amendments import FIELD_LABEL, FIELD_LETTER
from .bedrock import BedrockRunner, build_runner
from .config import APP_VERSION, DEFAULT_DB_PATH
from .ring_client import build_client
from .routes_admin import admin_bp
from .routes_capture import capture_bp
from .routes_export import export_bp
from .routes_manage import manage_bp
from .store import IncidentStore


def create_app(
    db_path: Optional[str] = None,
    use_fixtures: bool = True,
    bedrock: Optional[BedrockRunner] = None,
) -> Flask:
    app = Flask(__name__)
    db_path = db_path or str(DEFAULT_DB_PATH)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app.config["STORE"] = IncidentStore(db_path)
    app.config["RING"] = build_client(use_fixtures=use_fixtures)
    # A stub runner can be handed in by a test or by INCIDENT_BOOK_BEDROCK=off,
    # and every drafting path behaves the same either way.
    app.config["BEDROCK"] = bedrock or build_runner()
    app.config["APP_VERSION"] = APP_VERSION
    # In-memory "latest webhook event per device": what the capture button
    # reaches for. Real Ring event history backs any lookup by timestamp;
    # this table is just the most recent thing that arrived over the webhook,
    # matching how a real kiosk would react to a just-happened motion event.
    app.config["LATEST_EVENT"] = {}

    _register_filters(app)
    _register_error_pages(app)
    app.register_blueprint(capture_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(manage_bp)
    app.register_blueprint(export_bp)
    return app


# What the reader can do next, per status. Without these every mistyped record
# id, and every refusal raised by `abort()`, dropped out of the dark book into
# Werkzeug's own "Not Found" in Times on bare white.
_ERROR_HEADINGS = {
    400: "That request could not be acted on",
    404: "There is nothing in the book under that",
    405: "That address does not answer that way",
    409: "That cannot be done to this record",
    500: "Something went wrong",
}

_ERROR_NEXT = {
    400: "Go back, change what is named above, and try it again.",
    404: "Check the link. A record id is the one printed at the top of the record.",
    405: "Check the link.",
    409: "The record is in a state that does not allow it. The reason is above.",
    500: "The book is unchanged. Nothing was written.",
}


def _register_error_pages(app: Flask) -> None:
    # Werkzeug's own 404 description is three sentences of boilerplate about
    # checking your spelling. `abort(404, "...")` from a route says something
    # useful; a bare `abort(404)` does not, so name the address instead.
    _BOILERPLATE = "The requested URL was not found on the server."

    def render_error(exc):
        status = getattr(exc, "code", 500) or 500
        detail = getattr(exc, "description", "") or ""
        if status == 404 and detail.startswith(_BOILERPLATE):
            detail = f"Nothing in this book answers at {request.path}."
        page = render_template(
            "error.html",
            heading=_ERROR_HEADINGS.get(status, _ERROR_HEADINGS[500]),
            detail=detail,
            next_step=_ERROR_NEXT.get(status, _ERROR_NEXT[500]),
            section="",
        )
        return page, status

    for status in _ERROR_HEADINGS:
        app.register_error_handler(status, render_error)


def _register_filters(app: Flask) -> None:
    """One formatter for every time on every screen, for the same reason the
    documents have one: two date formats in one product is how a reader stops
    believing either."""
    app.jinja_env.filters["canonical"] = timefmt.canonical
    app.jinja_env.filters["day"] = timefmt.day
    app.jinja_env.filters["clock"] = timefmt.clock
    app.jinja_env.filters["prose"] = timefmt.prose
    app.jinja_env.globals["window"] = timefmt.window
    app.jinja_env.globals["letter_for"] = lambda name: FIELD_LETTER.get(name, "")
    app.jinja_env.globals["label_for_field"] = lambda name: FIELD_LABEL.get(name, name)
    app.jinja_env.globals["app_version"] = APP_VERSION


if __name__ == "__main__":
    application = create_app()
    # debug=False: the Werkzeug debugger is an interactive console on a process
    # holding a five-year statutory record and its clips. `app.run` is the
    # development entry point and it is still the one somebody reaches for.
    application.run(debug=False, port=5057)
