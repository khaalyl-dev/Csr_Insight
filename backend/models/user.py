"""
User model - represents a user account in the system.

A user can be SITE_USER (manages one or more sites) or CORPORATE_USER (admin with global access).
This table stores login credentials (email, password hash), profile info (name, avatar, phone),
preferences (language, theme), and notification settings.
"""
import uuid

import bcrypt
from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    """Generate a new UUID string for the primary key (e.g. 'a1b2c3d4-e5f6-...')."""
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {
        "comment": "Utilisateurs du système (Site User, Corporate User)",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_unicode_ci",
    }

    id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default,
        comment="Identifiant unique de l'utilisateur"
    )
    first_name = db.Column(db.String(255), nullable=False, comment="Prénom")
    last_name = db.Column(db.String(255), nullable=False, comment="Nom")
    email = db.Column(
        db.String(255), unique=True, nullable=False, index=True,
        comment="Adresse email (identifiant de connexion)"
    )
    password_hash = db.Column(db.String(255), nullable=False, comment="Mot de passe hashé")
    role = db.Column(
        db.String(50), nullable=False, default="SITE_USER",
        comment="Rôle: SITE_USER ou CORPORATE_USER"
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True, comment="Compte actif ou désactivé")
    is_corporate_global = db.Column(
        db.Boolean, nullable=False, default=False,
        comment="Accès corporate global (tous les sites)"
    )
    avatar_url = db.Column(db.String(512), nullable=True, comment="Chemin relatif de la photo de profil (ex: profile_photos/user_id.jpg)")
    phone = db.Column(db.String(64), nullable=True, comment="Téléphone utilisateur (avec préfixe pays)")
    language = db.Column(db.String(10), nullable=False, default="en", comment="Préférence langue (fr/en)")
    theme = db.Column(db.String(20), nullable=False, default="light", comment="Thème UI (light/dark)")
    notify_csr_plan_validation = db.Column(db.Boolean, nullable=False, default=True, comment="Notification validation plan CSR")
    notify_activity_validation = db.Column(db.Boolean, nullable=False, default=True, comment="Notification validation activité")
    notify_activity_reminders = db.Column(db.Boolean, nullable=False, default=True, comment="Rappels d'activités")
    notify_weekly_summary_email = db.Column(db.Boolean, nullable=False, default=True, comment="Email résumé CSR hebdomadaire")
    created_at = db.Column(db.DateTime, default=db.func.now(), comment="Date de création")
    updated_at = db.Column(
        db.DateTime, default=db.func.now(), onupdate=db.func.now(),
        comment="Dernière mise à jour"
    )
    permissions_rel = db.relationship(
        "UserPermission",
        backref="user",
        lazy="select",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def verify_password(self, password: str) -> bool:
        """Check if the given plain-text password matches the stored hash. Returns True/False."""
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def get_permissions(self):
        rows = [p for p in (self.permissions_rel or []) if bool(getattr(p, "is_allowed", True))]
        if not rows:
            return None
        keys = sorted({f"{p.resource}.{p.action}" for p in rows if p.resource and p.action})
        return {"keys": keys}

    def set_permissions(self, permissions) -> None:
        # Normalize incoming permission keys first.
        keys = []
        if isinstance(permissions, dict) and isinstance(permissions.get("keys"), list):
            keys = [str(k).strip() for k in permissions.get("keys") if str(k).strip()]
        elif isinstance(permissions, dict):
            # Backward compatibility with matrix format.
            for resource, actions in permissions.items():
                if not isinstance(actions, dict):
                    continue
                for action, allowed in actions.items():
                    if allowed:
                        keys.append(f"{resource}.{action}")
        uniq = sorted(set(keys))

        from models.user_permission import UserPermission

        # Important: for persisted users, force DELETE in DB first, then INSERT.
        # This avoids transient unique collisions on (user_id, resource, action)
        # when SQLAlchemy flush order inserts before relationship deletes.
        if self.id:
            UserPermission.query.filter_by(user_id=self.id).delete(synchronize_session=False)
            db.session.flush()
            if permissions is None:
                return
            for key in uniq:
                if "." not in key:
                    continue
                resource, action = key.split(".", 1)
                db.session.add(
                    UserPermission(
                        user_id=self.id,
                        resource=resource,
                        action=action,
                        is_allowed=True,
                    )
                )
            return

        # For transient users (before first flush), relationship assignment is fine.
        self.permissions_rel = []
        if permissions is None:
            return
        self.permissions_rel = [
            UserPermission(
                resource=key.split(".", 1)[0],
                action=key.split(".", 1)[1],
                is_allowed=True,
            )
            for key in uniq
            if "." in key
        ]
    @staticmethod
    def hash_password(password: str) -> str:
        """Convert a plain-text password to a secure hash (for storing in DB, never store plain passwords)."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
