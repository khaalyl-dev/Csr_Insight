"""
RealizedCsr model - stores the actual results of a CSR activity after it is done.

Each row links to a csr_activity and records: realized budget, participants, volunteer hours,
impact achieved, realization date. One activity can have multiple realized_csr rows (e.g. monthly reports).
"""
import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    """Generate a new UUID string for the primary key."""
    return str(uuid.uuid4())


class RealizedCsr(db.Model):
    __tablename__ = "realized_activity"
    __table_args__ = (
        {
            "comment": "Activités réalisées (saisie réalisations, coûts, participants, impact)",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default, comment="Identifiant de la réalisation")
    activity_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("planned_activity.id", ondelete="CASCADE"), nullable=False,
        comment="Activité (planifiée ou hors plan)"
    )
    # Données réalisées (alignées avec le tableau Realized activity)
    participants = db.Column(db.Integer, nullable=True, comment="Nombre de participants internes")
    corporate_image_improved = db.Column(db.Boolean, nullable=True, comment="Image corporate améliorée")
    incidents_number = db.Column(db.Integer, nullable=True, comment="Nombre d'incidents")
    contact_department = db.Column(db.String(255), nullable=True, comment="Département du contact")
    realized_budget = db.Column(db.Numeric(15, 2), nullable=True, comment="Budget réel dépensé (€)")
    action_impact_actual = db.Column(db.Numeric(15, 2), nullable=True, comment="Impact réalisé (en nombre)")
    action_impact_unit = db.Column(db.String(100), nullable=True, comment="Unité d'impact réalisée")
    # Indique si la réalisation vient d'une activité hors plan
    is_off_plan = db.Column(db.Boolean, nullable=False, default=False, comment="Réalisation d'une activité hors plan")
    off_plan_validation_mode = db.Column(
        db.String(10), nullable=True,
        comment="Mode de validation hors plan: 101 ou 111"
    )
    off_plan_validation_step = db.Column(
        db.Integer, nullable=True,
        comment="Étape de validation hors plan (111: 1 niveau site, 2 corporate; 101: 2 corporate)"
    )
    realization_date = db.Column(db.Date, nullable=True, comment="Date de réalisation")
    comment = db.Column(db.Text, nullable=True, comment="Commentaire")
    contact_name = db.Column(db.String(255), nullable=True, comment="Nom du contact")
    contact_email = db.Column(db.String(255), nullable=True, comment="Email du contact")
    created_by = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Utilisateur ayant saisi la réalisation"
    )
    created_at = db.Column(db.DateTime, default=db.func.now(), comment="Date de saisie")
    updated_at = db.Column(
        db.DateTime, default=db.func.now(), onupdate=db.func.now(),
        comment="Dernière mise à jour de la réalisation"
    )
    unlock_until = db.Column(
        db.DateTime, nullable=True,
        comment="Date limite de modification de la réalisation; au-delà elle redevient verrouillée"
    )
    unlock_since = db.Column(
        db.DateTime, nullable=True,
        comment="Date de début de la dernière ouverture de la réalisation"
    )
    status = db.Column(
        db.String(20), nullable=False, default="DRAFT",
        comment="Statut de la réalisation (DRAFT, VALIDATED, REJECTED, etc.)"
    )

    activity = db.relationship("CsrActivity", backref=db.backref("realized_csr", lazy="dynamic"))
