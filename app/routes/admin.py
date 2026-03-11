"""
Administration : utilisateurs, sauvegardes, logs, thème, logo.
"""

import io
import json
import base64
import os
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required, current_user
from app import db
from app.models import User, Contact, Roc, AuditLog, Backup, AppSetting

admin_bp = Blueprint("admin", __name__)

ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/gif", "image/svg+xml", "image/webp"}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 Mo


def _require_admin():
    if not current_user.is_admin:
        return jsonify({"error": "Accès réservé aux administrateurs."}), 403
    return None


def _log(action: str, detail: str = "") -> None:
    db.session.add(AuditLog(
        username=current_user.username,
        action=action,
        table_name="admin",
        detail=detail,
        ip_address=request.remote_addr or "",
    ))


# ══════════════════════════════════════════════════════════════════════════════
# UTILISATEURS
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/users")
@login_required
def list_users():
    err = _require_admin()
    if err:
        return err
    return jsonify([u.to_dict() for u in User.query.order_by(User.username).all()])


@admin_bp.route("/users", methods=["POST"])
@login_required
def create_user():
    err = _require_admin()
    if err:
        return err

    data      = request.get_json(silent=True) or {}
    username  = (data.get("username")  or "").strip()
    email     = (data.get("email")     or "").strip()
    password  = (data.get("password")  or "").strip()
    role      = (data.get("role")      or "viewer").strip()
    full_name = (data.get("full_name") or "").strip()

    if not username or not email or not password:
        return jsonify({"error": "username, email et password sont requis."}), 400
    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Rôle invalide (admin/editor/viewer)."}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": f"Le nom d'utilisateur '{username}' est déjà pris."}), 409
    if len(password) < 8:
        return jsonify({"error": "Le mot de passe doit faire au moins 8 caractères."}), 400

    u = User(username=username, email=email, role=role, full_name=full_name)
    u.set_password(password)
    db.session.add(u)
    _log("CREATE_USER", f"Création de {username} ({role})")
    db.session.commit()
    return jsonify(u.to_dict()), 201


@admin_bp.route("/users/<int:uid>", methods=["PUT"])
@login_required
def update_user(uid: int):
    err = _require_admin()
    if err:
        return err

    u    = db.get_or_404(User, uid)
    data = request.get_json(silent=True) or {}

    if "role" in data:
        if data["role"] not in ("admin", "editor", "viewer"):
            return jsonify({"error": "Rôle invalide."}), 400
        u.role = data["role"]
    if "full_name" in data:
        u.full_name = data["full_name"].strip()
    if "email" in data:
        u.email = data["email"].strip()
    if "active" in data:
        u.active = bool(data["active"])
    if "password" in data:
        pw = data["password"].strip()
        if pw:
            if len(pw) < 8:
                return jsonify({"error": "Mot de passe trop court (min 8 cars)."}), 400
            u.set_password(pw)

    _log("UPDATE_USER", f"Modification de {u.username}")
    db.session.commit()
    return jsonify(u.to_dict())


@admin_bp.route("/users/<int:uid>", methods=["DELETE"])
@login_required
def delete_user(uid: int):
    err = _require_admin()
    if err:
        return err
    if uid == current_user.id:
        return jsonify({"error": "Impossible de supprimer votre propre compte."}), 400

    u = db.get_or_404(User, uid)
    _log("DELETE_USER", f"Suppression de {u.username}")
    db.session.delete(u)
    db.session.commit()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# THÈME UTILISATEUR
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/theme", methods=["POST"])
@login_required
def set_theme():
    data  = request.get_json(silent=True) or {}
    theme = (data.get("theme") or "system").strip()
    if theme not in ("system", "light", "dark"):
        return jsonify({"error": "Thème invalide (system/light/dark)."}), 400
    current_user.theme = theme
    db.session.commit()
    return jsonify({"ok": True, "theme": theme})


# ══════════════════════════════════════════════════════════════════════════════
# LOGO APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/logo")
def get_logo():
    """Retourne le logo en base64 (public, pas besoin d'auth pour l'afficher)."""
    logo_b64  = AppSetting.get("logo_b64",   "")
    logo_mime = AppSetting.get("logo_mime",  "")
    if not logo_b64:
        return jsonify({"logo": None})
    return jsonify({"logo": f"data:{logo_mime};base64,{logo_b64}"})


