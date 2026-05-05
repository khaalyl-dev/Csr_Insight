"""
Effective lifecycle status for planned CSR activities (same rules as the REST API).

The column ``planned_activity.status`` is mainly the **workflow / change-request** state
(DRAFT, SUBMITTED, etc.). When the parent plan is VALIDATED or LOCKED, the product also
exposes a derived **effective** status (PLANNED / IN_PROGRESS / COMPLETED, UNDER_REVIEW, …)
for list views and analytics. Use this module so chatbot and API stay aligned.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_

from models import ChangeRequest, CsrActivity, CsrPlan


def build_cr_effective_context(activities: List[CsrActivity]) -> Dict[str, Any]:
    """Batch-load change requests for :func:`effective_planned_activity_status` (list views)."""
    activity_ids = [a.id for a in activities if getattr(a, "id", None)]
    plan_ids = list({a.plan_id for a in activities if getattr(a, "plan_id", None)})
    pending_activity_ids: set = set()
    pending_plan_ids: set = set()
    latest_activity_cr_status: Dict[str, str] = {}
    conds = []
    if activity_ids:
        conds.append(and_(ChangeRequest.entity_type == "ACTIVITY", ChangeRequest.entity_id.in_(activity_ids)))
    if plan_ids:
        conds.append(and_(ChangeRequest.entity_type == "PLAN", ChangeRequest.entity_id.in_(plan_ids)))
    if conds:
        for cr in ChangeRequest.query.filter(ChangeRequest.status == "PENDING", or_(*conds)).all():
            if cr.entity_type == "ACTIVITY":
                pending_activity_ids.add(cr.entity_id)
            elif cr.entity_type == "PLAN":
                pending_plan_ids.add(cr.entity_id)
    if activity_ids:
        for cr in (
            ChangeRequest.query.filter(
                ChangeRequest.entity_type == "ACTIVITY",
                ChangeRequest.entity_id.in_(activity_ids),
            )
            .order_by(ChangeRequest.created_at.desc())
            .all()
        ):
            if cr.entity_id not in latest_activity_cr_status:
                latest_activity_cr_status[cr.entity_id] = cr.status
    return {
        "pending_activity_ids": pending_activity_ids,
        "pending_plan_ids": pending_plan_ids,
        "latest_activity_cr_status": latest_activity_cr_status,
    }


def effective_planned_activity_status(
    a: CsrActivity,
    plan: Optional[CsrPlan],
    cr_ctx: Dict[str, Any],
    today: Optional[date] = None,
) -> str:
    """
    When the annual plan is VALIDATED or LOCKED:
    - Past plan year → COMPLETED; current year → IN_PROGRESS; future year → PLANNED
    - Pending change request on the plan or this activity → UNDER_REVIEW
    - Activity awaiting corporate / L1 validation (SUBMITTED) → UNDER_REVIEW
    - Rejected modification workflow or latest activity change request REJECTED → REJECTED
    Otherwise returns the stored activity status (workflow / draft plans).
    """
    if not plan:
        return (a.status or "DRAFT").upper()
    ps = (plan.status or "").upper()
    if ps not in ("VALIDATED", "LOCKED"):
        return (a.status or "DRAFT").upper()
    raw = (a.status or "DRAFT").upper()
    if raw == "CANCELLED":
        return "CANCELLED"
    if plan.id in cr_ctx.get("pending_plan_ids", set()):
        return "UNDER_REVIEW"
    if a.id in cr_ctx.get("pending_activity_ids", set()):
        return "UNDER_REVIEW"
    if raw == "SUBMITTED":
        return "UNDER_REVIEW"
    if raw == "REJECTED":
        return "REJECTED"
    latest = cr_ctx.get("latest_activity_cr_status", {}).get(a.id)
    if latest == "REJECTED":
        return "REJECTED"
    cy = (today or date.today()).year
    py = int(plan.year)
    if py < cy:
        return "COMPLETED"
    if py == cy:
        return "IN_PROGRESS"
    return "PLANNED"
