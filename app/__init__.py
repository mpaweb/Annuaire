"""
Annuaire Neoedge — Application Web
====================================
Factory Flask : initialise extensions, blueprints, admin par défaut.
"""

import os
import sys
from datetime import timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

db           = SQLAlchemy()
login_manager = LoginManager()
limiter      = Limiter(key_func=get_remote_address, default_limits=[])

# Clés insécurisées connues — on bloque le démarrage en prod si utilisées
_INSECURE_KEYS = {"dev-secret-insecure", "changez-moi-avec-une-vraie-cle-secrete", ""}


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # ── Vérification SECRET_KEY ────────────────────────────────────────────────
    secret_key = os.environ.get("SECRET_KEY", "dev-secret-insecure")
    flask_env  = os.environ.get("FLASK_ENV", "production")
    if secret_key in _INSECURE_KEYS:
        if flask_env == "production":
            print("[SECURITE CRITIQUE] SECRET_KEY non configurée ! "
                  "Générez une clé avec : python -c \"import secrets; print(secrets.token_hex(32))\" "
                  "et ajoutez-la dans .env", file=sys.stderr)
            sys.exit(1)
        else:
            print("[AVERTISSEMENT] SECRET_KEY non sécurisée — acceptable uniquement en développement.")

    # ── Configuration de base ──────────────────────────────────────────────────
    app.config["SECRET_KEY"]                  = secret_key
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_ENABLED"]            = True

    # ── Session sécurisée ─────────────────────────────────────────────────────
    is_https = flask_env == "production"
    app.config["SESSION_COOKIE_SECURE"]   = is_https   # Cookie envoyé uniquement en HTTPS
    app.config["SESSION_COOKIE_HTTPONLY"] = True        # Inaccessible au JS
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"      # Protège contre CSRF cross-site
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)  # Timeout 8h

    # ── Base de données ───────────────────────────────────────────────────────
    # Priorité : override admin > variable d'environnement > SQLite par défaut
    from app.models import AppSetting as _AS  # import tardif évité ici — on lit .env seulement
    db_url = os.environ.get("DATABASE_URL", "sqlite:///annuaire.db")

    # Railway fournit parfois postgres:// (ancien format)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    # Sur Windows, psycopg3 est requis
    if sys.platform == "win32" and "postgresql://" in db_url and "+psycopg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view            = "auth.login"
    login_manager.login_message         = "Veuillez vous connecter pour accéder à l'annuaire."
    login_manager.login_message_category = "warning"
    limiter.init_app(app)

    # ── Blueprints ────────────────────────────────────────────────────────────
    from app.auth import auth_bp
    from app.routes.contacts import contacts_bp
    from app.routes.rocs import rocs_bp
    from app.routes.export import export_bp
    from app.routes.admin import admin_bp
    from app.routes.duplicates import duplicates_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(contacts_bp,   url_prefix="/api/contacts")
    app.register_blueprint(rocs_bp,       url_prefix="/api/rocs")
    app.register_blueprint(export_bp,     url_prefix="/api/export")
    app.register_blueprint(admin_bp,      url_prefix="/api/admin")
    app.register_blueprint(duplicates_bp, url_prefix="/api/duplicates")

    # ── Headers de sécurité HTTP sur chaque réponse ───────────────────────────
    @app.after_request
    def set_security_headers(response):
        # Empêche le clickjacking (intégration dans une iframe)
        response.headers["X-Frame-Options"] = "DENY"
        # Empêche le sniffing MIME
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Force le navigateur à ne pas mettre en cache les pages sensibles
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"]        = "no-cache"
        # Politique de référent — ne pas fuiter l'URL dans les requêtes externes
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions navigateur (désactive les fonctionnalités non nécessaires)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # Content Security Policy — bloque XSS en limitant les sources autorisées
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "   # unsafe-inline nécessaire pour les handlers onclick du HTML
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "                # data: pour les logos en base64
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        # HSTS : forcer HTTPS pendant 1 an (uniquement si on est en production)
        if is_https:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ── Gestionnaire erreur rate limit ────────────────────────────────────────
    @app.errorhandler(429)
    def ratelimit_error(e):
        if request.is_json or request.path.startswith("/api/"):
            return jsonify({"error": "Trop de tentatives. Réessayez dans quelques minutes."}), 429
        from flask import render_template
        return render_template("login.html", rate_limited=True), 429

    # ── Créer les tables + admin par défaut ───────────────────────────────────
    with app.app_context():
        db.create_all()
        _apply_db_override()
        _create_default_admin()

    return app


def _apply_db_override() -> None:
    """Applique l'URL de DB configurée via l'interface admin si elle existe."""
    try:
        from app.models import AppSetting
        override = AppSetting.get("db_url_override", "")
        if override:
            print(f"[DB] URL override détectée : utilisation de la config admin.")
    except Exception:
        pass


def _create_default_admin() -> None:
    """Crée le compte admin au premier démarrage s'il n'existe pas."""
    from app.models import User

    username = os.environ.get("ADMIN_USERNAME", "admin")
    if User.query.filter_by(username=username).first():
        return

    pwd = os.environ.get("ADMIN_PASSWORD", "")
    if not pwd or len(pwd) < 8:
        pwd = "ChangeMe2024!"
        print(f"[INIT] Mot de passe admin par défaut utilisé : {pwd} — changez-le immédiatement !")

    admin = User(
        username  = username,
        email     = os.environ.get("ADMIN_EMAIL", "admin@neoedge.fr"),
        role      = "admin",
        full_name = "Administrateur",
    )
    admin.set_password(pwd)
    db.session.add(admin)
    db.session.commit()
    print(f"[INIT] Compte admin créé : {username}")
