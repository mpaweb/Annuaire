"""
Blueprint d'authentification : login, logout, changement de mot de passe.
Sécurité : rate limiting, protection brute force, session permanente avec timeout.
"""

from datetime import datetime, timezone, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, session)
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter
from app.models import User, AuditLog

auth_bp = Blueprint("auth", __name__)

# ── Compteur de tentatives en mémoire ────────────────────────────────────────
_login_attempts: dict = {}
MAX_ATTEMPTS    = 5
LOCKOUT_MINUTES = 15


def _log(action: str, detail: str = "") -> None:
    entry = AuditLog(
        username   = current_user.username if current_user.is_authenticated else "anonymous",
        action     = action,
        table_name = "users",
        detail     = detail,
        ip_address = request.remote_addr or "",
    )
    db.session.add(entry)
    db.session.commit()


def _check_brute_force(ip: str) -> tuple:
    """Retourne (bloque, message). Reset si lockout expire."""
    entry = _login_attempts.get(ip)
    if not entry:
        return False, ""
    lockout = entry.get("lockout_until")
    if lockout and datetime.now(timezone.utc) > lockout:
        _login_attempts.pop(ip, None)
        return False, ""
    if lockout:
        remaining = int((lockout - datetime.now(timezone.utc)).total_seconds() / 60) + 1
        return True, f"Compte temporairement bloque. Reessayez dans {remaining} min."
    return False, ""


def _record_failed_attempt(ip: str) -> None:
    entry = _login_attempts.setdefault(ip, {"count": 0, "lockout_until": None})
    entry["count"] += 1
    if entry["count"] >= MAX_ATTEMPTS:
        entry["lockout_until"] = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)


def _reset_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        ip = request.remote_addr or "unknown"

        blocked, block_msg = _check_brute_force(ip)
        if blocked:
            if request.is_json:
                return jsonify({"error": block_msg}), 429
            flash(block_msg, "danger")
            return render_template("login.html", rate_limited=True), 429

        data     = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            _record_failed_attempt(ip)
            entry = _login_attempts.get(ip, {})
            remaining = MAX_ATTEMPTS - entry.get("count", 0)
            msg = "Identifiants incorrects."
            if remaining > 0:
                msg += f" ({remaining} tentative(s) restante(s) avant blocage)"
            else:
                msg = f"Trop de tentatives. Compte bloque {LOCKOUT_MINUTES} minutes."
            db.session.add(AuditLog(
                username   = username or "inconnu",
                action     = "LOGIN_FAIL",
                table_name = "users",
                detail     = f"Echec connexion depuis {ip}",
                ip_address = ip,
            ))
            db.session.commit()
            if request.is_json:
                return jsonify({"error": msg}), 401
            flash(msg, "danger")
            return render_template("login.html"), 401

        if not user.active:
            msg = "Compte desactive. Contactez l'administrateur."
            if request.is_json:
                return jsonify({"error": msg}), 403
            flash(msg, "danger")
            return render_template("login.html"), 403

        _reset_attempts(ip)
        login_user(user, remember=False)
        session.permanent = True   # Active le timeout de 8h

        user.last_login = datetime.now(timezone.utc)
        db.session.add(AuditLog(
            username   = user.username,
            action     = "LOGIN",
            table_name = "users",
            detail     = f"Connexion depuis {ip}",
            ip_address = ip,
        ))
        db.session.commit()

        if request.is_json:
            return jsonify({"ok": True, "role": user.role, "full_name": user.full_name})
        return redirect(url_for("main.index"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    _log("LOGOUT")
    logout_user()
    session.clear()
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def change_password():
    data   = request.get_json(silent=True) or {}
    old_pw = (data.get("old_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()

    if not current_user.check_password(old_pw):
        return jsonify({"error": "Mot de passe actuel incorrect."}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "Le nouveau mot de passe doit faire au moins 8 caracteres."}), 400
    if new_pw == old_pw:
        return jsonify({"error": "Le nouveau mot de passe doit etre different de l'ancien."}), 400

    current_user.set_password(new_pw)
    db.session.commit()
    _log("CHANGE_PASSWORD", "Mot de passe modifie")
    return jsonify({"ok": True})


@auth_bp.route("/api/auth/me")
@login_required
def me():
    return jsonify({
        "id":        current_user.id,
        "username":  current_user.username,
        "full_name": current_user.full_name,
        "role":      current_user.role,
        "email":     current_user.email,
        "theme":     current_user.theme,
    })
