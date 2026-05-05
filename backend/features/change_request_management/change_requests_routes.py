"""
Change requests endpoints.
- Create: site user with access to plan can request change (plan must be VALIDATED).
- List: site user sees change requests for their sites submitted by level_0 / level_1 (or unset grade)
  on that site, plus matching off-plan activity rows; corporate sees all or by status.
- Approve/Reject: corporate only. On approve, plan stays VALIDATED (verrouillé); unlock_until is set so it is temporarily editable.
"""
import re
from typing import Optional

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import aliased, joinedload
from core import db, token_required, role_required
from core.user_avatar import user_avatar_serve_url, user_avatar_serve_url_for_id
from models import AuditLog, ChangeRequest, CsrActivity, CsrPlan, Document, UserSite, User, RealizedCsr, Validation
from features.notification_management.notification_helper import notify_corporate, notify_site_users, notify_user
from features.notification_management.socketio_emit import (
    emit_tasks_refresh_for_request_actor,
    emit_tasks_updated_for_site_contributors,
)
from features.audit_history_management.audit_helper import write_audit

bp = Blueprint("change_requests", __name__, url_prefix="/api/change-requests")

# Off-plan flag moved from planned_activity to realized_activity (RealizedCsr.is_off_plan).
activity_has_off_plan_realization_sql = exists().where(
    and_(
        RealizedCsr.activity_id == CsrActivity.id,
        RealizedCsr.is_off_plan.is_(True),
    )
)


def _step_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _activity_has_off_plan_realization(activity: CsrActivity) -> bool:
    if not activity or not activity.id:
        return False
    return (
        db.session.query(RealizedCsr.id)
        .filter(RealizedCsr.activity_id == activity.id, RealizedCsr.is_off_plan.is_(True))
        .first()
        is not None
    )


def _compose_activity_number(activity: Optional[CsrActivity]) -> str:
    if not activity:
        return ""
    base = (getattr(activity, "activity_number", None) or "").strip()
    plan = getattr(activity, "plan", None)
    if not base or not plan or not getattr(plan, "site", None) or not getattr(plan, "year", None):
        return base
    site_code = (getattr(plan.site, "code", "") or "").strip().upper()
    year = str(getattr(plan, "year", "")).strip()
    if not site_code or not year:
        return base
    prefix = f"{site_code}-{year}-"
    if base.upper().startswith(prefix):
        return base
    m = re.match(r"^[^-]+-\d{4}-(.+)$", base)
    if m:
        base = (m.group(1) or "").strip()
    return f"{prefix}{base}"


def _latest_off_plan_realization(activity: CsrActivity) -> Optional[RealizedCsr]:
    if not activity or not activity.id:
        return None
    return (
        RealizedCsr.query.filter_by(activity_id=activity.id, is_off_plan=True)
        .order_by(RealizedCsr.created_at.desc())
        .first()
    )


def _off_plan_validation_mode_for_json(activity: CsrActivity):
    r = _latest_off_plan_realization(activity)
    if r:
        return getattr(r, "off_plan_validation_mode", None)
    return getattr(activity, "off_plan_validation_mode", None)


def _user_can_access_site(user_id: str, site_id: str) -> bool:
    us = UserSite.query.filter_by(user_id=user_id, site_id=site_id, is_active=True).first()
    return us is not None


def _user_has_grade(user_id: str, site_id: str, grade: str) -> bool:
    us = UserSite.query.filter_by(
        user_id=user_id,
        site_id=site_id,
        is_active=True,
        grade=grade,
    ).first()
    return us is not None


def _user_has_any_grade(user_id: str, grade: str) -> bool:
    us = UserSite.query.filter_by(
        user_id=user_id,
        is_active=True,
        grade=grade,
    ).first()
    return us is not None


def _cr_plan_validation_mode(plan: CsrPlan) -> str:
    """Normalized plan.validation_mode (101/111); avoids importing csr_plans_routes (import cycle)."""
    raw = getattr(plan, "validation_mode", None)
    m = str(raw if raw is not None else "101").strip()
    return m if m in ("101", "111") else "101"


