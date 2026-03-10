"""
API REST — Contacts
  GET    /api/contacts/          liste (search, sort, page)
  POST   /api/contacts/          créer
  GET    /api/contacts/<id>      détail
  PUT    /api/contacts/<id>      modifier
  DELETE /api/contacts/<id>      supprimer
  DELETE /api/contacts/bulk      supprimer plusieurs
"""

import unicodedata
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app import db
from app.models import Contact, AuditLog

contacts_bp = Blueprint("contacts", __name__)


def _normalize(s: str) -> str:
    """Supprime les accents pour la recherche tolérante."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def _log(action: str, record_id: int = None, detail: str = "") -> None:
    entry = AuditLog(
        username=current_user.username,
        action=action,
        table_name="contacts",
        record_id=record_id,
        detail=detail,
        ip_address=request.remote_addr or "",
    )
    db.session.add(entry)


# ── Helpers ───────────────────────────────────────────────────────────────────

SORT_FIELDS = {
    "societe": Contact.societe,
    "nom":     Contact.nom,
    "prenom":  Contact.prenom,
    "email":   Contact.email,
    "fonction":Contact.fonction,
    "id":      Contact.id,
}


def _build_query(search: str, sort: str, direction: str):
    q = Contact.query
    if search:
        words = search.strip().split()
        for word in words:
            norm = _normalize(word)
            # Recherche multi-colonnes avec tolérance accents côté Python
            # Sur PostgreSQL on peut utiliser ILIKE ; on filtre après fetch si besoin.
            pattern = f"%{word}%"
            q = q.filter(
                or_(
                    Contact.societe.ilike(pattern),
                    Contact.nom.ilike(pattern),
                    Contact.prenom.ilike(pattern),
                    Contact.email.ilike(pattern),
                    Contact.fonction.ilike(pattern),
                    Contact.telephone.ilike(pattern),
                    Contact.notes.ilike(pattern),
                )
            )
    col = SORT_FIELDS.get(sort, Contact.societe)
    if direction == "desc":
        col = col.desc()
    q = q.order_by(col)
    return q


# ── Routes ────────────────────────────────────────────────────────────────────

@contacts_bp.route("/")
@login_required
def list_contacts():
    search    = request.args.get("q", "").strip()
    sort      = request.args.get("sort", "societe")
    direction = request.args.get("dir", "asc")
    page      = int(request.args.get("page", 1))
    per_page  = int(request.args.get("per_page", 500))

    q = _build_query(search, sort, direction)
    total = q.count()
    rows  = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        "total":   total,
        "page":    page,
        "results": [r.to_dict() for r in rows],
    })


@contacts_bp.route("/", methods=["POST"])
@login_required
def create_contact():
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    data = request.get_json(silent=True) or {}
    errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    c = Contact(
        societe    = data.get("societe",    "").strip(),
        nom        = data.get("nom",        "").strip(),
        prenom     = data.get("prenom",     "").strip(),
        fonction   = data.get("fonction",   "").strip(),
        email      = data.get("email",      "").strip(),
        telephone  = data.get("telephone",  "").strip(),
        telephone2 = data.get("telephone2", "").strip(),
        notes      = data.get("notes",      "").strip(),
        updated_by = current_user.username,
    )
    db.session.add(c)
    db.session.flush()
    _log("CREATE", c.id, f"{c.societe} / {c.nom} {c.prenom}")
    db.session.commit()
    return jsonify(c.to_dict()), 201


@contacts_bp.route("/<int:cid>")
@login_required
def get_contact(cid: int):
    c = db.get_or_404(Contact, cid)
    return jsonify(c.to_dict())


@contacts_bp.route("/<int:cid>", methods=["PUT"])
@login_required
def update_contact(cid: int):
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    c = db.get_or_404(Contact, cid)
    data = request.get_json(silent=True) or {}
    errors = _validate(data)
    if errors:
        return jsonify({"errors": errors}), 400

    c.societe    = data.get("societe",    c.societe).strip()
    c.nom        = data.get("nom",        c.nom).strip()
    c.prenom     = data.get("prenom",     c.prenom).strip()
    c.fonction   = data.get("fonction",   c.fonction).strip()
    c.email      = data.get("email",      c.email).strip()
    c.telephone  = data.get("telephone",  c.telephone).strip()
    c.telephone2 = data.get("telephone2", c.telephone2).strip()
    c.notes      = data.get("notes",      c.notes).strip()
    c.updated_by = current_user.username
    _log("UPDATE", c.id, f"{c.societe} / {c.nom} {c.prenom}")
    db.session.commit()
    return jsonify(c.to_dict())


@contacts_bp.route("/<int:cid>", methods=["DELETE"])
@login_required
def delete_contact(cid: int):
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    c = db.get_or_404(Contact, cid)
    _log("DELETE", c.id, f"{c.societe} / {c.nom} {c.prenom}")
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


@contacts_bp.route("/bulk", methods=["DELETE"])
@login_required
def bulk_delete():
    if not current_user.can_write:
        return jsonify({"error": "Droits insuffisants."}), 403

    ids = request.get_json(silent=True) or []
    if not ids:
        return jsonify({"error": "Aucun identifiant fourni."}), 400

    rows = Contact.query.filter(Contact.id.in_(ids)).all()
    for row in rows:
        _log("DELETE", row.id, f"{row.societe} / {row.nom} {row.prenom}")
        db.session.delete(row)
    db.session.commit()
    return jsonify({"deleted": len(rows)})


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(data: dict) -> list[str]:
    errors = []
    if not (data.get("societe") or "").strip():
        errors.append("La société est obligatoire.")
    if not (data.get("nom") or "").strip():
        errors.append("Le nom est obligatoire.")
    if not (data.get("prenom") or "").strip():
        errors.append("Le prénom est obligatoire.")
    email = (data.get("email") or "").strip()
    if email and "@" not in email:
        errors.append("L'email n'est pas valide.")
    return errors
