"""Everything this app hands to somebody else, served over HTTP.

Two documents per incident, because Labor Code 6401.9(d)(1)(B) makes
de-identification a duty on the log and not on the pack, and one document
trying to be both is the failure mode. Each is available as HTML and as PDF,
and each carries a machine-readable manifest. On top of those, the whole log
as CSV, because the obligation in (f)(5) and (f)(6) is over the book rather
than over one incident in it.
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, abort, current_app, jsonify

from .export import build_document, build_log_csv, build_violent_incident_log_entry
from .export_pdf import PdfUnavailable, render as render_pdf

export_bp = Blueprint("exports", __name__)


def _incident_or_404(incident_id: str):
    incident = current_app.config["STORE"].get_incident(incident_id)
    if incident is None:
        abort(404)
    return incident


def _document(incident_id: str, kind: str):
    store = current_app.config["STORE"]
    incident = _incident_or_404(incident_id)
    return build_document(
        kind,
        incident,
        clip_bytes=store.load_evidence(incident_id, "clip"),
        snapshot_bytes=store.load_evidence(incident_id, "snapshot"),
        premises=store.get_premises(incident.premises_id),
        device=store.get_device_registration(incident.device_id),
        draft=store.get_draft(incident_id),
        revisions=store.revisions(incident_id),
    )


@export_bp.get("/incidents/<incident_id>/export/log")
def export_log(incident_id: str):
    """The statute-shaped entry as JSON, de-identified."""
    store = current_app.config["STORE"]
    incident = _incident_or_404(incident_id)
    return jsonify(
        build_violent_incident_log_entry(
            incident, store.get_premises(incident.premises_id)
        )
    )


@export_bp.get("/incidents/<incident_id>/export/log.html")
def export_log_document(incident_id: str):
    html, _ = _document(incident_id, "log")
    return html


@export_bp.get("/incidents/<incident_id>/export/log.pdf")
def export_log_pdf(incident_id: str):
    return _pdf(incident_id, "log", "violent-incident-log")


@export_bp.get("/incidents/<incident_id>/export/pack")
def export_pack(incident_id: str):
    html, _ = _document(incident_id, "pack")
    return html


@export_bp.get("/incidents/<incident_id>/export/pack.pdf")
def export_pack_pdf(incident_id: str):
    return _pdf(incident_id, "pack", "evidence-pack")


@export_bp.get("/incidents/<incident_id>/export/pack.json")
def export_pack_manifest(incident_id: str):
    _, manifest = _document(incident_id, "pack")
    return jsonify(manifest)


@export_bp.get("/incidents/<incident_id>/export/manifest.sha256")
def export_manifest_file(incident_id: str):
    """The file the command printed on the document actually checks against."""
    _, manifest = _document(incident_id, "pack")
    body = manifest["manifest_sha256_file"]
    return Response(
        body,
        mimetype="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=manifest.sha256",
        },
    )


@export_bp.get("/export/log.csv")
def export_whole_log_csv():
    store = current_app.config["STORE"]
    incidents = store.list_incidents()
    sites = {p.premises_id: p for p in store.list_premises()}
    tz = next(iter(sites.values())).timezone_name if sites else ""
    body = build_log_csv(
        incidents,
        premises_by_id=sites,
        amendments_by_id={
            i.incident_id: store.revision_count(i.incident_id) for i in incidents
        },
        tz_name=tz,
    )
    return Response(
        body,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=violent-incident-log.csv"},
    )


@export_bp.get("/export/log.json")
def export_whole_log_json():
    """The same book as JSON, for an owner moving to another system. A
    product that traps a five-year statutory record is not one anybody should
    install."""
    store = current_app.config["STORE"]
    sites = {p.premises_id: p for p in store.list_premises()}
    entries = [
        build_violent_incident_log_entry(i, sites.get(i.premises_id))
        for i in store.list_incidents()
    ]
    return Response(
        json.dumps({"statute": "California Labor Code 6401.9(d)(2)", "entries": entries}, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=violent-incident-log.json"},
    )


def _pdf(incident_id: str, kind: str, stem: str):
    html, _ = _document(incident_id, kind)
    try:
        body = render_pdf(html)
    except PdfUnavailable as exc:
        # The HTML is the same document. Say which one this is rather than
        # returning a file that will not open.
        return Response(
            f"PDF rendering is not available on this machine: {exc}\n"
            "The same document is served as HTML at the .html or /pack address "
            "and prints from any browser.",
            status=503,
            mimetype="text/plain",
        )
    return Response(
        body,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={stem}-{incident_id}.pdf",
        },
    )
