"""
Modèles SQLAlchemy — compatibles PostgreSQL et SQLite (dev local).
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


# ══════════════════════════════════════════════════════════════════════════════
# UTILISATEURS
# ══════════════════════════════════════════════════════════════════════════════

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    email         = db.Column(db.String(200), unique=True, nullable=False)
    full_name     = db.Column(db.String(150), nullable=False, default="")
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="viewer")
    active        = db.Column(db.Boolean,     nullable=False, default=True)
    # Préférence de thème : system | light | dark
    theme         = db.Column(db.String(10),  nullable=False, default="system")
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login    = db.Column(db.DateTime, nullable=True)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def can_write(self) -> bool:
        return self.role in ("admin", "editor")

    def to_dict(self) -> dict:
        return {
            "id":        self.id,
            "username":  self.username,
            "email":     self.email,
            "full_name": self.full_name,
            "role":      self.role,
            "active":    self.active,
            "theme":     self.theme,
        }


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


# ══════════════════════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════════════════════

class Contact(db.Model):
    __tablename__ = "contacts"

    id         = db.Column(db.Integer, primary_key=True)
    societe    = db.Column(db.String(200), nullable=False, default="", index=True)
    nom        = db.Column(db.String(150), nullable=False, default="")
    prenom     = db.Column(db.String(150), nullable=False, default="")
    fonction   = db.Column(db.String(200), default="")
    email      = db.Column(db.String(200), default="", index=True)
    telephone  = db.Column(db.String(50),  default="")
    telephone2 = db.Column(db.String(50),  default="")
    notes      = db.Column(db.Text,        default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(80), default="")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "societe":    self.societe    or "",
            "nom":        self.nom        or "",
            "prenom":     self.prenom     or "",
            "fonction":   self.fonction   or "",
            "email":      self.email      or "",
            "telephone":  self.telephone  or "",
            "telephone2": self.telephone2 or "",
            "notes":      self.notes      or "",
            "updated_at": self.updated_at.strftime("%d/%m/%Y %H:%M") if self.updated_at else "",
            "updated_by": self.updated_by or "",
        }


# ══════════════════════════════════════════════════════════════════════════════
# ROC
# ══════════════════════════════════════════════════════════════════════════════

class Roc(db.Model):
    __tablename__ = "rocs"

    id                        = db.Column(db.Integer, primary_key=True)
    nom_client                = db.Column(db.String(200), nullable=False, default="", index=True)
    roc                       = db.Column(db.String(100), default="", index=True)
    trinity                   = db.Column(db.String(100), default="")
    infogerance               = db.Column(db.String(200), default="")
    astreinte                 = db.Column(db.String(200), default="")
    type_contrat              = db.Column(db.String(100), default="")
    date_anniversaire_contrat = db.Column(db.String(20),  default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    updated_by = db.Column(db.String(80), default="")

    def to_dict(self) -> dict:
        return {
            "id":                        self.id,
            "nom_client":                self.nom_client   or "",
            "roc":                       self.roc          or "",
            "trinity":                   self.trinity      or "",
            "infogerance":               self.infogerance  or "",
            "astreinte":                 self.astreinte    or "",
            "type_contrat":              self.type_contrat or "",
            "date_anniversaire_contrat": self.date_anniversaire_contrat or "",
            "updated_at": self.updated_at.strftime("%d/%m/%Y %H:%M") if self.updated_at else "",
            "updated_by": self.updated_by or "",
        }


# ══════════════════════════════════════════════════════════════════════════════
# JOURNAL D'AUDIT
# ══════════════════════════════════════════════════════════════════════════════

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id         = db.Column(db.Integer, primary_key=True)
    timestamp  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    username   = db.Column(db.String(80),  nullable=False)
    action     = db.Column(db.String(50),  nullable=False)
    table_name = db.Column(db.String(50),  nullable=False, default="")
    record_id  = db.Column(db.Integer,     nullable=True)
    detail     = db.Column(db.Text,        default="")
    ip_address = db.Column(db.String(50),  default="")

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "timestamp":  self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "username":   self.username,
            "action":     self.action,
            "table_name": self.table_name,
            "record_id":  self.record_id,
            "detail":     self.detail,
            "ip_address": self.ip_address,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SAUVEGARDES
# ══════════════════════════════════════════════════════════════════════════════

class Backup(db.Model):
    __tablename__ = "backups"

    id         = db.Column(db.Integer, primary_key=True)
    filename   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    created_by = db.Column(db.String(80), nullable=False)
    # type : manual | auto
    kind       = db.Column(db.String(10), nullable=False, default="manual")
    nb_contacts= db.Column(db.Integer, default=0)
    nb_rocs    = db.Column(db.Integer, default=0)
    # Contenu JSON compressé en base (pour restauration)
    data_json  = db.Column(db.Text, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "filename":    self.filename,
            "created_at":  self.created_at.strftime("%d/%m/%Y à %H:%M:%S"),
            "created_by":  self.created_by,
            "kind":        self.kind,
            "nb_contacts": self.nb_contacts,
            "nb_rocs":     self.nb_rocs,
        }


# ══════════════════════════════════════════════════════════════════════════════
# PARAMÈTRES APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key   = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")

    @staticmethod
    def get(key: str, default: str = "") -> str:
        row = AppSetting.query.get(key)
        return row.value if row else default

    @staticmethod
    def set(key: str, value: str) -> None:
        row = AppSetting.query.get(key)
        if row:
            row.value = value
        else:
            db.session.add(AppSetting(key=key, value=value))
        db.session.commit()
