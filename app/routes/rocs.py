"""
API REST — ROC (même structure que contacts)
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from app import db
from app.models import Roc, AuditLog

rocs_bp = Blueprint("rocs", __name__)


def _log(action: str, record_id: int = None, detail: str = "") -> None:
    entry = AuditLog(
        username=current_user.username,
        action=action,
        table_name="rocs",
        record_id=record_id,
        detail=detail,
        ip_address=request.remote_addr or "",
    )
    db.session.add(entry)


SORT_FIELDS = {
    "nom_client":   Roc.nom_client,
    "roc":          Roc.roc,
    "trinity":      Roc.trinity,
    "type_contrat": Roc.type_contrat,
    "id":           Roc.id,
}


@rocs_bp.route("/")
@login_required
def list_rocs():
    search    = request.args.get("q", "").strip()
    sort      = request.args.get("sort", "nom_client")
    direction = request.args.get("dir", "asc")
    page      = int(request.args.get("page", 1))
    per_page  = int(request.args.get("per_page", 500))

    q = Roc.query
    if search:
        for word in search.strip().split():
            pattern = f"%{word}%"
            q = q.filter(
                or_(
                    Roc.nom_client.ilike(pattern),
                    Roc.roc.ilike(pattern),
                    Roc.trinity.ilike(pattern),
                    Roc.infogerance.ilike(pattern),
                    Roc.type_contrat.ilike(pattern),
                )
            )
    col = SORT_FIELDS.get(sort, Roc.nom_client)
    if direction == "desc":
        col = col.desc()
    q = q.order_by(col)

    total = q.count()
    rows  = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({"total": total, "page": page, "results": [r.to_dict() for r in rows]})


@rocs_bp.route("/", methods=["POST"])
@login_required
def create_roc():
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    data = request.get_json(silent=True) or {}
    errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    r = Roc(
        nom_client               = data.get("nom_client", "").strip(),
        roc                      = data.get("roc", "").strip(),
        trinity                  = data.get("trinity", "").strip(),
        infogerance              = data.get("infogerance", "").strip(),
        astreinte                = data.get("astreinte", "").strip(),
        type_contrat             = data.get("type_contrat", "").strip(),
        date_anniversaire_contrat= data.get("date_anniversaire_contrat", "").strip(),
        updated_by               = current_user.username,
    )
    db.session.add(r)
    db.session.flush()
    _log("CREATE", r.id, f"{r.nom_client} / {r.roc}")
    db.session.commit()
    return jsonify(r.to_dict()), 201


@rocs_bp.route("/<int:rid>")
@login_required
def get_roc(rid: int):
    r = db.get_or_404(Roc, rid)
    return jsonify(r.to_dict())


@rocs_bp.route("/<int:rid>", methods=["PUT"])
@login_required
def update_roc(rid: int):
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    r = db.get_or_404(Roc, rid)
    data = request.get_json(silent=True) or {}
    errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    r.nom_client               = data.get("nom_client",               r.nom_client).strip()
    r.roc                      = data.get("roc",                      r.roc).strip()
    r.trinity                  = data.get("trinity",                  r.trinity).strip()
    r.infogerance              = data.get("infogerance",              r.infogerance).strip()
    r.astreinte                = data.get("astreinte",                r.astreinte).strip()
    r.type_contrat             = data.get("type_contrat",             r.type_contrat).strip()
    r.date_anniversaire_contrat= data.get("date_anniversaire_contrat",r.date_anniversaire_contrat).strip()
    r.updated_by               = current_user.username
    _log("UPDATE", r.id, f"{r.nom_client} / {r.roc}")
    db.session.commit()
    return jsonify(r.to_dict())


@rocs_bp.route("/<int:rid>", methods=["DELETE"])
@login_required
def delete_roc(rid: int):
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    r = db.get_or_404(Roc, rid)
    _log("DELETE", r.id, f"{r.nom_client} / {r.roc}")
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})


@rocs_bp.route("/bulk", methods=["DELETE"])
@login_required
def bulk_delete():
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    ids = request.get_json(silent=True) or []
    rows = Roc.query.filter(Roc.id.in_(ids)).all()
    for row in rows:
        _log("DELETE", row.id, f"{row.nom_client} / {row.roc}")
        db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": len(rows)})


def _validate(data: dict) -> list[str]:
    errors = []
    if not (data.get("nom_client") or "").strip():
        errors.append("Le nom client est obligatoire.")
    if not (data.get("roc") or "").strip():
        errors.append("Le ROC est obligatoire.")
    return errors
