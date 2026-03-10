"""
Blueprint d'authentification : login, logout, changement de mot de passe.
"""

from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, AuditLog

auth_bp = Blueprint("auth", __name__)


def _log(action: str, detail: str = "") -> None:
    entry = AuditLog(
        username=current_user.username if current_user.is_authenticated else "anonymous",
        action=action,
        table_name="users",
        detail=detail,
        ip_address=request.remote_addr or "",
    )
    db.session.add(entry)
    db.session.commit()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            if request.is_json:
                return jsonify({"error": "Identifiants incorrects."}), 401
            flash("Identifiants incorrects.", "danger")
            return render_template("login.html"), 401

        if not user.active:
            if request.is_json:
                return jsonify({"error": "Compte désactivé."}), 403
            flash("Compte désactivé.", "danger")
            return render_template("login.html"), 403

        login_user(user, remember=True)
        user.last_login = datetime.now(timezone.utc)
        entry = AuditLog(
            username=user.username,
            action="LOGIN",
            table_name="users",
            detail=f"Connexion depuis {request.remote_addr}",
            ip_address=request.remote_addr or "",
        )
        db.session.add(entry)
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
    if request.is_json:
        return jsonify({"ok": True})
    return redirect(url_for("auth.login"))


@auth_bp.route("/api/auth/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_pw = (data.get("old_password") or "").strip()
    new_pw = (data.get("new_password") or "").strip()

    if not current_user.check_password(old_pw):
        return jsonify({"error": "Mot de passe actuel incorrect."}), 400
    if len(new_pw) < 8:
        return jsonify({"error": "Le nouveau mot de passe doit faire au moins 8 caractères."}), 400

    current_user.set_password(new_pw)
    db.session.commit()
    _log("CHANGE_PASSWORD", "Mot de passe modifié")
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
    })