@admin_bp.route("/logo", methods=["POST"])
@login_required
def upload_logo():
    err = _require_admin()
    if err:
        return err

    if "logo" not in request.files:
        return jsonify({"error": "Aucun fichier reçu."}), 400

    f    = request.files["logo"]
    mime = f.mimetype or ""
    if mime not in ALLOWED_LOGO_TYPES:
        return jsonify({"error": "Format non supporté. Utilisez PNG, JPG, GIF, SVG ou WEBP."}), 400

    data = f.read()
    if len(data) > MAX_LOGO_SIZE:
        return jsonify({"error": "Fichier trop volumineux (max 2 Mo)."}), 400

    b64 = base64.b64encode(data).decode("ascii")
    AppSetting.set("logo_b64",  b64)
    AppSetting.set("logo_mime", mime)
    _log("UPLOAD_LOGO", f"Logo mis à jour ({mime}, {len(data)//1024} Ko)")
    return jsonify({"ok": True, "logo": f"data:{mime};base64,{b64}"})


@admin_bp.route("/logo", methods=["DELETE"])
@login_required
def delete_logo():
    err = _require_admin()
    if err:
        return err
    AppSetting.set("logo_b64",  "")
    AppSetting.set("logo_mime", "")
    _log("DELETE_LOGO", "Logo supprimé")
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# STATISTIQUES
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/stats")
@login_required
def stats():
    last = Backup.query.order_by(Backup.created_at.desc()).first()
    return jsonify({
        "contacts":     Contact.query.count(),
        "rocs":         Roc.query.count(),
        "users":        User.query.count(),
        "users_active": User.query.filter_by(active=True).count(),
        "last_backup":  last.created_at.strftime("%d/%m/%Y à %H:%M") if last else "Jamais",
        "nb_backups":   Backup.query.count(),
    })


# ══════════════════════════════════════════════════════════════════════════════
# SAUVEGARDES
# ══════════════════════════════════════════════════════════════════════════════

def _make_backup_data() -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": current_user.username,
        "contacts":    [c.to_dict() for c in Contact.query.all()],
        "rocs":        [r.to_dict() for r in Roc.query.all()],
    }


@admin_bp.route("/backups")
@login_required
def list_backups():
    err = _require_admin()
    if err:
        return err
    rows = Backup.query.order_by(Backup.created_at.desc()).limit(50).all()
    return jsonify([b.to_dict() for b in rows])


@admin_bp.route("/backups", methods=["POST"])
@login_required
def create_backup():
    err = _require_admin()
    if err:
        return err

    kind = (request.get_json(silent=True) or {}).get("kind", "manual")
    data = _make_backup_data()
    js   = json.dumps(data, ensure_ascii=False)
    fname = f"annuaire_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{kind}.json"

    bk = Backup(
        filename    = fname,
        created_by  = current_user.username,
        kind        = kind,
        nb_contacts = len(data["contacts"]),
        nb_rocs     = len(data["rocs"]),
        data_json   = js,
    )
    db.session.add(bk)
    _log("BACKUP", f"{kind} — {len(data['contacts'])} contacts / {len(data['rocs'])} ROC")
    db.session.commit()

    # Garder seulement les 30 dernières sauvegardes automatiques
    if kind == "auto":
        old = Backup.query.filter_by(kind="auto")\
                    .order_by(Backup.created_at.desc())\
                    .offset(30).all()
        for o in old:
            db.session.delete(o)
        db.session.commit()

    return jsonify(bk.to_dict()), 201


@admin_bp.route("/backups/<int:bid>/download")
@login_required
def download_backup(bid: int):
    err = _require_admin()
    if err:
        return err
    bk  = db.get_or_404(Backup, bid)
    buf = io.BytesIO(bk.data_json.encode("utf-8"))
    return send_file(buf, mimetype="application/json",
                     as_attachment=True, download_name=bk.filename)