def _normalize_body_validation_mode(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s in ("101", "111") else None


def _off_plan_activity_validation_mode(activity: CsrActivity, r: Optional[RealizedCsr], plan: CsrPlan) -> str:
    """Mode 101/111 for off-plan flow: realization row first, then plan.validation_mode."""
    raw = getattr(r, "off_plan_validation_mode", None) if r is not None else None
    if raw is None or not str(raw).strip():
        raw = _cr_plan_validation_mode(plan)
    m = str(raw).strip()
    return m if m in ("101", "111") else "101"


def _change_request_awaiting_corporate_unlock(cr: ChangeRequest) -> bool:
    """True if corporate is the next actor for this pending unlock request."""
    if cr.status != "PENDING":
        return False
    vm = str(getattr(cr, "validation_mode", None) or "").strip()
    if vm == "111" and _step_int(getattr(cr, "validation_step", None)) != 2:
        # Étape site (1 ou NULL si non persisté) — pas encore au corporate
        return False
    return True


def _site_requester_is_level_0_or_1(requester_user_id: str, site_id: str) -> bool:
    """True if requester has active UserSite on site with grade level_0, level_1, or unset/empty."""
    us = UserSite.query.filter_by(
        user_id=requester_user_id, site_id=site_id, is_active=True
    ).first()
    if not us:
        return False
    g = (us.grade or "").strip().lower()
    return g in ("level_0", "level_1", "")


def _change_request_to_json(cr: ChangeRequest, include_documents=False):
    out = {
        "id": cr.id,
        "site_id": cr.site_id,
        "site_name": cr.site.name if cr.site else None,
        "entity_type": cr.entity_type,
        "entity_id": cr.entity_id,
        "year": cr.year,
        "reason": cr.reason,
        "status": cr.status,
        "requested_by": cr.requested_by,
        "requested_by_name": f"{cr.requester.first_name} {cr.requester.last_name}" if cr.requester else None,
        "requested_by_avatar_url": user_avatar_serve_url(cr.requester) if cr.requester else None,
        "requested_duration": cr.requested_duration,
        "reviewed_by": cr.reviewed_by,
        "reviewed_by_name": f"{cr.reviewer.first_name} {cr.reviewer.last_name}" if cr.reviewer else None,
        "reviewed_by_avatar_url": user_avatar_serve_url(cr.reviewer) if cr.reviewer else None,
        "reviewed_at": cr.reviewed_at.isoformat() if cr.reviewed_at else None,
        "created_at": cr.created_at.isoformat() if cr.created_at else None,
        "validation_mode": getattr(cr, "validation_mode", None),
        "validation_step": getattr(cr, "validation_step", None),
    }
    if include_documents:
        docs = Document.query.filter_by(change_request_id=cr.id).order_by(Document.uploaded_at.asc()).all()
        out["documents"] = [
            {
                "id": d.id,
                "file_name": d.file_name,
                "file_path": d.file_path,
                "file_type": d.file_type_upper if hasattr(d, "file_type_upper") else (d.file_type or ""),
                "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            }
            for d in docs
        ]
    # Plan summary when entity_type is PLAN
    if cr.entity_type == "PLAN" and cr.entity_id:
        plan = CsrPlan.query.get(cr.entity_id)
        if plan:
            out["plan_site_name"] = plan.site.name if plan.site else None
            out["plan_year"] = plan.year
    # Activity summary when entity_type is ACTIVITY
    if cr.entity_type == "ACTIVITY" and cr.entity_id:
        activity = CsrActivity.query.get(cr.entity_id)
        if activity and activity.plan:
            out["plan_site_name"] = activity.plan.site.name if activity.plan.site else None
            out["plan_year"] = activity.plan.year
            out["plan_id"] = activity.plan_id
            out["activity_title"] = activity.title or ""
            out["activity_number"] = activity.activity_number or ""
    return out


def _corporate_validation_step_pending(activity: CsrActivity) -> bool:
    """True if activity is SUBMITTED and the next validator is corporate (mode 101, or 111 with step 2)."""
    if not activity or activity.status != "SUBMITTED":
        return False
    if _activity_has_off_plan_realization(activity):
        r = _latest_off_plan_realization(activity)
        if not r:
            return False
        plan = activity.plan
        if not plan:
            return False
        mode = _off_plan_activity_validation_mode(activity, r, plan)
        step = _step_int(getattr(r, "off_plan_validation_step", None))
        if mode == "111":
            if step == 2:
                return True
            if step == 1:
                return False
            v1 = Validation.query.filter_by(
                entity_type="ACTIVITY", entity_id=activity.id, grade="level_1", status="PENDING"
            ).first()
            if v1 is not None:
                return False
            v2 = Validation.query.filter_by(
                entity_type="ACTIVITY", entity_id=activity.id, grade="level_2", status="PENDING"
            ).first()
            return v2 is not None
        return True
    plan = activity.plan
    if not plan or plan.status != "VALIDATED":
        return False
    mode = getattr(activity, "off_plan_validation_mode", None) or getattr(plan, "validation_mode", None) or "101"
    mode = str(mode).strip()
    if mode not in ("101", "111"):
        mode = "101"
    step = _step_int(getattr(activity, "off_plan_validation_step", None))
    if mode == "111":
        if step == 2:
            return True
        if step == 1:
            return False
        v1 = Validation.query.filter_by(
            entity_type="ACTIVITY", entity_id=activity.id, grade="level_1", status="PENDING"
        ).first()
        if v1 is not None:
            return False
        v2 = Validation.query.filter_by(
            entity_type="ACTIVITY", entity_id=activity.id, grade="level_2", status="PENDING"
        ).first()
        return v2 is not None
    return True


def _activity_has_pending_level1_validation(activity_id: str) -> bool:
    """True if a level_1 ACTIVITY validation row is still PENDING (source of truth for L1 inbox)."""
    return (
        Validation.query.filter_by(
            entity_type="ACTIVITY",
            entity_id=activity_id,
            grade="level_1",
            status="PENDING",
        ).first()
        is not None
    )


def _level1_validation_step_pending(activity: CsrActivity) -> bool:
    """True if activity is SUBMITTED and the next validator is level 1 (mode 111 step 1)."""
    if not activity or activity.status != "SUBMITTED":
        return False
    if _activity_has_off_plan_realization(activity):
        r = _latest_off_plan_realization(activity)
        if not r:
            return False
        plan = activity.plan
        if not plan:
            return False
        mode = _off_plan_activity_validation_mode(activity, r, plan)
        step = _step_int(getattr(r, "off_plan_validation_step", None))
        if mode == "111" and step == 1:
            return _activity_has_pending_level1_validation(activity.id)
        if mode == "111" and step is None:
            return _activity_has_pending_level1_validation(activity.id)
        return False
    plan = activity.plan
    if not plan or plan.status != "VALIDATED":
        return False
    mode = getattr(activity, "off_plan_validation_mode", None) or getattr(plan, "validation_mode", None) or "101"
    mode = str(mode).strip()
    if mode not in ("101", "111"):
        mode = "101"
    step = _step_int(getattr(activity, "off_plan_validation_step", None))
    if mode == "111" and step == 1:
        return _activity_has_pending_level1_validation(activity.id)
    if mode == "111" and step is None:
        return _activity_has_pending_level1_validation(activity.id)
    return False


def _off_plan_awaits_level1_validation(activity: CsrActivity) -> bool:
    """True if this off-plan activity is SUBMITTED and awaits level 1 validation."""
    if not activity or not _activity_has_off_plan_realization(activity):
        return False
    return _level1_validation_step_pending(activity)


def _off_plan_awaits_corporate_validation(activity: CsrActivity) -> bool:
    """True if this off-plan activity is SUBMITTED and the next step is corporate (mode 101, or 111 after L1)."""
    if not activity or not _activity_has_off_plan_realization(activity):
        return False
    return _corporate_validation_step_pending(activity)


def _in_plan_mod_awaits_corporate_validation(activity: CsrActivity) -> bool:
    """True if an in-plan activity was submitted for modification review and awaits corporate (same step rules as off-plan)."""
    if not activity or _activity_has_off_plan_realization(activity):
        return False
    plan = activity.plan
    if not plan or plan.status != "VALIDATED":
        return False
    return _corporate_validation_step_pending(activity)


def _pending_off_plan_corporate_item(activity: CsrActivity) -> dict:
    plan = activity.plan
    site = plan.site if plan else None
    requester_name = None
    realized = (
        RealizedCsr.query.filter_by(activity_id=activity.id)
        .order_by(RealizedCsr.created_at.desc())
        .first()
    )
    if realized and getattr(realized, "created_by", None):
        u = User.query.get(realized.created_by)
        if u:
            requester_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or None
    rid = (realized.created_by if realized else None) or ""
    # Synthetic list id (not a DB row); avoids colliding with change_requests.id UUIDs.
    synthetic_id = f"off-plan-{activity.id}"
    return {
        "pending_item_type": "OFF_PLAN_ACTIVITY",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": "Activité hors plan — validation corporate en attente.",
        "requested_by_name": requester_name,
        "requested_by": rid,
        "requested_by_avatar_url": user_avatar_serve_url_for_id(rid),
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
        "off_plan_validation_mode": _off_plan_validation_mode_for_json(activity),
    }


def _pending_off_plan_level1_item(activity: CsrActivity) -> dict:
    plan = activity.plan
    site = plan.site if plan else None
    requester_name = None
    realized = (
        RealizedCsr.query.filter_by(activity_id=activity.id)
        .order_by(RealizedCsr.created_at.desc())
        .first()
    )
    if realized and getattr(realized, "created_by", None):
        u = User.query.get(realized.created_by)
        if u:
            requester_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or None
    rid = (realized.created_by if realized else None) or ""
    synthetic_id = f"off-plan-l1-{activity.id}"
    return {
        "pending_item_type": "OFF_PLAN_ACTIVITY",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": "Activité hors plan — validation niveau 1 en attente.",
        "requested_by_name": requester_name,
        "requested_by": rid,
        "requested_by_avatar_url": user_avatar_serve_url_for_id(rid),
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
        "off_plan_validation_mode": _off_plan_validation_mode_for_json(activity),
    }


def _in_plan_mod_review_requester(activity: CsrActivity) -> tuple:
    """(user_id, display_name) for who submitted / resubmitted modification review; else responsible_user if set."""
    rid, requester_name = "", None
    log = (
        AuditLog.query.filter(
            AuditLog.entity_type == "ACTIVITY",
            AuditLog.entity_id == activity.id,
            AuditLog.user_id.isnot(None),
            or_(
                AuditLog.description == "Soumission modification activité (plan validé) pour validation",
                AuditLog.description == "Renvoi modification activité (plan validé) pour validation",
            ),
        )
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    if log and log.user_id:
        rid = log.user_id
        u = User.query.get(log.user_id)
        if u:
            requester_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or None
        return rid, requester_name
    if getattr(activity, "responsible_user_id", None):
        u = User.query.get(activity.responsible_user_id)
        if u:
            rid = activity.responsible_user_id
            requester_name = f"{u.first_name or ''} {u.last_name or ''}".strip() or None
    return rid, requester_name


def _pending_in_plan_mod_level1_item(activity: CsrActivity) -> dict:
    plan = activity.plan
    site = plan.site if plan else None
    rid, requester_name = _in_plan_mod_review_requester(activity)
    synthetic_id = f"in-plan-mod-l1-{activity.id}"
    return {
        "pending_item_type": "IN_PLAN_ACTIVITY_MOD",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": "Modification d'activité sur plan validé — validation niveau 1 en attente.",
        "requested_by_name": requester_name,
        "requested_by": rid,
        "requested_by_avatar_url": user_avatar_serve_url_for_id(rid),
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "created_at": activity.updated_at.isoformat() if activity.updated_at else None,
        "off_plan_validation_mode": getattr(activity, "off_plan_validation_mode", None)
        or (getattr(plan, "validation_mode", None) if plan else None),
    }


def _pending_in_plan_mod_corporate_item(activity: CsrActivity) -> dict:
    plan = activity.plan
    site = plan.site if plan else None
    rid, requester_name = _in_plan_mod_review_requester(activity)
    synthetic_id = f"in-plan-mod-{activity.id}"
    return {
        "pending_item_type": "IN_PLAN_ACTIVITY_MOD",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": "Modification d'activité sur plan validé — validation corporate en attente.",
        "requested_by_name": requester_name,
        "requested_by": rid,
        "requested_by_avatar_url": user_avatar_serve_url_for_id(rid),
        "status": "PENDING",
        "reviewed_by": None,
        "reviewed_at": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "created_at": activity.updated_at.isoformat() if activity.updated_at else None,
        "off_plan_validation_mode": getattr(activity, "off_plan_validation_mode", None)
        or (getattr(plan, "validation_mode", None) if plan else None),
    }


def _off_plan_mine_list_item(activity: CsrActivity, user_id: str) -> Optional[dict]:
    """Synthetic row for « Mes demandes » : off-plan activity created by user (via realized_csr.created_by)."""
    st = activity.status
    if st == "SUBMITTED":
        cr_status = "PENDING"
        reason = "Activité hors plan — en attente de validation."
    elif st == "VALIDATED":
        cr_status = "APPROVED"
        reason = "Activité hors plan — validée."
    elif st == "REJECTED":
        cr_status = "REJECTED"
        reason = "Activité hors plan — rejetée (vous pouvez modifier et renvoyer)."
    else:
        return None
    plan = activity.plan
    site = plan.site if plan else None
    u = User.query.get(user_id)
    requester_name = (
        f"{u.first_name or ''} {u.last_name or ''}".strip() if u else None
    ) or None
    synthetic_id = f"off-plan-mine-{activity.id}"
    reviewed_at = None
    if st in ("VALIDATED", "REJECTED") and activity.updated_at:
        reviewed_at = activity.updated_at.isoformat()
    return {
        "pending_item_type": "OFF_PLAN_ACTIVITY",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": reason,
        "requested_by": user_id,
        "requested_by_name": requester_name,
        "requested_by_avatar_url": user_avatar_serve_url(u),
        "requested_duration": None,
        "status": cr_status,
        "reviewed_by": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "reviewed_at": reviewed_at,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
        "off_plan_validation_mode": _off_plan_validation_mode_for_json(activity),
    }


def _in_plan_mod_mine_list_item(activity: CsrActivity, requester_user_id: str) -> Optional[dict]:
    """Synthetic row for « Mes demandes » : modification sur plan validé (soumission après déverrouillage corporate)."""
    st = activity.status
    if st == "SUBMITTED":
        cr_status = "PENDING"
        reason = "Modification activité sur plan validé — en attente de validation."
    elif st == "REJECTED":
        cr_status = "REJECTED"
        reason = "Modification activité sur plan validé — rejetée (vous pouvez modifier et renvoyer)."
    else:
        return None
    plan = activity.plan
    site = plan.site if plan else None
    u = User.query.get(requester_user_id)
    requester_name = (
        f"{u.first_name or ''} {u.last_name or ''}".strip() if u else None
    ) or None
    synthetic_id = f"in-plan-mod-mine-{activity.id}"
    reviewed_at = None
    if st == "REJECTED" and activity.updated_at:
        reviewed_at = activity.updated_at.isoformat()
    return {
        "pending_item_type": "IN_PLAN_ACTIVITY_MOD",
        "id": synthetic_id,
        "activity_id": activity.id,
        "plan_id": activity.plan_id,
        "site_id": plan.site_id if plan else None,
        "site_name": site.name if site else None,
        "plan_site_name": site.name if site else None,
        "plan_year": plan.year if plan else None,
        "year": plan.year if plan else 0,
        "activity_number": _compose_activity_number(activity),
        "activity_title": activity.title or "",
        "entity_type": "ACTIVITY",
        "entity_id": activity.id,
        "reason": reason,
        "requested_by": requester_user_id,
        "requested_by_name": requester_name,
        "requested_by_avatar_url": user_avatar_serve_url(u),
        "requested_duration": None,
        "status": cr_status,
        "reviewed_by": None,
        "reviewed_by_name": None,
        "reviewed_by_avatar_url": None,
        "reviewed_at": reviewed_at,
        "created_at": activity.updated_at.isoformat() if activity.updated_at else None,
        "off_plan_validation_mode": getattr(activity, "off_plan_validation_mode", None)
        or (getattr(plan, "validation_mode", None) if plan else None),
    }


def _parse_duration_days(raw) -> int:
    """Parse requested_duration to number of days. Accepts int or string like '7', '14', '30' or '7 days'."""
    if raw is None:
        return 30
    if isinstance(raw, int) and raw > 0:
        return min(365, max(1, raw))
    s = (str(raw).strip() or "30").lower()
    for part in s.split():
        if part.isdigit():
            return min(365, max(1, int(part)))
    return 30


@bp.post("")
@token_required
def create_change_request():
    """Create a change request for a validated plan or activity. Body: plan_id or activity_id, reason (required), requested_duration (optional, days)."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    plan_id = (data.get("plan_id") or "").strip()
    activity_id = (data.get("activity_id") or "").strip()
    reason = (data.get("reason") or "").strip()
    requested_duration = data.get("requested_duration")
    if not plan_id and not activity_id:
        return jsonify({"message": "plan_id ou activity_id obligatoire"}), 400
    if activity_id and plan_id:
        return jsonify({"message": "Indiquez soit plan_id soit activity_id, pas les deux"}), 400
    if not reason:
        return jsonify({"message": "La justification (reason) est obligatoire"}), 400
    role = (getattr(request, "role", "") or "").upper()
    user_id = request.user_id
    plan = None
    entity_type = "PLAN"
    entity_id = plan_id
    if activity_id:
        activity = CsrActivity.query.get(activity_id)
        if not activity:
            return jsonify({"message": "Activité introuvable"}), 404
        plan = activity.plan
        entity_type = "ACTIVITY"
        entity_id = activity.id
    else:
        plan = CsrPlan.query.get(plan_id)
        if not plan:
            return jsonify({"message": "Plan introuvable"}), 404
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if plan.status != "VALIDATED":
        return jsonify({"message": "Seuls les plans validés peuvent faire l'objet d'une demande de modification"}), 400
    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(user_id, plan.site_id):
            return jsonify({"message": "Vous n'avez pas accès à ce site"}), 403
    pending_same = ChangeRequest.query.filter_by(
        entity_type=entity_type,
        entity_id=entity_id,
        status="PENDING",
    ).first()
    if pending_same:
        msg = (
            "Une demande de déverrouillage est déjà en attente pour cette activité."
            if entity_type == "ACTIVITY"
            else "Une demande de déverrouillage est déjà en attente pour ce plan."
        )
        return jsonify({"message": msg}), 409
    duration_days = _parse_duration_days(requested_duration)
    duration_label = f"{duration_days} jours"
    plan_vm = _cr_plan_validation_mode(plan)
    raw_vm = _normalize_body_validation_mode(data.get("validation_mode"))
    is_site = role in ("SITE_USER", "SITE")
    is_l1 = is_site and _user_has_grade(user_id, plan.site_id, "level_1")
    cr_vm: str
    cr_step: int
    if not is_site:
        cr_vm = raw_vm or plan_vm
        cr_step = 2
    elif is_l1:
        # Demandeur niveau 1 : validation site déjà acquise, suite = corporate uniquement
        cr_vm = raw_vm or plan_vm
        cr_step = 2
    else:
        if not raw_vm:
            return jsonify(
                {
                    "message": (
                        "Indiquez validation_mode : 101 (validation corporate uniquement) ou "
                        "111 (validation niveau 1 du site puis corporate)."
                    )
                }
            ), 400
        cr_vm = raw_vm
        cr_step = 1 if cr_vm == "111" else 2

    cr = ChangeRequest(
        site_id=plan.site_id,
        entity_type=entity_type,
        entity_id=entity_id,
        year=plan.year,
        reason=reason,
        status="PENDING",
        requested_by=user_id,
        requested_duration=duration_label,
        validation_mode=cr_vm,
        validation_step=cr_step,
    )
    db.session.add(cr)
    db.session.flush()
    desc = f"Demande de modification plan {plan.year}" if entity_type == "PLAN" else f"Demande de modification activité {entity_id}: {reason[:150]}"
    write_audit(
        user_id=request.user_id,
        site_id=plan.site_id,
        action="REQUEST_MODIFICATION",
        entity_type=entity_type,
        entity_id=entity_id,
        description=desc,
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    msg = f"Le site {site_name} a demande une modification pour le plan CSR {plan.year}. Motif: {reason}"
    if entity_type == "ACTIVITY":
        act = CsrActivity.query.get(entity_id)
        act_label = f"{act.activity_number} – {act.title}" if act else entity_id
        msg = f"Le site {site_name} a demande une modification pour l'activité {act_label}. Motif: {reason}"
    if cr_vm == "111" and cr_step == 1:
        notify_site_users(
            site_id=plan.site_id,
            title="Demande de déverrouillage — validation niveau 1",
            message=(
                f"Une demande de modification ({entity_type}) pour {site_name}, plan {plan.year}, "
                f"attend la validation niveau 1. Motif: {reason[:200]}"
            ),
            type="warning",
            entity_type="CHANGE_REQUEST",
            entity_id=cr.id,
            notification_category="activity_validation",
        )
    else:
        notify_corporate(
            title="Nouvelle demande de modification",
            message=msg,
            type="warning",
            site_id=plan.site_id,
            entity_type="CHANGE_REQUEST",
            entity_id=cr.id,
            notification_category="activity_validation",
        )

    return jsonify(_change_request_to_json(cr, include_documents=True)), 201


@bp.get("")
@token_required
def list_change_requests():
    """List change requests. Query: status (optional). Site user: site's requests from level_0/level_1 (+ unset grade),
    off-plan synthetic rows, and in-plan modification review rows; status=PENDING is the L1 validation inbox (off-plan + in-plan mod).
    Corporate: all; PENDING adds corporate inbox rows for activity validation."""
    status = (request.args.get("status") or "").strip().upper() or None
    role = (getattr(request, "role", "") or "").upper()
    user_id = request.user_id
    site_pending_inbox = role in ("SITE_USER", "SITE") and status == "PENDING"
    site_allowed_ids = None
    if role in ("SITE_USER", "SITE"):
        site_allowed_ids = [
            us.site_id
            for us in UserSite.query.filter_by(user_id=user_id, is_active=True).all()
        ]
    if role in ("CORPORATE_USER", "CORPORATE"):
        q = ChangeRequest.query
        if status:
            q = q.filter(ChangeRequest.status == status)
        q = q.order_by(ChangeRequest.created_at.desc())
        items = q.all()
        if status == "PENDING":
            items = [cr for cr in items if _change_request_awaiting_corporate_unlock(cr)]
    else:
        # For site users, /changes/pending is a validation inbox (not this list).
        # /changes (no status): all unlock requests for viewer's sites from level_0 / level_1 (or unset grade).
        if site_pending_inbox:
            items = []
        elif not site_allowed_ids:
            items = []
        else:
            requester_us = aliased(UserSite)
            q = (
                ChangeRequest.query.join(
                    requester_us,
                    and_(
                        requester_us.user_id == ChangeRequest.requested_by,
                        requester_us.site_id == ChangeRequest.site_id,
                        requester_us.is_active.is_(True),
                    ),
                )
                .filter(
                    ChangeRequest.site_id.in_(site_allowed_ids),
                    or_(
                        requester_us.grade.in_(("level_0", "level_1")),
                        requester_us.grade.is_(None),
                        requester_us.grade == "",
                    ),
                )
            )
            if status:
                q = q.filter(ChangeRequest.status == status)
            q = q.order_by(ChangeRequest.created_at.desc())
            items = q.all()
    out = []
    for cr in items:
        row = _change_request_to_json(cr)
        row["pending_item_type"] = "CHANGE_REQUEST"
        out.append(row)
    if role in ("SITE_USER", "SITE") and not site_pending_inbox and site_allowed_ids:
        mine_off = (
            CsrActivity.query.options(
                joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
            )
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(
                CsrPlan.site_id.in_(site_allowed_ids),
                activity_has_off_plan_realization_sql,
                CsrActivity.status.in_(("SUBMITTED", "VALIDATED", "REJECTED")),
            )
            .all()
        )
        for a in mine_off:
            plan = a.plan
            if not plan:
                continue
            realized = (
                RealizedCsr.query.filter_by(activity_id=a.id, is_off_plan=True)
                .order_by(RealizedCsr.created_at.desc())
                .first()
            )
            creator_id = getattr(realized, "created_by", None) if realized else None
            if not creator_id:
                continue
            row = _off_plan_mine_list_item(a, creator_id)
            if not row:
                continue
            if status:
                if row["status"] != status:
                    continue
            out.append(row)
        mine_in_plan = (
            CsrActivity.query.options(
                joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
            )
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(
                CsrPlan.site_id.in_(site_allowed_ids),
                ~activity_has_off_plan_realization_sql,
                CsrPlan.status == "VALIDATED",
                CsrActivity.status.in_(("SUBMITTED", "REJECTED")),
            )
            .all()
        )
        for a in mine_in_plan:
            plan = a.plan
            if not plan:
                continue
            rid, _ = _in_plan_mod_review_requester(a)
            if not rid:
                continue
            row = _in_plan_mod_mine_list_item(a, rid)
            if not row:
                continue
            if status:
                if row["status"] != status:
                    continue
            out.append(row)
    # My submissions log (plans + activity validation submissions) for any role.
    if not site_pending_inbox:
        # Plans submitted by current user.
        plans_q = CsrPlan.query.filter(
            CsrPlan.submitted_by == user_id,
            CsrPlan.status.in_(("SUBMITTED", "VALIDATED", "REJECTED")),
        )
        if role in ("SITE_USER", "SITE"):
            if site_allowed_ids:
                plans_q = plans_q.filter(CsrPlan.site_id.in_(site_allowed_ids))
            else:
                plans_q = plans_q.filter(False)
        plans = plans_q.all()
        requester = User.query.get(user_id) if user_id else None
        for p in plans:
            plan_validations = (
                Validation.query.filter(
                    Validation.entity_type == "PLAN",
                    Validation.entity_id == p.id,
                    Validation.status.in_(("APPROVED", "REJECTED")),
                    Validation.validated_by.isnot(None),
                )
                .order_by(Validation.validated_at.asc(), Validation.created_at.asc())
                .all()
            )
            # 1) Submission log row.
            submitted_row = {
                "id": f"plan-sub-{p.id}",
                "site_id": p.site_id,
                "site_name": p.site.name if p.site else None,
                "entity_type": "PLAN",
                "entity_id": p.id,
                "year": p.year,
                "reason": "Plan submitted for validation",
                "status": "SUBMITTED",
                "requested_by": user_id,
                "requested_by_name": f"{requester.first_name} {requester.last_name}" if requester else None,
                "requested_by_avatar_url": user_avatar_serve_url_for_id(user_id),
                "requested_duration": None,
                "reviewed_by": None,
                "reviewed_by_name": None,
                "reviewed_by_avatar_url": None,
                "reviewed_at": None,
                "created_at": p.submitted_at.isoformat() if getattr(p, "submitted_at", None) else (p.updated_at.isoformat() if p.updated_at else None),
                "validation_mode": getattr(p, "validation_mode", None),
                "validation_step": getattr(p, "validation_step", None),
                "plan_site_name": p.site.name if p.site else None,
                "plan_year": p.year,
                "plan_id": p.id,
                "pending_item_type": "PLAN_VALIDATION",
            }
            if not status or submitted_row["status"] == status:
                out.append(submitted_row)

            # 2) One row per validation decision (level_1 approve, level_2 reject, ...).
            for v in plan_validations:
                reviewer = User.query.get(v.validated_by) if v.validated_by else None
                grade_label = (v.grade or "").replace("_", " ").strip() or "validator"
                step_reason = (
                    (v.comment or "").strip()
                    if v.status == "REJECTED"
                    else f"{grade_label} approved plan validation"
                )
                decision_row = {
                    "id": f"plan-sub-{p.id}-step-{v.id}",
                    "site_id": p.site_id,
                    "site_name": p.site.name if p.site else None,
                    "entity_type": "PLAN",
                    "entity_id": p.id,
                    "year": p.year,
                    "reason": step_reason or "Plan validation rejected",
                    "status": v.status,
                    "requested_by": user_id,
                    "requested_by_name": f"{requester.first_name} {requester.last_name}" if requester else None,
                    "requested_by_avatar_url": user_avatar_serve_url_for_id(user_id),
                    "requested_duration": None,
                    "reviewed_by": v.validated_by,
                    "reviewed_by_name": (f"{reviewer.first_name} {reviewer.last_name}" if reviewer else None),
                    "reviewed_by_avatar_url": user_avatar_serve_url(reviewer) if reviewer else None,
                    "reviewed_at": v.validated_at.isoformat() if v.validated_at else None,
                    "created_at": (
                        v.validated_at.isoformat()
                        if v.validated_at
                        else (v.created_at.isoformat() if v.created_at else None)
                    ),
                    "validation_mode": getattr(p, "validation_mode", None),
                    "validation_step": getattr(p, "validation_step", None),
                    "plan_site_name": p.site.name if p.site else None,
                    "plan_year": p.year,
                    "plan_id": p.id,
                    "pending_item_type": "PLAN_VALIDATION",
                }
                if status and decision_row["status"] != status:
                    continue
                out.append(decision_row)
    # Site level-1 inbox: off-plan (111 step 1) + modifications sur plan validé (111 step 1).
    if site_pending_inbox:
        # No level_1 assignment anywhere => no validation inbox entries.
        if not _user_has_any_grade(user_id, "level_1"):
            return jsonify([]), 200
        activities = (
            CsrActivity.query.options(
                joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
            )
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(
                CsrActivity.status == "SUBMITTED",
                or_(
                    activity_has_off_plan_realization_sql,
                    and_(~activity_has_off_plan_realization_sql, CsrPlan.status == "VALIDATED"),
                ),
            )
            .all()
        )
        existing_activity_ids = {
            row.get("activity_id")
            for row in out
            if row.get("pending_item_type") in ("OFF_PLAN_ACTIVITY", "IN_PLAN_ACTIVITY_MOD")
        }
        for a in activities:
            if not _level1_validation_step_pending(a):
                continue
            plan = a.plan
            if not plan:
                continue
            if not _user_can_access_site(user_id, plan.site_id):
                continue
            if not _user_has_grade(user_id, plan.site_id, "level_1"):
                continue
            if a.id in existing_activity_ids:
                continue
            if _activity_has_off_plan_realization(a):
                out.append(_pending_off_plan_level1_item(a))
            else:
                out.append(_pending_in_plan_mod_level1_item(a))
        unlock_crs = (
            ChangeRequest.query.filter(
                ChangeRequest.status == "PENDING",
                ChangeRequest.validation_mode == "111",
                or_(
                    ChangeRequest.validation_step == 1,
                    ChangeRequest.validation_step.is_(None),
                ),
                ChangeRequest.site_id.in_(site_allowed_ids),
            )
            .order_by(ChangeRequest.created_at.desc())
            .all()
        )
        seen_cr_ids = {row.get("id") for row in out if row.get("pending_item_type") == "CHANGE_REQUEST"}
        for cr in unlock_crs:
            if not _user_has_grade(user_id, cr.site_id, "level_1"):
                continue
            if cr.id in seen_cr_ids:
                continue
            row = _change_request_to_json(cr)
            row["pending_item_type"] = "CHANGE_REQUEST"
            out.append(row)
    # Only when explicitly filtering PENDING (corporate inbox), not for full history lists.
    if role in ("CORPORATE_USER", "CORPORATE") and status == "PENDING":
        activities = (
            CsrActivity.query.options(
                joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
            )
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(
                CsrActivity.status == "SUBMITTED",
                or_(
                    activity_has_off_plan_realization_sql,
                    and_(~activity_has_off_plan_realization_sql, CsrPlan.status == "VALIDATED"),
                ),
            )
            .all()
        )
        for a in activities:
            if _off_plan_awaits_corporate_validation(a):
                out.append(_pending_off_plan_corporate_item(a))
            elif _in_plan_mod_awaits_corporate_validation(a):
                out.append(_pending_in_plan_mod_corporate_item(a))
    out.sort(key=lambda x: (x.get("created_at") or ""), reverse=True)
    return jsonify(out), 200


@bp.get("/<string:cr_id>")
@token_required
def get_change_request(cr_id):
    """Get one change request with documents."""
    cr = ChangeRequest.query.get(cr_id)
    if not cr:
        return jsonify({"message": "Demande introuvable"}), 404
    role = (getattr(request, "role", "") or "").upper()
    user_id = request.user_id
    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(user_id, cr.site_id):
            return jsonify({"message": "Accès non autorisé"}), 403
        if not _site_requester_is_level_0_or_1(cr.requested_by, cr.site_id):
            return jsonify({"message": "Accès non autorisé"}), 403
    return jsonify(_change_request_to_json(cr, include_documents=True)), 200


@bp.post("/<string:cr_id>/approve")
@token_required
def approve_change_request(cr_id):
    """Approve unlock request. Mode 111 step 1: niveau 1 site only (passe l’étape corporate). Sinon corporate final."""
    from datetime import datetime, timedelta
    role = (getattr(request, "role", "") or "").upper()
    cr = ChangeRequest.query.get(cr_id)
    if not cr:
        return jsonify({"message": "Demande introuvable"}), 404
    if cr.status != "PENDING":
        return jsonify({"message": "Cette demande n'est plus en attente"}), 400

    vm = str(getattr(cr, "validation_mode", None) or "101").strip() or "101"
    if vm not in ("101", "111"):
        vm = "101"
    step = _step_int(getattr(cr, "validation_step", None))

    if vm == "111" and step != 2:
        if role not in ("SITE_USER", "SITE"):
            return jsonify({"message": "À cette étape, seul un utilisateur du site (niveau 1) peut approuver"}), 403
        if not _user_has_grade(request.user_id, cr.site_id, "level_1"):
            return jsonify({"message": "Seul un validateur niveau 1 de ce site peut approuver cette demande"}), 403
        cr.validation_step = 2
        write_audit(
            request.user_id,
            cr.site_id,
            "APPROVE",
            "CHANGE_REQUEST",
            cr.id,
            "Validation niveau 1 demande de déverrouillage — transmission corporate",
        )
        db.session.commit()
        site_name = cr.site.name if cr.site else "Site inconnu"
        ent = "le plan" if cr.entity_type == "PLAN" else "l'activité"
        notify_corporate(
            title="Demande de déverrouillage — validation corporate",
            message=(
                f"Le site {site_name} : demande de modification ({ent}) pour l'année {cr.year} "
                f"a été validée au niveau 1. En attente de votre décision."
            ),
            type="warning",
            site_id=cr.site_id,
            entity_type="CHANGE_REQUEST",
            entity_id=cr.id,
            notification_category="activity_validation",
        )
        emit_tasks_refresh_for_request_actor()
        emit_tasks_updated_for_site_contributors(cr.site_id)
        return jsonify(_change_request_to_json(cr, include_documents=True)), 200

    if role not in ("CORPORATE_USER", "CORPORATE"):
        return jsonify({"message": "Seul un utilisateur corporate peut approuver une demande de modification"}), 403

    cr.status = "APPROVED"
    cr.reviewed_by = request.user_id
    cr.reviewed_at = datetime.utcnow()
    plan = None
    if cr.entity_type == "PLAN" and cr.entity_id:
        plan = CsrPlan.query.get(cr.entity_id)
        if plan:
            now = datetime.utcnow()
            days = _parse_duration_days(cr.requested_duration)
            plan.unlock_until = now + timedelta(days=days)
            plan.unlock_since = now
    elif cr.entity_type == "ACTIVITY" and cr.entity_id:
        activity = CsrActivity.query.get(cr.entity_id)
        if activity:
            plan = activity.plan
            now = datetime.utcnow()
            days = _parse_duration_days(cr.requested_duration)
            activity.unlock_until = now + timedelta(days=days)
            activity.unlock_since = now
    desc = f"Demande de modification approuvée (plan {plan.year})" if plan else "Demande de modification approuvée"
    write_audit(request.user_id, cr.site_id, "APPROVE", cr.entity_type, cr.entity_id, desc)
    db.session.commit()

    site_name = cr.site.name if cr.site else "Site inconnu"
    notify_user(
        cr.requested_by,
        title="Demande de modification approuvee",
        message=(
            f"Votre demande de modification pour le site {site_name} a ete approuvee. "
            f"Le plan est maintenant ouvert pendant {cr.requested_duration or 'une periode limitee'}."
        ),
        type="success",
        site_id=cr.site_id,
        entity_type="CHANGE_REQUEST",
        entity_id=cr.id,
        notification_category="activity_validation",
    )
    emit_tasks_refresh_for_request_actor()
    emit_tasks_updated_for_site_contributors(cr.site_id)
    return jsonify(_change_request_to_json(cr, include_documents=True)), 200


@bp.post("/<string:cr_id>/reject")
@token_required
def reject_change_request(cr_id):
    """Reject unlock request. Niveau 1 (étape 1) ou corporate (étape finale)."""
    role = (getattr(request, "role", "") or "").upper()
    data = request.get_json(silent=True) or {}
    comment = (data.get("comment") or "").strip()
    cr = ChangeRequest.query.get(cr_id)
    if not cr:
        return jsonify({"message": "Demande introuvable"}), 404
    if cr.status != "PENDING":
        return jsonify({"message": "Cette demande n'est plus en attente"}), 400
    from datetime import datetime

    vm = str(getattr(cr, "validation_mode", None) or "101").strip() or "101"
    if vm not in ("101", "111"):
        vm = "101"
    step = _step_int(getattr(cr, "validation_step", None))
    is_l1_step = vm == "111" and step != 2

    if is_l1_step:
        if role not in ("SITE_USER", "SITE"):
            return jsonify({"message": "À cette étape, seul un utilisateur du site (niveau 1) peut rejeter"}), 403
        if not _user_has_grade(request.user_id, cr.site_id, "level_1"):
            return jsonify({"message": "Seul un validateur niveau 1 de ce site peut rejeter cette demande"}), 403
        if not comment:
            return jsonify({"message": "Un motif de rejet est obligatoire"}), 400
    elif role not in ("CORPORATE_USER", "CORPORATE"):
        return jsonify({"message": "Seul un utilisateur corporate peut rejeter une demande de modification"}), 403

    cr.status = "REJECTED"
    cr.reviewed_by = request.user_id
    cr.reviewed_at = datetime.utcnow()
    if comment:
        cr.reason = (cr.reason or "") + "\n[Rejet: " + comment + "]"
    desc = f"Demande de modification rejetée: {comment[:200]}" if comment else "Demande de modification rejetée"
    write_audit(request.user_id, cr.site_id, "REJECT", cr.entity_type, cr.entity_id, desc)
    db.session.commit()
    emit_tasks_updated_for_site_contributors(cr.site_id)

    site_name = cr.site.name if cr.site else "Site inconnu"
    notify_user(
        cr.requested_by,
        title="Demande de modification rejetee",
        message=(
            f"Votre demande de modification pour le site {site_name} a ete rejetee. "
            f"Motif: {comment or 'Aucun motif precise.'}"
        ),
        type="error",
        site_id=cr.site_id,
        entity_type="CHANGE_REQUEST",
        entity_id=cr.id,
        notification_category="activity_validation",
    )
    emit_tasks_refresh_for_request_actor()
    return jsonify(_change_request_to_json(cr, include_documents=True)), 200
