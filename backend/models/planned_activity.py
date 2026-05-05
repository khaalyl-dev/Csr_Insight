"""
CsrActivity model - represents a planned CSR activity (not yet realized).

Each activity belongs to a plan, a category (Environment, Social, etc.), and optionally an external partner.
Planned budget, dates, impact targets are here. When the activity is done, the actual results go in
realized_csr (linked by activity_id). is_off_plan=True for activities outside the annual plan.
"""
import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    """Generate a new UUID string for the primary key."""
    return str(uuid.uuid4())


class CsrActivity(db.Model):
    __tablename__ = "planned_activity"
    __table_args__ = (
        db.Index("ix_csr_activities_plan_id", "plan_id"),
        db.Index("ix_csr_activities_category_id", "category_id"),
        db.UniqueConstraint("plan_id", "activity_number", name="uq_csr_activities_plan_number"),
        {
            "comment": "Activités CSR (planifiées ou hors plan)",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default, comment="Identifiant de l'activité")
    plan_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("csr_plans.id", ondelete="CASCADE"), nullable=False,
        comment="Plan annuel CSR"
    )
    category_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False,
        comment="Catégorie (Environment, Social, etc.)"
    )
    external_partner_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("external_partners.id", ondelete="SET NULL"), nullable=True,
        comment="Partenaire externe éventuel"
    )
    activity_number = db.Column(db.String(50), nullable=False, comment="Numéro d'activité (ex. CSR 1)")
    title = db.Column(db.String(255), nullable=False, comment="Titre / intitulé")
    organization = db.Column(db.String(255), nullable=True, comment="Organisation")
    contract_type = db.Column(db.String(100), nullable=True, comment="Type de contrat")
    description = db.Column(db.Text, nullable=True, comment="Description détaillée")
    collaboration_nature = db.Column(
        db.String(30), nullable=True,
        comment="Nature collaboration: CHARITY_DONATION, PARTNERSHIP, SPONSORSHIP, OTHERS"
    )
    periodicity = db.Column(db.String(100), nullable=True, comment="Périodicité (ex. NA, Every year)")
    planned_budget = db.Column(db.Numeric(15, 2), nullable=True, comment="Budget prévu (€)")
    # Action impact (target) – in numbers and unit
    action_impact_target = db.Column(db.Numeric(15, 2), nullable=True, comment="Objectif d'impact (nombre)")
    action_impact_unit = db.Column(db.String(100), nullable=True, comment="Unité d'impact cible (Trees, etc.)")
    action_impact_duration = db.Column(db.String(100), nullable=True, comment="Durée de l'impact")
    employees_planned = db.Column(db.Integer, nullable=True, comment="Employés impliqués (prévu)")
    start_year = db.Column(db.Integer, nullable=True, comment="Année de démarrage")
    edition = db.Column(db.Integer, nullable=True, comment="Numéro d'édition")
    edition_year = db.Column(
        db.Integer,
        nullable=True,
        comment="Année de l'édition (colonne Year du fichier consolidé CSR)",
    )
    organizer = db.Column(db.String(255), nullable=True, comment="Organisateur (ex. HR)")
    status = db.Column(
        db.String(20), nullable=False, default="DRAFT",
        comment=(
            "Statut workflow en base (soumission, validation d’activité, demandes de modification). "
            "Ce n’est pas le statut « métier » affiché quand le plan annuel est validé : dans ce cas l’API "
            "calcule effective_status (PLANNED / IN_PROGRESS / COMPLETED, UNDER_REVIEW, REJECTED, CANCELLED)."
        ),
    )
    # Métadonnées de création / mise à jour / verrouillage
    created_by = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"), db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        comment="Utilisateur ayant créé l'activité"
    )
    created_at = db.Column(db.DateTime, default=db.func.now(), comment="Date de création")
    updated_at = db.Column(
        db.DateTime, default=db.func.now(), onupdate=db.func.now(),
        comment="Dernière mise à jour"
    )
    unlock_until = db.Column(
        db.DateTime, nullable=True,
        comment="Date limite de modification (après approbation d'une demande de modification activité); au-delà l'activité redevient verrouillée"
    )
    unlock_since = db.Column(
        db.DateTime, nullable=True,
        comment="Date de début de la dernière ouverture (approbation demande de modification activité)"
    )
    # Workflow de validation pour une modification soumise alors que le plan est déjà validé (pas hors plan).
    off_plan_validation_mode = db.Column(
        db.String(10), nullable=True,
        comment="Mode validation modification in-plan: 101 ou 111 (réutilise la logique hors plan)"
    )
    off_plan_validation_step = db.Column(
        db.Integer, nullable=True,
        comment="Étape validation modification in-plan (111: 1=L1, 2=corporate; 101: 2=corporate)"
    )

    plan = db.relationship(
        "CsrPlan",
        backref=db.backref("csr_activities", lazy="dynamic"),
        foreign_keys=[plan_id],
    )
    category = db.relationship("Category", backref=db.backref("csr_activities", lazy="dynamic"))
    external_partner = db.relationship(
        "ExternalPartner",
        foreign_keys=[external_partner_id],
        backref=db.backref("csr_activities", lazy="dynamic"),
    )