@admin_bp.route("/backups/<int:bid>/restore", methods=["POST"])
@login_required
def restore_backup(bid: int):
    err = _require_admin()
    if err:
        return err

    bk   = db.get_or_404(Backup, bid)
    try:
        data = json.loads(bk.data_json)
    except (json.JSONDecodeError, Exception) as e:
        return jsonify({"error": f"Fichier de sauvegarde corrompu : {e}"}), 400

    contacts_data = data.get("contacts", [])
    rocs_data     = data.get("rocs",     [])

    try:
        # Créer une sauvegarde de sécurité avant restauration
        current_data = _make_backup_data()
        safety = Backup(
            filename    = f"annuaire_pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            created_by  = current_user.username,
            kind        = "auto",
            nb_contacts = len(current_data["contacts"]),
            nb_rocs     = len(current_data["rocs"]),
            data_json   = json.dumps(current_data, ensure_ascii=False),
        )
        db.session.add(safety)
        db.session.flush()

        # Supprimer les données existantes (synchronize_session=False évite les conflits)
        Contact.query.delete(synchronize_session=False)
        Roc.query.delete(synchronize_session=False)
        db.session.flush()

        # Réinsérer les contacts
        for c in contacts_data:
            db.session.add(Contact(
                societe    = c.get("societe",    "") or "",
                nom        = c.get("nom",        "") or "",
                prenom     = c.get("prenom",     "") or "",
                fonction   = c.get("fonction",   "") or "",
                email      = c.get("email",      "") or "",
                telephone  = c.get("telephone",  "") or "",
                telephone2 = c.get("telephone2", "") or "",
                notes      = c.get("notes",      "") or "",
                updated_by = "restauration",
            ))

        # Réinsérer les ROC
        for r in rocs_data:
            db.session.add(Roc(
                nom_client                = r.get("nom_client",               "") or "",
                roc                       = r.get("roc",                      "") or "",
                trinity                   = r.get("trinity",                  "") or "",
                infogerance               = r.get("infogerance",              "") or "",
                astreinte                 = r.get("astreinte",                "") or "",
                type_contrat              = r.get("type_contrat",             "") or "",
                date_anniversaire_contrat = r.get("date_anniversaire_contrat","") or "",
                updated_by                = "restauration",
            ))

        _log("RESTORE", f"Restauration de {bk.filename} ({len(contacts_data)}C / {len(rocs_data)}R)")
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Erreur lors de la restauration : {str(e)}"}), 500

    return jsonify({
        "ok":          True,
        "nb_contacts": len(contacts_data),
        "nb_rocs":     len(rocs_data),
    })


@admin_bp.route("/backups/<int:bid>", methods=["DELETE"])
@login_required
def delete_backup(bid: int):
    err = _require_admin()
    if err:
        return err
    bk = db.get_or_404(Backup, bid)
    _log("DELETE_BACKUP", f"Suppression de {bk.filename}")
    db.session.delete(bk)
    db.session.commit()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════════════
# LOGS D'AUDIT
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/logs")
@login_required
def audit_logs():
    err = _require_admin()
    if err:
        return err

    page     = int(request.args.get("page",     1))
    per_page = int(request.args.get("per_page", 100))
    level    = request.args.get("level", "")
    search   = request.args.get("q",     "").strip()

    q = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if level:
        q = q.filter(AuditLog.action == level)
    if search:
        q = q.filter(
            AuditLog.detail.ilike(f"%{search}%") |
            AuditLog.username.ilike(f"%{search}%")
        )

    total = q.count()
    rows  = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({"total": total, "page": page, "results": [r.to_dict() for r in rows]})


@admin_bp.route("/logs/purge", methods=["POST"])
@login_required
def purge_logs():
    err = _require_admin()
    if err:
        return err
    n = AuditLog.query.delete()
    db.session.add(AuditLog(
        username=current_user.username,
        action="PURGE_LOGS",
        table_name="audit_logs",
        detail=f"{n} entrées supprimées",
        ip_address=request.remote_addr or "",
    ))
    db.session.commit()
    return jsonify({"ok": True, "deleted": n})


# ══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC & CONFIGURATION BASE DE DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

@admin_bp.route("/db/diagnostic")
@login_required
def db_diagnostic():
    err = _require_admin()
    if err:
        return err

    from sqlalchemy import text, inspect
    import os

    engine     = db.engine
    db_url     = str(engine.url)
    is_sqlite  = "sqlite" in db_url
    is_pg      = "postgresql" in db_url

    # Taille de la base
    db_size = "N/A"
    try:
        if is_sqlite:
            # Extraire le chemin du fichier SQLite
            db_path = db_url.replace("sqlite:///", "")
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.getcwd(), "instance", db_path.lstrip("/"))
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                db_size = f"{size_bytes / 1024:.1f} Ko" if size_bytes < 1048576 else f"{size_bytes / 1048576:.2f} Mo"
        elif is_pg:
            with db.engine.connect() as conn:
                result = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
                db_size = result or "N/A"
    except Exception:
        pass

    # Compter les lignes par table
    tables_info = []
    for model, name in [(Contact, "contacts"), (Roc, "rocs"), (User, "users"),
                        (AuditLog, "audit_logs"), (Backup, "backups")]:
        try:
            count = db.session.query(model).count()
            tables_info.append({"name": name, "rows": count})
        except Exception:
            tables_info.append({"name": name, "rows": "?"})

    # Vérifications
    checks = []

    # Contacts sans email
    try:
        n = Contact.query.filter((Contact.email == None) | (Contact.email == "")).count()
        checks.append({"label": "Contacts sans email", "value": str(n),
                        "status": "warning" if n > 0 else "ok"})
    except Exception:
        pass

    # Contacts sans société
    try:
        n = Contact.query.filter((Contact.societe == None) | (Contact.societe == "")).count()
        checks.append({"label": "Contacts sans société", "value": str(n),
                        "status": "warning" if n > 0 else "ok"})
    except Exception:
        pass

    # ROC sans nom client
    try:
        n = Roc.query.filter((Roc.nom_client == None) | (Roc.nom_client == "")).count()
        checks.append({"label": "ROC sans nom client", "value": str(n),
                        "status": "warning" if n > 0 else "ok"})
    except Exception:
        pass

    # Utilisateurs inactifs
    try:
        n = User.query.filter_by(active=False).count()
        checks.append({"label": "Utilisateurs inactifs", "value": str(n),
                        "status": "warning" if n > 0 else "ok"})
    except Exception:
        pass

    # Connexion DB
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks.append({"label": "Connexion base de données", "value": "OK", "status": "ok"})
    except Exception as e:
        checks.append({"label": "Connexion base de données", "value": str(e), "status": "error"})

    overall = "error" if any(c["status"] == "error" for c in checks) else \
              "warning" if any(c["status"] == "warning" for c in checks) else "ok"
    status_msg = {"ok": "Tout est en ordre", "warning": "Attention requise", "error": "Erreur détectée"}[overall]

    return jsonify({
        "db_type":    "SQLite" if is_sqlite else "PostgreSQL" if is_pg else "Inconnu",
        "db_size":    db_size,
        "status":     overall,
        "status_msg": status_msg,
        "tables":     tables_info,
        "checks":     checks,
    })


