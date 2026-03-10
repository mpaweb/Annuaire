"""
Scanner de doublons — contacts et ROC.
"""

import unicodedata
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import func
from app import db
from app.models import Contact, Roc, AuditLog

duplicates_bp = Blueprint("duplicates", __name__)


def _norm(s: str) -> str:
    if not s:
        return ""
    return unicodedata.normalize("NFD", s.strip().lower()).encode("ascii", "ignore").decode()


def _log(detail: str) -> None:
    db.session.add(AuditLog(
        username=current_user.username,
        action="DEDUP",
        table_name="duplicates",
        detail=detail,
        ip_address=request.remote_addr or "",
    ))


# ── Contacts ──────────────────────────────────────────────────────────────────

@duplicates_bp.route("/contacts")
@login_required
def scan_contacts():
    """
    Retourne les groupes de doublons détectés dans les contacts.
    Mode : exact (email) ou similar (nom+societe normalisés).
    """
    mode = request.args.get("mode", "similar")
    all_contacts = Contact.query.all()

    groups = []
    seen_ids: set[int] = set()

    if mode == "email":
        # Grouper par email identique (non vide)
        from collections import defaultdict
        by_email: dict[str, list] = defaultdict(list)
        for c in all_contacts:
            key = _norm(c.email)
            if key:
                by_email[key].append(c)
        for key, group in by_email.items():
            if len(group) > 1:
                ids = {c.id for c in group}
                if not ids & seen_ids:
                    seen_ids |= ids
                    groups.append({
                        "key":     key,
                        "reason":  "Email identique",
                        "records": [c.to_dict() for c in group],
                    })
    else:
        # Grouper par (nom normalisé + société normalisée)
        from collections import defaultdict
        by_key: dict[str, list] = defaultdict(list)
        for c in all_contacts:
            key = _norm(c.nom) + "|" + _norm(c.societe)
            if _norm(c.nom):
                by_key[key].append(c)
        for key, group in by_key.items():
            if len(group) > 1:
                ids = {c.id for c in group}
                if not ids & seen_ids:
                    seen_ids |= ids
                    groups.append({
                        "key":     key,
                        "reason":  "Nom + Société similaires",
                        "records": [c.to_dict() for c in group],
                    })

    return jsonify({"groups": groups, "total_groups": len(groups)})


@duplicates_bp.route("/contacts/merge", methods=["POST"])
@login_required
def merge_contacts():
    """
    Conserve keep_id, fusionne les champs manquants depuis les autres,
    supprime les doublons.
    """
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    data    = request.get_json(silent=True) or {}
    keep_id = data.get("keep_id")
    del_ids = data.get("delete_ids", [])

    if not keep_id or not del_ids:
        return jsonify({"error": "keep_id et delete_ids sont requis."}), 400

    keep = db.get_or_404(Contact, keep_id)
    deleted = 0
    for did in del_ids:
        dup = db.session.get(Contact, did)
        if not dup or dup.id == keep_id:
            continue
        # Fusionner les champs vides
        for field in ("societe", "nom", "prenom", "fonction",
                      "email", "telephone", "telephone2"):
            if not getattr(keep, field) and getattr(dup, field):
                setattr(keep, field, getattr(dup, field))
        if dup.notes:
            keep.notes = (keep.notes + " | " + dup.notes).strip(" |") if keep.notes else dup.notes
        db.session.delete(dup)
        deleted += 1

    keep.updated_by = current_user.username
    _log(f"Fusion contacts : keep={keep_id}, supprimés={del_ids}")
    db.session.commit()
    return jsonify({"ok": True, "deleted": deleted, "record": keep.to_dict()})


# ── ROC ───────────────────────────────────────────────────────────────────────

@duplicates_bp.route("/rocs")
@login_required
def scan_rocs():
    all_rocs = Roc.query.all()
    from collections import defaultdict
    by_key: dict[str, list] = defaultdict(list)
    for r in all_rocs:
        key = _norm(r.roc)
        if key:
            by_key[key].append(r)

    groups = []
    for key, group in by_key.items():
        if len(group) > 1:
            groups.append({
                "key":     key,
                "reason":  "ROC identique",
                "records": [r.to_dict() for r in group],
            })
    return jsonify({"groups": groups, "total_groups": len(groups)})


@duplicates_bp.route("/rocs/merge", methods=["POST"])
@login_required
def merge_rocs():
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    data    = request.get_json(silent=True) or {}
    keep_id = data.get("keep_id")
    del_ids = data.get("delete_ids", [])

    if not keep_id or not del_ids:
        return jsonify({"error": "keep_id et delete_ids sont requis."}), 400

    keep = db.get_or_404(Roc, keep_id)
    deleted = 0
    for did in del_ids:
        dup = db.session.get(Roc, did)
        if not dup or dup.id == keep_id:
            continue
        for field in ("nom_client", "roc", "trinity", "infogerance",
                      "astreinte", "type_contrat", "date_anniversaire_contrat"):
            if not getattr(keep, field) and getattr(dup, field):
                setattr(keep, field, getattr(dup, field))
        db.session.delete(dup)
        deleted += 1

    keep.updated_by = current_user.username
    _log(f"Fusion ROC : keep={keep_id}, supprimés={del_ids}")
    db.session.commit()
    return jsonify({"ok": True, "deleted": deleted, "record": keep.to_dict()})
