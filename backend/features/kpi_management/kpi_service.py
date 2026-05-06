from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from sqlalchemy import func

from core import db
from models import (
    ActivityKpi,
    CsrActivity,
    CsrCompletedObjective,
    CsrObjective,
    RealizedCsr,
)


def _to_float(value: Optional[Any]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_rate(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 2)


def _as_int(value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compute_lifecycle_status(
    activity: CsrActivity,
    total_realization_count: int,
    published_realization_count: int,
) -> str:
    """DRAFT / PLANNED / PENDING / COMPLETED — execution lifecycle for lists and dashboards.

    When the **annual plan** is approved (VALIDATED or LOCKED), line workflow DRAFT is ignored:

      - At least one **realization row** (any status) → **COMPLETED** (saisie / données soumises),
        including activities that were only PLANNED or PENDING by year alone.
      - Otherwise, by **plan year** vs current year: past → COMPLETED, current → PENDING, future → PLANNED.

    Before approval (plan DRAFT, or plan SUBMITTED/REJECTED, etc.), lifecycle follows line workflow
    and realization rows as before.
    """
    plan = getattr(activity, "plan", None)
    act_st = (getattr(activity, "status", None) or "").upper()
    plan_st = (getattr(plan, "status", None) or "").upper() if plan else ""

    if plan is None:
        return "PLANNED"

    if plan_st == "DRAFT":
        return "DRAFT"

    approved_plan = plan_st in ("VALIDATED", "LOCKED")
    if approved_plan:
        if total_realization_count > 0:
            return "COMPLETED"
        plan_year = getattr(plan, "year", None)
        current_year = date.today().year
        if plan_year is None:
            return "PLANNED"
        if plan_year < current_year:
            return "COMPLETED"
        if plan_year == current_year:
            return "PENDING"
        return "PLANNED"

    if act_st == "DRAFT":
        return "DRAFT"
    if published_realization_count > 0:
        return "COMPLETED"
    if total_realization_count > 0 and published_realization_count == 0:
        return "DRAFT"
    current_year = date.today().year
    plan_year = getattr(plan, "year", None)
    if plan_year is not None and plan_year >= current_year:
        return "PENDING"
    return "PLANNED"


def activity_kpi_to_json(activity_id: str) -> Optional[Dict[str, Any]]:
    k = ActivityKpi.query.filter_by(activity_id=activity_id).first()
    if not k:
        return None
    realized_rows_count = (
        db.session.query(func.count(RealizedCsr.id)).filter(RealizedCsr.activity_id == activity_id).scalar() or 0
    )
    return {
        "has_realized_data": realized_rows_count > 0,
        "lifecycle_status": k.lifecycle_status,
        "incidents_count": k.incidents_count,
        "participants_actual_sum": k.participants_actual_sum,
        "employees_planned": k.employees_planned,
        "involvement_rate": _to_float(k.involvement_rate),
        "announced_objectives_count": k.announced_objectives_count,
        "completed_objectives_count": k.completed_objectives_count,
        "action_delivery_rate": _to_float(k.action_delivery_rate),
        "realized_budget_sum": _to_float(k.realized_budget_sum),
        "planned_budget_amount": _to_float(k.planned_budget_amount),
        "budget_control_rate": _to_float(k.budget_control_rate),
        "plan_total_hc": k.plan_total_hc,
        "participants_vs_total_hc_rate": _to_float(k.participants_vs_total_hc_rate),
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


def recompute_activity_kpi(activity_id: str) -> None:
    activity = CsrActivity.query.options(db.joinedload(CsrActivity.plan)).filter_by(id=activity_id).first()
    if not activity:
        ActivityKpi.query.filter_by(activity_id=activity_id).delete(synchronize_session=False)
        return

    participants_sum_raw, incidents_sum_raw, realized_budget_sum_raw, realization_count_raw = (
        db.session.query(
            func.coalesce(func.sum(RealizedCsr.participants), 0),
            func.coalesce(func.sum(RealizedCsr.incidents_number), 0),
            func.coalesce(func.sum(RealizedCsr.realized_budget), 0),
            func.count(RealizedCsr.id),
        )
        .filter(RealizedCsr.activity_id == activity.id)
        .first()
    )

    announced_count = (
        db.session.query(func.count(CsrObjective.id))
        .filter(CsrObjective.activity_id == activity.id)
        .scalar()
        or 0
    )
    completed_count = (
        db.session.query(func.count(CsrCompletedObjective.id))
        .filter(
            CsrCompletedObjective.activity_id == activity.id,
            CsrCompletedObjective.achieved.is_(True),
        )
        .scalar()
        or 0
    )

    participants_sum = _as_int(participants_sum_raw) or 0
    incidents_sum = _as_int(incidents_sum_raw) or 0
    realized_budget_sum = _to_float(realized_budget_sum_raw) or 0.0
    employees_planned = _as_int(getattr(activity, "employees_planned", None))
    planned_budget = _to_float(getattr(activity, "planned_budget", None))
    plan_total_hc = _as_int(getattr(activity.plan, "total_hc", None) if activity.plan else None)

    involvement_rate = _safe_rate(float(participants_sum), float(employees_planned)) if employees_planned else None
    action_delivery_rate = _safe_rate(float(completed_count), float(announced_count)) if announced_count else None
    budget_control_rate = _safe_rate(realized_budget_sum, planned_budget) if planned_budget else None
    participants_vs_total_hc_rate = _safe_rate(float(participants_sum), float(plan_total_hc)) if plan_total_hc else None

    total_realization_count = int(realization_count_raw or 0)
    published_realization_count = (
        db.session.query(func.count(RealizedCsr.id))
        .filter(RealizedCsr.activity_id == activity.id, RealizedCsr.status != "DRAFT")
        .scalar()
        or 0
    )
    lifecycle_status = compute_lifecycle_status(
        activity,
        total_realization_count,
        int(published_realization_count),
    )

    row = ActivityKpi.query.filter_by(activity_id=activity.id).first()
    if not row:
        row = ActivityKpi(activity_id=activity.id, plan_id=activity.plan_id)
        db.session.add(row)

    row.plan_id = activity.plan_id
    row.incidents_count = incidents_sum
    row.participants_actual_sum = participants_sum
    row.employees_planned = employees_planned
    row.involvement_rate = involvement_rate
    row.announced_objectives_count = announced_count
    row.completed_objectives_count = completed_count
    row.action_delivery_rate = action_delivery_rate
    row.realized_budget_sum = realized_budget_sum
    row.planned_budget_amount = planned_budget
    row.budget_control_rate = budget_control_rate
    row.plan_total_hc = plan_total_hc
    row.participants_vs_total_hc_rate = participants_vs_total_hc_rate
    row.lifecycle_status = lifecycle_status


def recompute_plan_activity_kpis(plan_id: str) -> None:
    activity_ids = [
        row[0]
        for row in db.session.query(CsrActivity.id).filter(CsrActivity.plan_id == plan_id).all()
    ]
    for activity_id in activity_ids:
        recompute_activity_kpi(activity_id)


def ensure_plan_activity_kpis(plan_id: str) -> bool:
    """Recompute KPI rows for all activities in the plan if any snapshot row is missing.

    Returns True if a recompute was run (caller should commit).
    """
    activity_ids = [
        row[0]
        for row in db.session.query(CsrActivity.id).filter(CsrActivity.plan_id == plan_id).all()
    ]
    if not activity_ids:
        return False
    existing = {
        row[0]
        for row in db.session.query(ActivityKpi.activity_id)
        .filter(ActivityKpi.activity_id.in_(activity_ids))
        .all()
    }
    stale_lifecycle = (
        db.session.query(ActivityKpi.id)
        .filter(
            ActivityKpi.activity_id.in_(activity_ids),
            ActivityKpi.lifecycle_status.is_(None),
        )
        .first()
    )
    if len(existing) >= len(activity_ids) and not stale_lifecycle:
        return False
    recompute_plan_activity_kpis(plan_id)
    return True

