"""
CsrPlan model - represents an annual CSR plan for a site.

Each site has one plan per year (e.g. Site A, 2024). The plan has a status (DRAFT -> SUBMITTED -> VALIDATED).
Validation mode 101 or 111 defines the approval flow. Activities belong to a plan via csr_activities.plan_id.
"""
import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    """Generate a new UUID string for the primary key."""
    return str(uuid.uuid4())


class CsrPlan(db.Model):
    __tablename__ = "csr_plans"
    __table_args__ = (
        db.UniqueConstraint("site_id", "year", name="uq_csr_plans_site_year"),
        {
            "comment": "Plans annuels CSR par site",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default, comment="Identifiant du plan")
    site_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False,
        comment="Site concerné"
    )
    year = db.Column(db.Integer, nullable=False, comment="Année du plan")
    validation_mode = db.Column(
        db.String(10), nullable=False, default="101",
        comment="Mode de validation: 101 ou 111"
    )
    status = db.Column(
        db.String(20), nullable=False, default="DRAFT",
        comment="Statut: DRAFT, SUBMITTED, VALIDATED, REJECTED, LOCKED"
    )
    allocated_budget = db.Column(db.Numeric(15, 2), nullable=True, comment="Budget alloué du plan (€)")
    total_hc = db.Column(db.Integer, nullable=True, comment="Effectif total (HC) commun aux activités du plan")
    submitted_at = db.Column(db.DateTime, nullable=True, comment="Date de soumission")
    rejected_comment = db.Column(db.Text, nullable=True, comment="Motif de rejet si status=REJECTED")
    rejected_activity_ids = db.Column(
        db.Text, nullable=True,
        comment="IDs des activités à modifier (JSON array), ex. [\"uuid1\", \"uuid2\"]"
    )
    validation_step = db.Column(
        db.Integer, nullable=True,
        comment="Mode 111: 1=attente Level 1, 2=attente Level 2. Mode 101: 2=attente Level 2"
    )
    validated_at = db.Column(db.DateTime, nullable=True, comment="Date de validation finale")
    unlock_until = db.Column(
        db.DateTime, nullable=True,
        comment="Date limite de modification (après approbation d'une demande de modification); au-delà le plan redevient verrouillé"
    )
    unlock_since = db.Column(
        db.DateTime, nullable=True,
        comment="Date de début de la dernière ouverture (approbation demande de modification); sert à marquer activités ajoutées/modifiées"
    )
    created_by = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Créateur du plan"
    )
    submitted_by = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Dernier utilisateur ayant soumis le plan pour validation",
    )
    created_at = db.Column(db.DateTime, default=db.func.now(), comment="Date de création")
    updated_at = db.Column(
        db.DateTime, default=db.func.now(), onupdate=db.func.now(),
        comment="Dernière mise à jour"
    )

    site = db.relationship("Site", backref=db.backref("csr_plans", lazy="dynamic"))
