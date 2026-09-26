"""The three screens that belong to whoever owns the shop rather than to
whoever is on the floor: settings, the periodic review, and retention.

These are the second surface. The person who presses the button is not the
person who has to hand a Cal/OSHA inspector five years of records, and until
now this app had nothing at all for the second one.
"""

from __future__ import annotations

import json
import time

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from . import retention, review
from .premises import DeviceRegistration, Premises
from .timefmt import COMMON_ZONES

manage_bp = Blueprint("manage", __name__)
REVIEWS_KEY = "plan_reviews"


@manage_bp.get("/settings")
def settings():
    return _settings_page()


def _settings_page(error: str = "", status: int = 200):
    store = current_app.config["STORE"]
    ring = current_app.config["RING"]
    devices = ring.list_devices()
    page = render_template(
        "settings.html",
        sites=store.list_premises(),
        devices=[
            (d, store.get_device_registration(d.device_id) or DeviceRegistration(d.device_id))
            for d in devices
        ],
        zones=COMMON_ZONES,
        bedrock=current_app.config["BEDROCK"],
        error=error,
        form=request.form,
    )
    return (page, status) if status != 200 else page


@manage_bp.post("/settings/premises")
def save_premises():
    """Save a premises, or refuse.

    An empty submit used to mint a premises with a fresh id and no name, which
    then sat in the Editing dropdown forever reading "Not recorded" and could
    not be removed, because nothing in this app deletes a premises. The button
    sits directly under an empty form on the first screen an owner opens, so
    one stray press put junk into the install permanently. A record with no
    name is not a premises; refusing is the only correct answer.
    """
    store = current_app.config["STORE"]
    name = request.form.get("name", "").strip()
    if not name:
        return _settings_page(
            "A premises needs a name before it can be saved. Nothing was "
            "written. Type the name the shop trades under and press the "
            "button again.",
            status=400,
        )
    premises_id = request.form.get("premises_id") or Premises.new_id()
    existing = store.get_premises(premises_id)
    record = Premises(
        premises_id=premises_id,
        name=name,
        legal_entity=request.form.get("legal_entity", "").strip(),
        address_line1=request.form.get("address_line1", "").strip(),
        address_line2=request.form.get("address_line2", "").strip(),
        city=request.form.get("city", "").strip(),
        state=request.form.get("state", "").strip(),
        postal_code=request.form.get("postal_code", "").strip(),
        establishment_id=request.form.get("establishment_id", "").strip(),
        timezone_name=request.form.get("timezone_name", "").strip(),
        revision=(existing.revision + 1) if existing else 1,
        created_at=existing.created_at if existing else int(time.time() * 1000),
    )
    store.save_premises(record)
    return redirect(url_for("manage.settings"))


@manage_bp.post("/settings/device")
def save_device():
    store = current_app.config["STORE"]
    device_id = request.form.get("device_id", "")
    if not device_id:
        abort(400, "a device id is required")
    store.save_device_registration(
        DeviceRegistration(
            device_id=device_id,
            premises_id=request.form.get("premises_id", ""),
            covers=request.form.get("covers", "").strip(),
            does_not_cover=request.form.get("does_not_cover", "").strip(),
        )
    )
    return redirect(url_for("manage.settings"))


@manage_bp.get("/review")
def plan_review():
    return _review_page()


def _review_page(error: str = "", status: int = 200):
    store = current_app.config["STORE"]
    incidents = store.list_incidents()
    reviews = _reviews(store)
    last_review_at = reviews[-1]["at"] if reviews else None
    last_incident_at = max((i.occurred_at for i in incidents), default=None)
    site = next(iter(store.list_premises()), None)
    page = render_template(
        "review.html",
        review=review.build(incidents),
        reviews=list(reversed(reviews)),
        due_note=review.due_note(last_review_at, last_incident_at),
        tz=site.timezone_name if site else "",
        error=error,
        form=request.form,
    )
    return (page, status) if status != 200 else page


@manage_bp.post("/review/record")
def record_review():
    """Write down that the review happened. 6401.9(c)(2)(L) asks for one at
    least annually, when a deficiency becomes apparent, and after every
    incident, and an employer who did the review but cannot show it is in the
    same position as one who did not."""
    store = current_app.config["STORE"]
    by = request.form.get("by", "").strip()
    note = request.form.get("note", "").strip()
    # An empty submit used to be accepted, write a permanent row reading "Not
    # recorded / No note was written", and flip the compliance line at the top
    # of this page to "No review is owed". A duty discharged by an empty click
    # is the premise of this app failing, so the two fields that make the row
    # worth showing an inspector are required and nothing is written without
    # them.
    missing = [
        label
        for label, value in (("who did the review", by), ("what came of it", note))
        if not value
    ]
    if missing:
        return _review_page(
            "Nothing was recorded. A review the employer can show an inspector "
            "needs " + " and ".join(missing) + ". Fill "
            + ("them" if len(missing) > 1 else "that")
            + " in and press the button again.",
            status=400,
        )
    reviews = _reviews(store)
    reviews.append(
        {
            "at": int(time.time() * 1000),
            "by": by,
            "title": request.form.get("title", "").strip(),
            "note": note,
        }
    )
    store.set_setting(REVIEWS_KEY, json.dumps(reviews))
    return redirect(url_for("manage.plan_review"))


@manage_bp.get("/retention")
def retention_screen():
    store = current_app.config["STORE"]
    site = next(iter(store.list_premises()), None)
    return render_template(
        "retention.html",
        position=retention.position(store),
        eligible=retention.eligible_for_purge(store),
        ledger=store.retention_events(),
        tz=site.timezone_name if site else "",
    )


@manage_bp.post("/retention/purge")
def purge():
    store = current_app.config["STORE"]
    actor = request.form.get("by", "").strip()
    if not actor:
        abort(400, "a purge has to be attributable to a person")
    incident_id = request.form.get("incident_id", "")
    incident = store.get_incident(incident_id)
    if incident is None:
        abort(404)
    try:
        retention.purge(store, incident, actor_name=actor)
    except retention.RetainedTooRecently as exc:
        abort(409, str(exc))
    return redirect(url_for("manage.retention_screen"))


def _reviews(store) -> list[dict]:
    return json.loads(store.get_setting(REVIEWS_KEY, "[]"))
