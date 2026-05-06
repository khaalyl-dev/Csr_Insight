import uuid

from sqlalchemy import CHAR

from core.db import db


def _uuid_default():
    return str(uuid.uuid4())


class ActivityKpi(db.Model):
    __tablename__ = "activity_kpis"
    __table_args__ = (
        db.UniqueConstraint("activity_id", name="uq_activity_kpis_activity_id"),
        db.Index("ix_activity_kpis_plan_id", "plan_id"),
        {
            "comment": "KPIs persistes par activite CSR",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_unicode_ci",
        },
    )

    id = db.Column(CHAR(36, collation="utf8mb4_unicode_ci"), primary_key=True, default=_uuid_default)
    plan_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        db.ForeignKey("csr_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id = db.Column(
        CHAR(36, collation="utf8mb4_unicode_ci"),
        db.ForeignKey("planned_activity.id", ondelete="CASCADE"),
        nullable=False,
    )

    incidents_count = db.Column(db.Integer, nullable=True)
    participants_actual_sum = db.Column(db.Integer, nullable=True)
    employees_planned = db.Column(db.Integer, nullable=True)
    involvement_rate = db.Column(db.Numeric(8, 2), nullable=True)

    announced_objectives_count = db.Column(db.Integer, nullable=True)
    completed_objectives_count = db.Column(db.Integer, nullable=True)
    action_delivery_rate = db.Column(db.Numeric(8, 2), nullable=True)

    realized_budget_sum = db.Column(db.Numeric(15, 2), nullable=True)
    planned_budget_amount = db.Column(db.Numeric(15, 2), nullable=True)
    budget_control_rate = db.Column(db.Numeric(8, 2), nullable=True)

    plan_total_hc = db.Column(db.Integer, nullable=True)
    participants_vs_total_hc_rate = db.Column(db.Numeric(8, 2), nullable=True)

    # Execution bucket for lists (distinct from line/plan workflow status).
    # When annual plan is VALIDATED/LOCKED: any realization row → COMPLETED; else year vs current year
    # (past / current / future → COMPLETED / PENDING / PLANNED). Before approval: see kpi_service.
    lifecycle_status = db.Column(db.String(20), nullable=True)

    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

