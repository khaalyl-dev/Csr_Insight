"""
UserPermission model - normalized per-user permission entries.
"""
import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    return str(uuid.uuid4())


class UserPermission(db.Model):
    __tablename__ = "user_permissions"
    __table_args__ = (
        db.UniqueConstraint("user_id", "resource", "action", name="uq_user_permissions_user_resource_action"),
        {
            "comment": "Permissions globales par utilisateur (resource/action)",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        primary_key=True,
        default=_uuid_default,
        comment="Identifiant unique de permission utilisateur",
    )
    user_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Utilisateur concerné",
    )
    resource = db.Column(db.String(64), nullable=False, comment="Ressource (plan, activity, ...)")
    action = db.Column(db.String(64), nullable=False, comment="Action (read, create, ...)")
    is_allowed = db.Column(db.Boolean, nullable=False, default=True, comment="Permission autorisée")
    created_at = db.Column(db.DateTime, default=db.func.now(), comment="Date de création")
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), comment="Dernière mise à jour")