@admin_bp.route("/db/optimize", methods=["POST"])
@login_required
def db_optimize():
    err = _require_admin()
    if err:
        return err
    from sqlalchemy import text
    try:
        with db.engine.connect() as conn:
            if "sqlite" in str(db.engine.url):
                conn.execute(text("PRAGMA optimize"))
                conn.commit()
            elif "postgresql" in str(db.engine.url):
                conn.execute(text("ANALYZE"))
                conn.commit()
        _log("DB_OPTIMIZE", "Optimisation base de données")
        db.session.commit()
        return jsonify({"ok": True, "message": "Base de données optimisée avec succès."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.route("/db/vacuum", methods=["POST"])
@login_required
def db_vacuum():
    err = _require_admin()
    if err:
        return err
    from sqlalchemy import text
    try:
        if "sqlite" not in str(db.engine.url):
            return jsonify({"ok": False, "error": "VACUUM disponible uniquement sur SQLite."}), 400
        # VACUUM doit s'exécuter hors transaction
        with db.engine.connect() as conn:
            conn.execute(text("VACUUM"))
        _log("DB_VACUUM", "Nettoyage VACUUM SQLite")
        db.session.commit()
        return jsonify({"ok": True, "message": "Nettoyage VACUUM effectué avec succès."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@admin_bp.route("/db/config")
@login_required
def get_db_config():
    err = _require_admin()
    if err:
        return err

    db_url = str(db.engine.url)
    is_sqlite = "sqlite" in db_url
    is_pg     = "postgresql" in db_url

    result = {
        "db_type":       "sqlite" if is_sqlite else "postgresql" if is_pg else "other",
        "db_url_masked": _mask_url(db_url),
    }
    if is_sqlite:
        result["sqlite_file"] = db_url.replace("sqlite:///", "").lstrip("/")
    elif is_pg:
        url = db.engine.url
        result["pg_host"] = url.host or ""
        result["pg_port"] = str(url.port or 5432)
        result["pg_db"]   = url.database or ""
        result["pg_user"] = url.username or ""

    return jsonify(result)


@admin_bp.route("/db/config", methods=["POST"])
@login_required
def set_db_config():
    err = _require_admin()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    url  = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante."}), 400

    # Corriger postgres:// → postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    # Sauvegarder dans AppSetting (sera lue au prochain redémarrage)
    AppSetting.set("db_url_override", url)
    _log("DB_CONFIG", f"Nouvelle URL DB : {_mask_url(url)}")
    db.session.commit()
    return jsonify({"ok": True, "message": "Configuration sauvegardée. Redémarrez le serveur."})


@admin_bp.route("/db/test", methods=["POST"])
@login_required
def test_db_connection():
    err = _require_admin()
    if err:
        return err

    from sqlalchemy import create_engine, text as sa_text
    data = request.get_json(silent=True) or {}
    url  = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL manquante."}), 400
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    try:
        engine = create_engine(url, connect_args={"connect_timeout": 5} if "postgresql" in url else {})
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


def _mask_url(url: str) -> str:
    """Masque le mot de passe dans une URL de connexion."""
    import re
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1****\2", url)
