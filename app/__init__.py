"""
Annuaire Neoedge — Application Web
====================================
Factory Flask : initialise extensions, blueprints, admin par défaut.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Configuration ──────────────────────────────────────────────────────────
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-insecure")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///annuaire_dev.db"
    )
    # Railway fournit parfois postgres:// (ancien format) — corriger pour SQLAlchemy
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    # Sur Windows, psycopg3 est utilisé : adapter le driver dans l'URL
    import sys as _sys
    if _sys.platform == "win32" and "postgresql://" in uri and "+psycopg" not in uri:
        uri = uri.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = uri

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"] = True

    # ── Extensions ─────────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à l'annuaire."
    login_manager.login_message_category = "warning"

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from app.auth import auth_bp
    from app.routes.contacts import contacts_bp
    from app.routes.rocs import rocs_bp
    from app.routes.export import export_bp
    from app.routes.admin import admin_bp
    from app.routes.duplicates import duplicates_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp, url_prefix="/api/contacts")
    app.register_blueprint(rocs_bp, url_prefix="/api/rocs")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(duplicates_bp, url_prefix="/api/duplicates")

    # ── Créer les tables + admin par défaut ────────────────────────────────────
    with app.app_context():
        db.create_all()
        _create_default_admin()

    return app


def _create_default_admin() -> None:
    """Crée le compte admin au premier démarrage s'il n'existe pas."""
    from app.models import User

    username = os.environ.get("ADMIN_USERNAME", "admin")
    if User.query.filter_by(username=username).first():
        return

    admin = User(
        username=username,
        email=os.environ.get("ADMIN_EMAIL", "admin@neoedge.fr"),
        role="admin",
        full_name="Administrateur",
    )
    admin.set_password(os.environ.get("ADMIN_PASSWORD", "admin"))
    from app import db as _db
    _db.session.add(admin)
    _db.session.commit()
    print(f"[INIT] Compte admin créé : {username}")
