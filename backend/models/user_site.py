"""
UserSite model - links users to sites (who has access to which site).

Each row means: "User X has access to Site Y". The grade (level_0, level_1, level_2) indicates
the validation level for that user on that site. A corporate user with level_2 can approve plans.
A site user with level_1 can create/submit plans. is_active=False means access was revoked.
"""
import uuid
import json

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    """Generate UUID string for primary key."""
    return str(uuid.uuid4())


class UserSite(db.Model):
    __tablename__ = "user_sites"
    __table_args__ = (
        db.UniqueConstraint("user_id", "site_id", name="uq_user_sites_user_site"),
        {
            "comment": "Association utilisateur–site: droits d'accès par site",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default, comment="Identifiant de l'association")
    user_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        comment="Utilisateur"
    )
    site_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False,
        comment="Site auquel l'accès est accordé"
    )
    grade = db.Column(
        db.String(20), nullable=True,
        comment="Niveau de validation: level_0, level_1, level_2"
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True, comment="Accès actif ou non")
    granted_by = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Utilisateur ayant accordé l'accès"
    )
    granted_at = db.Column(db.DateTime, nullable=True, comment="Date d'attribution")
    access_types_json = db.Column(
        db.Text,
        nullable=True,
        comment="Types d'accès accordés pour ce site (JSON array)",
    )

    user = db.relationship("User", foreign_keys=[user_id])
    site = db.relationship("Site", backref=db.backref("user_sites", lazy="dynamic"))

    def get_access_types(self):
        if not self.access_types_json:
            return []
        try:
            value = json.loads(self.access_types_json)
            if isinstance(value, list):
                return [str(v) for v in value if v is not None and str(v).strip()]
            return []
        except Exception:
            return []

    def set_access_types(self, access_types):
        values = [str(v).strip() for v in (access_types or []) if v is not None and str(v).strip()]
        self.access_types_json = json.dumps(values) if values else None
