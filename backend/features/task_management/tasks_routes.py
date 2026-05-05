"""
Aggregated actionable tasks for the current user (no extra DB table).
Uses the same permission rules as plan/activity/change-request flows.
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from core import token_required
from models import ChangeRequest, CsrActivity, CsrPlan, UserSite
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from features.change_request_management.change_requests_routes import (
    activity_has_off_plan_realization_sql,
    _change_request_awaiting_corporate_unlock,
    _in_plan_mod_awaits_corporate_validation,
    _level1_validation_step_pending,
    _off_plan_awaits_corporate_validation,
    _user_has_grade,
)
from features.csr_plan_management.csr_plans_routes import (
    _compute_can_approve,
    _plan_is_editable,
    _user_can_access_site,
)
from features.planned_activity_management.planned_csr_routes import _activity_is_editable, _compose_activity_number

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _norm_role() -> str:
    return (getattr(request, "role", "") or "").upper()


def _site_allowed_ids(user_id: str) -> list[str]:
    rows = UserSite.query.filter_by(user_id=user_id, is_active=True).all()
    return [r.site_id for r in rows if r.site_id]


def _site_grade_allows_contributor_tasks(user_id: str, site_id: str) -> bool:
    """Draft / rejected / resubmit / unlock-window work for site contributors (L0, L1, or unset grade)."""
    us = UserSite.query.filter_by(user_id=user_id, site_id=site_id, is_active=True).first()
    if not us:
        return False
    g = (us.grade or "").strip().lower()
    return g in ("level_0", "level_1", "")


def _corporate_pending_change_inbox_non_empty() -> bool:
    """Any unlock request or activity validation waiting on corporate (same rules as /changes?status=PENDING)."""
    for cr in ChangeRequest.query.filter(ChangeRequest.status == "PENDING").limit(400).all():
        if _change_request_awaiting_corporate_unlock(cr):
            return True
    q = (
        CsrActivity.query.join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
        .filter(
            CsrActivity.status == "SUBMITTED",
            or_(
                activity_has_off_plan_realization_sql,
                and_(~activity_has_off_plan_realization_sql, CsrPlan.status == "VALIDATED"),
            ),
        )
        .limit(800)
    )
    for a in q.all():
        if _off_plan_awaits_corporate_validation(a) or _in_plan_mod_awaits_corporate_validation(a):
            return True
    return False


def _l1_pending_change_inbox_non_empty(user_id: str, allowed_site_ids: list[str]) -> bool:
    """L1 validation inbox: unlock CRs at step 1 + activities awaiting site L1 (same as /changes/pending for L1)."""
    for site_id in allowed_site_ids:
        if not _user_has_grade(user_id, site_id, "level_1"):
            continue
        if (
            ChangeRequest.query.filter(
                ChangeRequest.site_id == site_id,
                ChangeRequest.status == "PENDING",
                ChangeRequest.validation_mode == "111",
                or_(
                    ChangeRequest.validation_step == 1,
                    ChangeRequest.validation_step.is_(None),
                ),
            ).first()
        ):
            return True
        acts = (
            CsrActivity.query.join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(
                CsrPlan.site_id == site_id,
                CsrActivity.status == "SUBMITTED",
                or_(
                    activity_has_off_plan_realization_sql,
                    and_(~activity_has_off_plan_realization_sql, CsrPlan.status == "VALIDATED"),
                ),
            )
            .all()
        )
        for a in acts:
            if _level1_validation_step_pending(a):
                return True
    return False


def _append(tasks: list[dict], task_id: str, kind: str, href: str, meta: dict | None = None) -> None:
    if any(t["id"] == task_id for t in tasks):
        return
    tasks.append(
        {
            "id": task_id,
            "kind": kind,
            "href": href,
            "meta": meta or {},
        }
    )


# Lower sorts first — surface rejections so site users fix plans/activities quickly.
_TASK_KIND_PRIORITY = {
    "FIX_REJECTED_PLAN": 0,
    "RESUBMIT_ACTIVITY": 1,
    "EDIT_UNLOCKED_ACTIVITY": 1,
    "EDIT_UNLOCKED_PLAN": 1,
    "EDIT_PLAN_DRAFT": 2,
    "APPROVE_PLAN": 3,
    "REVIEW_PENDING_CHANGES": 4,
}


@bp.get("")
@token_required
def list_tasks():
    """Return tasks the current user can act on (role- and grade-aware)."""
    user_id = request.user_id
    role = _norm_role()
    tasks: list[dict] = []

    if role in ("CORPORATE_USER", "CORPORATE"):
        plans_sub = (
            CsrPlan.query.options(joinedload(CsrPlan.site))
            .filter(CsrPlan.status == "SUBMITTED")
            .all()
        )
        for plan in plans_sub:
            if _compute_can_approve(plan, user_id, role):
                site = plan.site
                _append(
                    tasks,
                    f"approve-plan-{plan.id}",
                    "APPROVE_PLAN",
                    f"/csr-plans/{plan.id}",
                    {
                        "site_name": site.name if site else None,
                        "site_code": site.code if site else None,
                        "year": plan.year,
                    },
                )

        if _corporate_pending_change_inbox_non_empty():
            _append(
                tasks,
                "corporate-pending-changes",
                "REVIEW_PENDING_CHANGES",
                "/changes/pending",
                {},
            )

        n = len(tasks)
        return jsonify({"tasks": tasks[:80], "count": n}), 200

    # SITE_USER / SITE
    if role not in ("SITE_USER", "SITE"):
        return jsonify({"tasks": [], "count": 0}), 200

    allowed = _site_allowed_ids(user_id)
    if not allowed:
        return jsonify({"tasks": [], "count": 0}), 200

    plans = (
        CsrPlan.query.options(joinedload(CsrPlan.site))
        .filter(CsrPlan.site_id.in_(allowed))
        .all()
    )

    now = datetime.utcnow()

    for plan in plans:
        if plan.status == "REJECTED" and _plan_is_editable(plan, role):
            if _user_can_access_site(user_id, plan.site_id) and _site_grade_allows_contributor_tasks(
                user_id, plan.site_id
            ):
                site = plan.site
                _append(
                    tasks,
                    f"fix-rejected-plan-{plan.id}",
                    "FIX_REJECTED_PLAN",
                    f"/csr-plans/{plan.id}",
                    {
                        "site_name": site.name if site else None,
                        "year": plan.year,
                        "status": plan.status,
                    },
                )

        if plan.status == "DRAFT" and _plan_is_editable(plan, role):
            if _user_can_access_site(user_id, plan.site_id) and _site_grade_allows_contributor_tasks(
                user_id, plan.site_id
            ):
                site = plan.site
                _append(
                    tasks,
                    f"edit-plan-{plan.id}",
                    "EDIT_PLAN_DRAFT",
                    f"/csr-plans/{plan.id}",
                    {
                        "site_name": site.name if site else None,
                        "year": plan.year,
                        "status": plan.status,
                    },
                )

        unlock_until = getattr(plan, "unlock_until", None)
        if (
            plan.status == "VALIDATED"
            and unlock_until
            and unlock_until > now
            and _plan_is_editable(plan, role)
            and _user_can_access_site(user_id, plan.site_id)
            and _site_grade_allows_contributor_tasks(user_id, plan.site_id)
        ):
            site = plan.site
            _append(
                tasks,
                f"edit-unlocked-plan-{plan.id}",
                "EDIT_UNLOCKED_PLAN",
                f"/csr-plans/{plan.id}",
                {
                    "site_name": site.name if site else None,
                    "year": plan.year,
                    "status": plan.status,
                },
            )

        if plan.status == "SUBMITTED" and _compute_can_approve(plan, user_id, role):
            site = plan.site
            _append(
                tasks,
                f"approve-plan-{plan.id}",
                "APPROVE_PLAN",
                f"/csr-plans/{plan.id}",
                {
                    "site_name": site.name if site else None,
                    "year": plan.year,
                },
            )

    activities = (
        CsrActivity.query.options(
            joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
        )
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
        .filter(CsrPlan.site_id.in_(allowed))
        .filter(CsrActivity.status == "REJECTED")
        .all()
    )

    for a in activities:
        plan = a.plan
        if not plan:
            continue
        if not _user_can_access_site(user_id, plan.site_id):
            continue

        if a.status == "REJECTED" and _activity_is_editable(a, role):
            if not _site_grade_allows_contributor_tasks(user_id, plan.site_id):
                continue
            site = plan.site
            _append(
                tasks,
                f"resubmit-activity-{a.id}",
                "RESUBMIT_ACTIVITY",
                f"/planned-activity/{a.id}/edit",
                {
                    "activity_number": _compose_activity_number(plan, a.activity_number),
                    "activity_title": a.title,
                    "site_name": site.name if site else None,
                    "year": plan.year,
                    "plan_id": plan.id,
                },
            )

    activities_unlocked = (
        CsrActivity.query.options(
            joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
        )
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
        .filter(CsrPlan.site_id.in_(allowed))
        .filter(CsrActivity.unlock_until.isnot(None))
        .filter(CsrActivity.unlock_until > now)
        .all()
    )
    for a in activities_unlocked:
        plan = a.plan
        if not plan:
            continue
        if not _user_can_access_site(user_id, plan.site_id):
            continue
        if not _site_grade_allows_contributor_tasks(user_id, plan.site_id):
            continue
        if not _activity_is_editable(a, role):
            continue
        # Rejected rows already use RESUBMIT_ACTIVITY above.
        if a.status == "REJECTED":
            continue
        site = plan.site
        _append(
            tasks,
            f"edit-unlocked-activity-{a.id}",
            "EDIT_UNLOCKED_ACTIVITY",
            f"/csr-plans/{plan.id}?editActivity={a.id}",
            {
                "activity_number": _compose_activity_number(plan, a.activity_number),
                "activity_title": a.title,
                "site_name": site.name if site else None,
                "year": plan.year,
                "plan_id": plan.id,
            },
        )

    if _l1_pending_change_inbox_non_empty(user_id, allowed):
        _append(
            tasks,
            "site-pending-changes",
            "REVIEW_PENDING_CHANGES",
            "/changes/pending",
            {},
        )

    tasks.sort(
        key=lambda t: (
            _TASK_KIND_PRIORITY.get(t["kind"], 99),
            -(t.get("meta", {}).get("year") or 0),
            t["id"],
        )
    )
    n = len(tasks)
    return jsonify({"tasks": tasks[:80], "count": n}), 200
