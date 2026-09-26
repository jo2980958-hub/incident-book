"""The completion stage: reached later, calmly, from the incident list, never
forced on the person who just pressed the button.

Three things happen on this path and they happen in this order, always. A
member of staff may ask the model for a first draft of the two free-text
fields. They read it, change it or replace it. They press save, and the save
is what files it, with their name against it and a row in the amendment trail
saying what changed.
"""

from __future__ import annotations

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

from .amendments import diff, history_by_field, revision_number
from .drafting import draft_narrative
from .premises import resolve
from .search import STATUSES, Query
from .statute import (
    CIRCUMSTANCE_OPTIONS,
    INCIDENT_TYPES,
    LOCATION_CLASSES,
    PERPETRATOR_CLASSES,
    VIOLENCE_TYPES,
)

admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/incidents")
def incident_list():
    store = current_app.config["STORE"]
    query = _query_from_request()
    incidents = store.list_incidents(query)
    sites = {p.premises_id: p for p in store.list_premises()}
    return render_template(
        "incident_list.html",
        incidents=incidents,
        query=query,
        counts=store.counts(),
        sites=sites,
        statuses=STATUSES,
        violence_types=VIOLENCE_TYPES,
        incident_types=INCIDENT_TYPES,
        circumstance_options=CIRCUMSTANCE_OPTIONS,
        amendments={i.incident_id: store.revision_count(i.incident_id) for i in incidents},
    )


@admin_bp.get("/incidents/<incident_id>/edit")
def edit_form(incident_id: str):
    store = current_app.config["STORE"]
    incident = store.get_incident(incident_id)
    if incident is None:
        abort(404)
    revisions = store.revisions(incident_id)
    runner = current_app.config["BEDROCK"]
    return render_template(
        "incident_form.html",
        incident=incident,
        premises=resolve(store.get_premises(incident.premises_id)),
        sites=store.list_premises(),
        draft=store.get_draft(incident_id),
        history=history_by_field(revisions),
        revision=revision_number(revisions),
        model_name=runner.model_id,
        violence_types=VIOLENCE_TYPES,
        perpetrator_classes=PERPETRATOR_CLASSES,
        circumstance_options=CIRCUMSTANCE_OPTIONS,
        location_classes=LOCATION_CLASSES,
        incident_types=INCIDENT_TYPES,
        missing=incident.missing_statute_fields(),
    )


@admin_bp.post("/incidents/<incident_id>/draft")
def request_draft(incident_id: str):
    """Ask Bedrock for a first version of (C) and (H).

    Nothing here writes a statutory field. The result is a proposal stored
    beside the incident, and the form opens with it in the boxes for a human
    to change. If Bedrock cannot be reached, the proposal is the staff
    member's own words, unchanged, so the only thing lost is convenience.
    """
    store = current_app.config["STORE"]
    incident = store.get_incident(incident_id)
    if incident is None:
        abort(404)
    if incident.is_purged:
        abort(409, "this record was purged after its five years and cannot be drafted")
    words = request.form.get("words", "")
    site = resolve(store.get_premises(incident.premises_id))
    draft = draft_narrative(
        current_app.config["BEDROCK"], incident, words, site.one_line()
    )
    store.save_draft(draft)
    return redirect(url_for("admin.edit_form", incident_id=incident_id) + "#draft")


@admin_bp.post("/incidents/<incident_id>/edit")
def save_form(incident_id: str):
    store = current_app.config["STORE"]
    incident = store.get_incident(incident_id)
    if incident is None:
        abort(404)
    if incident.is_purged:
        abort(409, "this record was purged after its five years and cannot be edited")

    before = store.get_incident(incident_id)  # a separate instance to diff against
    incident.premises_id = request.form.get("premises_id", incident.premises_id)
    incident.violence_types = request.form.getlist("violence_types")
    incident.description = request.form.get("description", "")
    incident.perpetrator_class = request.form.get("perpetrator_class") or None
    incident.circumstances = request.form.getlist("circumstances")
    incident.location_class = request.form.get("location_class") or None
    incident.location_detail = request.form.get("location_detail", "")
    incident.incident_types = request.form.getlist("incident_types")
    incident.consequences_response = request.form.get("consequences_response", "")
    incident.consequences_actions = request.form.get("consequences_actions", "")
    incident.completed_by = request.form.get("completed_by", "").strip()
    incident.completed_by_title = request.form.get("completed_by_title", "").strip()

    was_complete = incident.completed
    incident.completed = incident.is_statute_complete()
    if incident.completed and not was_complete:
        incident.completed_at = int(time.time() * 1000)

    changes = diff(before, incident)
    store.save_incident(incident)
    if changes:
        store.add_revision(
            incident_id,
            kind="amended" if was_complete else "completed",
            changes=changes,
            actor_name=incident.completed_by,
            actor_title=incident.completed_by_title,
            note=_draft_note(store, incident),
        )
    return redirect(url_for("admin.incident_list"))


def _draft_note(store, incident) -> str:
    """One sentence on the trail row saying what the software drafted and
    whether the person changed it. This is the answer to the question a judge
    asks about the model: nothing filed unread, and the record says so."""
    draft = store.get_draft(incident.incident_id)
    if draft is None or not draft.came_from_a_model:
        return ""
    unchanged = [
        letter
        for letter, filed, proposed in (
            ("C", incident.description, draft.description),
            ("H", incident.consequences_response, draft.consequences_response),
        )
        if proposed and filed.strip() == proposed.strip()
    ]
    edited = [
        letter
        for letter, filed, proposed in (
            ("C", incident.description, draft.description),
            ("H", incident.consequences_response, draft.consequences_response),
        )
        if proposed and filed.strip() != proposed.strip()
    ]
    parts = [f"Software drafted a first version using {draft.model_id}."]
    if edited:
        parts.append(f"Field(s) {', '.join(edited)} were edited by the completer.")
    if unchanged:
        parts.append(f"Field(s) {', '.join(unchanged)} were accepted unchanged.")
    return " ".join(parts)


def _query_from_request() -> Query:
    args = request.args
    return Query(
        text=args.get("text", ""),
        premises_id=args.get("premises_id", ""),
        device_id=args.get("device_id", ""),
        status=args.get("status", "any"),
        incident_type=args.get("incident_type", ""),
        violence_type=args.get("violence_type", ""),
        circumstance=args.get("circumstance", ""),
        date_from=args.get("date_from", ""),
        date_to=args.get("date_to", ""),
    )
