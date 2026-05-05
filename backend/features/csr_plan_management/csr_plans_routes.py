"""
CSR plans (annual plans) endpoints.
List and create plans; enforce site access for SITE_USER.
"""
import json

from datetime import datetime
import logging
import re
from typing import Optional, Tuple

from flask import Blueprint, request, jsonify
from sqlalchemy import distinct, func

logger = logging.getLogger(__name__)

from core import db, token_required
from core.permissions import has_permission
from core.user_avatar import user_avatar_serve_url
from models import CsrPlan, Site, User, UserSite, Validation, ChangeRequest
from features.csr_plan_management.plan_visibility import csr_plans_visible_query
from features.change_request_management.change_requests_routes import (
    _activity_has_off_plan_realization,
    _activity_has_pending_level1_validation,
    _latest_off_plan_realization,
)
from features.notification_management.notification_helper import notify_corporate, notify_site_users
from features.notification_management.socketio_emit import emit_tasks_refresh_for_request_actor
from features.audit_history_management.audit_helper import (
    audit_create,
    audit_update,
    audit_delete,
    write_audit,
    snapshot_plan,
)

bp = Blueprint("csr_plans", __name__, url_prefix="/api/csr-plans")
VALIDATION_MODE_SITE_STEPS = {
    "101": 0,  # corporate only
    "111": 1,  # level_1 + corporate
    "211": 2,  # level_1 + level_2 + corporate
    "311": 3,  # level_1 + level_2 + level_3 + corporate
}


def _normalize_validation_mode(raw: Optional[str]) -> str:
    m = str(raw if raw is not None else "101").strip()
    return m if m in VALIDATION_MODE_SITE_STEPS else "101"


def _plan_required_site_steps(plan: CsrPlan) -> int:
    return VALIDATION_MODE_SITE_STEPS.get(_plan_validation_mode_str(plan), 0)


def _require_plan_permission(action: str):
    role = (getattr(request, "role", "") or "").upper()
    if has_permission(getattr(request, "user_id", ""), role, "plan", action):
        return None
    return jsonify({"message": f"Permission refusée: plan.{action}"}), 403


def _is_corporate(role: str) -> bool:
    return (role or "").upper() in ("CORPORATE_USER", "CORPORATE")


def _compose_activity_number(plan: CsrPlan, raw_activity_number: Optional[str]) -> str:
    base = (raw_activity_number or "").strip()
    if not base:
        return ""
    if not plan or not getattr(plan, "site", None) or not getattr(plan, "year", None):
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


def _plan_validation_mode_str(plan: CsrPlan) -> str:
    """Normalized plan validation mode."""
    return _normalize_validation_mode(getattr(plan, "validation_mode", None))


def _plan_validation_step_int(plan: CsrPlan) -> Optional[int]:
    raw = getattr(plan, "validation_step", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _plan_validation_grade(plan: CsrPlan) -> str:
    """Validation grade for the current step (level_n or level_corporate)."""
    site_steps = _plan_required_site_steps(plan)
    step = _plan_validation_step_int(plan)
    if step is None:
        return "level_corporate"
    if step <= site_steps:
        return f"level_{step}"
    return "level_corporate"


def _get_or_create_plan_validation(plan_id: str, site_id: str, grade: str):
    """Get or create Validation row for this plan and grade."""
    v = Validation.query.filter_by(
        entity_type="PLAN", entity_id=plan_id, grade=grade
    ).first()
    if v:
        return v
    v = Validation(
        entity_type="PLAN",
        entity_id=plan_id,
        site_id=site_id,
        grade=grade,
        status="PENDING",
    )
    db.session.add(v)
    return v


def _reset_plan_validation_row_pending(v: Validation) -> None:
    """Clear a validation row so a new review cycle can start (e.g. resubmit after reject)."""
    v.status = "PENDING"
    v.comment = None
    v.rejected_activity_ids = None
    v.validated_by = None
    v.validated_at = None


def _configure_plan_validation_after_site_submit(plan: CsrPlan, user_id: str) -> None:
    """
    Set validation_step and Validation rows when a site user submits for review.

    Mode 111: if the submitter has grade level_1 on the plan site, Level 1 is treated as already
    done (same as manual L1 approve) — only corporate (Level 2) must approve.
    Otherwise mode 111 stays at step 1 for a separate L1 approver.
    Mode 101: step 2, corporate only (unchanged).
    """
    site_steps = _plan_required_site_steps(plan)
    first_step = 1
    plan.validation_step = first_step
    first_grade = f"level_{first_step}" if site_steps > 0 else "level_corporate"
    v = _get_or_create_plan_validation(plan.id, plan.site_id, first_grade)
    _reset_plan_validation_row_pending(v)


def _parse_rejected_activity_ids(plan: CsrPlan):
    """Return list of activity IDs from plan.rejected_activity_ids (JSON text). Supports legacy rejected_activity_id."""
    raw = getattr(plan, "rejected_activity_ids", None)
    if raw:
        try:
            ids = json.loads(raw)
            return ids if isinstance(ids, list) else []
        except (TypeError, json.JSONDecodeError):
            pass
    # Legacy: single rejected_activity_id
    leg = getattr(plan, "rejected_activity_id", None)
    return [leg] if leg else []


def _plan_total_budget_from_activities(plan: CsrPlan):
    """Sum of all activities' planned_budget for this plan."""
    from models import CsrActivity
    total = db.session.query(db.func.coalesce(db.func.sum(CsrActivity.planned_budget), 0)).filter(CsrActivity.plan_id == plan.id).scalar()
    return float(total) if total is not None else None


def _plan_total_realized_budget(plan: CsrPlan):
    """Sum of all realized_budget from realized_csr for this plan's activities."""
    from models import CsrActivity, RealizedCsr
    total = (
        db.session.query(db.func.coalesce(db.func.sum(RealizedCsr.realized_budget), 0))
        .join(CsrActivity, CsrActivity.id == RealizedCsr.activity_id)
        .filter(CsrActivity.plan_id == plan.id)
        .scalar()
    )
    return float(total) if total is not None else None


def _plan_activities_realized_count(plan_id: str) -> int:
    """Distinct planned activities in this plan that have at least one realization row."""
    from models import CsrActivity, RealizedCsr
    n = (
        db.session.query(func.count(distinct(RealizedCsr.activity_id)))
        .select_from(RealizedCsr)
        .join(CsrActivity, CsrActivity.id == RealizedCsr.activity_id)
        .filter(CsrActivity.plan_id == plan_id)
        .scalar()
    )
    return int(n or 0)


def _submitter_user(plan: CsrPlan):
    """User who submitted for validation (SUBMITTED only); legacy rows fall back to creator."""
    if plan.status != "SUBMITTED":
        return None
    uid = getattr(plan, "submitted_by", None) or plan.created_by
    if not uid:
        return None
    return User.query.get(uid)


def _submitter_display_name(plan: CsrPlan) -> Optional[str]:
    """First + last name of last submitter (SUBMITTED only); legacy rows use created_by."""
    u = _submitter_user(plan)
    if not u:
        return None
    parts = [(getattr(u, "first_name", None) or "").strip(), (getattr(u, "last_name", None) or "").strip()]
    parts = [p for p in parts if p]
    if parts:
        return " ".join(parts)
    return (getattr(u, "email", None) or "").strip() or None


def _plan_to_json(plan: CsrPlan):
    """Serialize plan with budget fields.

    - ``allocated_budget``: stored on the annual plan
    - ``budget_consumed``: computed from realizations
    """
    current_year = datetime.utcnow().year
    total_estimated = _plan_total_budget_from_activities(plan)
    budget_consumed = _plan_total_realized_budget(plan)
    if getattr(plan, "allocated_budget", None) is not None:
        allocated_budget = float(plan.allocated_budget)
    elif plan.year < current_year:
        allocated_budget = budget_consumed
    else:
        allocated_budget = total_estimated
    return {
        "id": plan.id,
        "site_id": plan.site_id,
        "site_name": plan.site.name if plan.site else None,
        "site_code": plan.site.code if plan.site else None,
        "site_region": plan.site.region if plan.site else None,
        "site_country": plan.site.country if plan.site else None,
        "year": plan.year,
        "validation_mode": _plan_validation_mode_str(plan),
        "validation_step": getattr(plan, "validation_step", None),
        "status": plan.status,
        "allocated_budget": allocated_budget,
        "budget_consumed": budget_consumed,
        "total_hc": getattr(plan, "total_hc", None),
        "total_estimated_budget": total_estimated,
        "submitted_at": plan.submitted_at.isoformat() if plan.submitted_at else None,
        "validated_at": plan.validated_at.isoformat() if plan.validated_at else None,
        "rejected_comment": getattr(plan, "rejected_comment", None) or None,
        "rejected_activity_ids": _parse_rejected_activity_ids(plan),
        "unlock_until": plan.unlock_until.isoformat() if getattr(plan, "unlock_until", None) else None,
        "created_by": plan.created_by,
        "submitted_by": getattr(plan, "submitted_by", None),
        "submitted_by_name": _submitter_display_name(plan),
        "submitted_by_avatar_url": user_avatar_serve_url(_submitter_user(plan)),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


def _user_can_access_site(user_id: str, site_id: str) -> bool:
    return UserSite.query.filter_by(
        user_id=user_id, site_id=site_id, is_active=True
    ).first() is not None


def _user_has_grade(user_id: str, site_id: str, grade: str) -> bool:
    us = UserSite.query.filter_by(user_id=user_id, site_id=site_id, is_active=True).first()
    if not us:
        return False
    g = (us.grade or "").strip().lower()
    return g == (grade or "").strip().lower()


def _compute_can_approve(plan: CsrPlan, user_id: str, role: str) -> bool:
    """True si l'utilisateur courant peut approuver/rejeter ce plan (status SUBMITTED)."""
    if plan.status != "SUBMITTED":
        return False
    step = _plan_validation_step_int(plan)
    if step is None:
        return False
    site_steps = _plan_required_site_steps(plan)
    if step <= site_steps:
        grade = f"level_{step}"
        return _user_can_access_site(user_id, plan.site_id) and _user_has_grade(user_id, plan.site_id, grade)
    return role in ("CORPORATE_USER", "CORPORATE")


def _plan_json_with_approval_flags(plan: CsrPlan, user_id: Optional[str], role: str) -> dict:
    """Same as _plan_to_json plus can_approve/can_reject so PATCH responses do not leave stale flags on the client."""
    out = _plan_to_json(plan)
    uid = (user_id or "").strip()
    r = (role or "").upper()
    if uid:
        out["can_approve"] = out["can_reject"] = _compute_can_approve(plan, uid, r)
    else:
        out["can_approve"] = out["can_reject"] = False
    return out


def _compute_can_approve_off_plan_activity(a, user_id: str, role: str) -> bool:
    """True si l'utilisateur peut approuver/rejeter une activité en attente (hors plan ou modification sur plan validé)."""
    from models import CsrActivity

    if not isinstance(a, CsrActivity):
        return False
    if a.status != "SUBMITTED":
        return False
    plan = a.plan
    if not plan:
        return False
    is_off = _activity_has_off_plan_realization(a)
    if not is_off:
        if plan.status != "VALIDATED":
            return False
    off_r = _latest_off_plan_realization(a) if is_off else None
    step_raw = (
        getattr(off_r, "off_plan_validation_step", None)
        if off_r is not None
        else getattr(a, "off_plan_validation_step", None)
    )
    step = int(step_raw) if step_raw is not None else None
    raw_mode = (
        getattr(off_r, "off_plan_validation_mode", None)
        if off_r is not None
        else getattr(a, "off_plan_validation_mode", None)
    )
    mode = _normalize_validation_mode(str(raw_mode or _plan_validation_mode_str(plan) or "101").strip() or "101")
    site_id = plan.site_id
    rupper = (role or "").upper()
    corp = rupper in ("CORPORATE_USER", "CORPORATE")
    site_steps = VALIDATION_MODE_SITE_STEPS.get(mode, 0)
    if step is None:
        step = site_steps + 1
    if step <= site_steps:
        required_grade = f"level_{step}"
        if step == 1:
            return (
                _user_can_access_site(user_id, site_id)
                and _user_has_grade(user_id, site_id, "level_1")
                and _activity_has_pending_level1_validation(a.id)
            )
        return _user_can_access_site(user_id, site_id) and _user_has_grade(user_id, site_id, required_grade)
    return corp


@bp.get("")
@token_required
def list_plans():
    """List CSR plans. Optional query: site_id, year, status.
    Visibility: site users and non–globally-scoped corporate users only see plans for their assigned sites;
    corporate users with is_corporate_global see all plans."""
    denied = _require_plan_permission("read")
    if denied:
        return denied
    site_id = request.args.get("site_id")
    year = request.args.get("year", type=int)
    status = request.args.get("status")

    q = csr_plans_visible_query(request.user_id, getattr(request, "role", "") or "")

    if site_id:
        q = q.filter_by(site_id=site_id)
    if year is not None:
        q = q.filter_by(year=year)
    if status:
        q = q.filter_by(status=status)

    from models import CsrActivity
    plans = q.order_by(CsrPlan.year.desc(), CsrPlan.created_at.desc()).all()
    role_str = (getattr(request, "role", "") or "").upper()
    user_id = getattr(request, "user_id", None)
    result = []
    for p in plans:
        obj = _plan_to_json(p)
        obj["activities_count"] = CsrActivity.query.filter_by(plan_id=p.id).count()
        obj["activities_realized_count"] = _plan_activities_realized_count(p.id)
        if p.status == "SUBMITTED" and user_id:
            obj["can_approve"] = obj["can_reject"] = _compute_can_approve(p, user_id, role_str)
        else:
            obj["can_approve"] = obj["can_reject"] = False
        result.append(obj)
    return jsonify(result), 200


@bp.post("")
@token_required
def create_plan():
    """Create a new CSR plan (DRAFT). SITE_USER must have access to the chosen site."""
    denied = _require_plan_permission("create")
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not data:
        logger.warning("create_plan 400: body absent ou JSON invalide")
        return jsonify({"message": "Données manquantes ou format JSON invalide"}), 400

    site_id = (data.get("site_id") or "").strip() if data.get("site_id") is not None else ""
    year = data.get("year")
    if not site_id:
        logger.warning("create_plan 400: site_id manquant, body=%s", {k: v for k, v in data.items() if k != "allocated_budget"})
        return jsonify({"message": "Le site est obligatoire"}), 400
    if year is None or year == "":
        logger.warning("create_plan 400: year manquant, site_id=%s", site_id)
        return jsonify({"message": "L'année est obligatoire"}), 400

    try:
        year = int(year)
    except (TypeError, ValueError):
        logger.warning("create_plan 400: year invalide %r", year)
        return jsonify({"message": "L'année doit être un nombre entier (ex: 2025)"}), 400

    role = getattr(request, "role", "").upper()
    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(request.user_id, site_id):
            return jsonify({"message": "Vous n'avez pas accès à ce site"}), 403

    if CsrPlan.query.filter_by(site_id=site_id, year=year).first():
        logger.info("create_plan 400: plan déjà existant site=%s year=%s", site_id, year)
        return jsonify({"message": "Un plan existe déjà pour ce site et cette année"}), 400

    validation_mode = _normalize_validation_mode(data.get("validation_mode", "101"))
    allocated_budget = data.get("allocated_budget")
    total_hc = data.get("total_hc")
    if allocated_budget is not None:
        try:
            allocated_budget = float(allocated_budget)
        except (TypeError, ValueError):
            allocated_budget = None
    if total_hc is not None and total_hc != "":
        try:
            total_hc = int(total_hc)
        except (TypeError, ValueError):
            return jsonify({"message": "Le total HC doit être un nombre entier"}), 400
        if total_hc < 0:
            return jsonify({"message": "Le total HC doit être >= 0"}), 400
    else:
        total_hc = None

    plan = CsrPlan(
        site_id=site_id,
        year=year,
        validation_mode=validation_mode,
        status="DRAFT",
        allocated_budget=allocated_budget,
        total_hc=total_hc,
        created_by=request.user_id,
    )
    db.session.add(plan)
    db.session.flush()
    audit_create(
        user_id=request.user_id,
        site_id=site_id,
        entity_type="PLAN",
        entity_id=plan.id,
        description=f"Création plan {plan.year} site {site_id}",
        new_snapshot=snapshot_plan(plan),
    )
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify(_plan_to_json(plan)), 201


def _bulk_submit_plan(plan_id: str, user_id: str, role: str) -> Tuple[bool, Optional[str]]:
    """Submit one plan. Returns (success, error_message)."""
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return False, "Plan introuvable"
    if plan.status != "DRAFT":
        return False, f"Plan non brouillon (statut: {plan.status})"
    if role in ("SITE_USER", "SITE") and not _user_can_access_site(user_id, plan.site_id):
        return False, "Accès refusé"
    now = datetime.utcnow()
    if _is_corporate(role):
        plan.status = "VALIDATED"
        plan.submitted_at = now
        plan.validated_at = now
        plan.validation_step = None
        plan.unlock_until = None
    else:
        plan.status = "SUBMITTED"
        plan.submitted_at = now
        plan.submitted_by = user_id
        _configure_plan_validation_after_site_submit(plan, user_id)
    return True, None


def _bulk_delete_plan(plan_id: str, user_id: str, role: str) -> Tuple[bool, Optional[str]]:
    """Delete one plan. Returns (success, error_message)."""
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return False, "Plan introuvable"
    if not _plan_is_editable(plan, role):
        return False, f"Plan non modifiable (statut: {plan.status})"
    if role in ("SITE_USER", "SITE") and not _user_can_access_site(user_id, plan.site_id):
        return False, "Accès refusé"
    old_snapshot = snapshot_plan(plan)
    audit_delete(
        user_id=user_id,
        site_id=plan.site_id,
        entity_type="PLAN",
        entity_id=plan.id,
        description=f"Suppression plan {plan.year}",
        old_snapshot=old_snapshot,
    )
    # Explicitly delete activities first to avoid SQLAlchemy nulling plan_id on flush.
    from models import CsrActivity
    db.session.query(CsrActivity).filter_by(plan_id=plan.id).delete(synchronize_session=False)
    db.session.delete(plan)
    return True, None


@bp.post("/bulk-submit")
@token_required
def bulk_submit_plans():
    """Soumettre plusieurs plans (DRAFT → SUBMITTED). Body: { plan_ids: string[] }."""
    denied = _require_plan_permission("bulk_submit")
    if denied:
        return denied
    data = request.get_json() or {}
    plan_ids = data.get("plan_ids") or []
    if not isinstance(plan_ids, list):
        plan_ids = []
    plan_ids = [str(x).strip() for x in plan_ids if x]
    if not plan_ids:
        return jsonify({"message": "Aucun plan sélectionné", "success_count": 0, "errors": []}), 400

    role = (getattr(request, "role", "") or "").upper()
    user_id = request.user_id
    results = []
    for pid in plan_ids:
        ok, err = _bulk_submit_plan(pid, user_id, role)
        results.append({"plan_id": pid, "success": ok, "error": err})
    db.session.commit()
    emit_tasks_refresh_for_request_actor()

    success_count = sum(1 for r in results if r["success"])
    errors = [r for r in results if not r["success"]]
    return jsonify({
        "message": f"{success_count} plan(s) soumis pour validation.",
        "success_count": success_count,
        "total": len(plan_ids),
        "errors": [{"plan_id": e["plan_id"], "error": e["error"]} for e in errors],
    }), 200


@bp.post("/bulk-delete")
@token_required
def bulk_delete_plans():
    """Supprimer plusieurs plans (DRAFT ou REJECTED uniquement). Body: { plan_ids: string[] }."""
    denied = _require_plan_permission("bulk_delete")
    if denied:
        return denied
    data = request.get_json() or {}
    plan_ids = data.get("plan_ids") or []
    if not isinstance(plan_ids, list):
        plan_ids = []
    plan_ids = [str(x).strip() for x in plan_ids if x]
    if not plan_ids:
        return jsonify({"message": "Aucun plan sélectionné", "success_count": 0, "errors": []}), 400

    role = (getattr(request, "role", "") or "").upper()
    user_id = request.user_id
    results = []
    for pid in plan_ids:
        ok, err = _bulk_delete_plan(pid, user_id, role)
        results.append({"plan_id": pid, "success": ok, "error": err})
    db.session.commit()
    emit_tasks_refresh_for_request_actor()

    success_count = sum(1 for r in results if r["success"])
    errors = [r for r in results if not r["success"]]
    return jsonify({
        "message": f"{success_count} plan(s) supprimé(s).",
        "success_count": success_count,
        "total": len(plan_ids),
        "errors": [{"plan_id": e["plan_id"], "error": e["error"]} for e in errors],
    }), 200


@bp.patch("/<string:plan_id>")
@token_required
def update_plan(plan_id):
    """Update a plan. Allowed only when editable (DRAFT/REJECTED and not past unlock_until)."""
    denied = _require_plan_permission("update")
    if denied:
        return denied
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    role = (getattr(request, "role", "") or "").upper()
    if not _plan_is_editable(plan, role):
        return jsonify({"message": "Plan non modifiable (verrouillé ou période d'ouverture expirée)"}), 400

    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Données manquantes"}), 400

    old_snapshot = snapshot_plan(plan)
    if "year" in data and data["year"] is not None:
        try:
            year = int(data["year"])
        except (TypeError, ValueError):
            return jsonify({"message": "L'année doit être un nombre entier"}), 400
        if year < 2000 or year > 2100:
            return jsonify({"message": "Année invalide"}), 400
        existing = CsrPlan.query.filter_by(site_id=plan.site_id, year=year).first()
        if existing and existing.id != plan_id:
            return jsonify({"message": "Un plan existe déjà pour ce site et cette année"}), 400
        plan.year = year

    if "validation_mode" in data and data["validation_mode"] is not None:
        plan.validation_mode = _normalize_validation_mode(data["validation_mode"])

    if "allocated_budget" in data:
        tb = data.get("allocated_budget")
        if tb is None or tb == "":
            plan.allocated_budget = None
        else:
            try:
                tb_val = float(tb)
            except (TypeError, ValueError):
                return jsonify({"message": "Le budget total doit être un nombre"}), 400
            if tb_val < 0:
                return jsonify({"message": "Le budget total doit être >= 0"}), 400
            plan.allocated_budget = tb_val
    if "total_hc" in data:
        thc = data.get("total_hc")
        if thc is None or thc == "":
            plan.total_hc = None
        else:
            try:
                thc_val = int(thc)
            except (TypeError, ValueError):
                return jsonify({"message": "Le total HC doit être un nombre entier"}), 400
            if thc_val < 0:
                return jsonify({"message": "Le total HC doit être >= 0"}), 400
            plan.total_hc = thc_val

    if plan.status == "REJECTED":
        plan.rejected_comment = None
        plan.rejected_activity_ids = None

    audit_update(
        user_id=request.user_id,
        site_id=plan.site_id,
        entity_type="PLAN",
        entity_id=plan_id,
        description=f"Modification plan {plan.year}",
        old_snapshot=old_snapshot,
        new_snapshot=snapshot_plan(plan),
    )
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify(_plan_json_with_approval_flags(plan, request.user_id, getattr(request, "role", ""))), 200


def _plan_is_editable(plan: CsrPlan, role: str = "") -> bool:
    """True if plan can be edited: corporate always; otherwise DRAFT/REJECTED, or VALIDATED with unlock_until in the future."""
    if _is_corporate(role):
        return True
    unlock_until = getattr(plan, "unlock_until", None)
    now = datetime.utcnow()
    if plan.status in ("DRAFT", "REJECTED"):
        return True
    if plan.status == "VALIDATED" and unlock_until and now <= unlock_until:
        return True
    return False


@bp.get("/<string:plan_id>")
@token_required
def get_plan(plan_id):
    """Get plan by ID with activities. SITE_USER must have access to the plan's site. Auto-lock when unlock_until is past."""
    denied = _require_plan_permission("read")
    if denied:
        return denied
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404

    role = (getattr(request, "role", "") or "").upper()
    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Accès refusé"}), 403

    # If plan was open for edit and deadline passed, clear unlock_until (re-lock)
    unlock_until = getattr(plan, "unlock_until", None)
    now = datetime.utcnow()
    if unlock_until and now > unlock_until:
        plan.unlock_until = None
        db.session.commit()

    from models import CsrActivity, RealizedCsr
    activities = CsrActivity.query.filter_by(plan_id=plan.id).order_by(CsrActivity.activity_number).all()
    # Clear expired activity-level unlocks
    for a in activities:
        au = getattr(a, "unlock_until", None)
        if au and now > au:
            a.unlock_until = None
            a.unlock_since = None
    db.session.commit()
    out = _plan_to_json(plan)
    role_str = (getattr(request, "role", "") or "").upper()
    out["can_approve"] = out["can_reject"] = _compute_can_approve(plan, request.user_id, role_str)
    if role_str in ("SITE_USER", "SITE"):
        us = UserSite.query.filter_by(
            user_id=request.user_id, site_id=plan.site_id, is_active=True
        ).first()
        g = (us.grade or "").strip().lower() if us else ""
        out["viewer_site_grade"] = g if g else None
    else:
        out["viewer_site_grade"] = None

    def _activity_is_editable(a, is_off_plan_activity: bool):
        """True if activity can be edited: plan editable OR activity individually unlocked."""
        au = getattr(a, "unlock_until", None)
        activity_unlock_active = au is not None and now <= au
        # SUBMITTED = awaiting review; still editable if corporate approved an activity-level change request (unlock).
        if is_off_plan_activity and a.status == "SUBMITTED":
            return activity_unlock_active
        if not is_off_plan_activity and a.status == "SUBMITTED":
            return activity_unlock_active
        if is_off_plan_activity and a.status == "REJECTED":
            return True
        if not is_off_plan_activity and a.status == "REJECTED":
            return True
        if _plan_is_editable(plan, role_str):
            return True
        return activity_unlock_active

    # Reference: timestamp when the change request was approved (validation approved) for this plan.
    # We compare this with each activity's created_at and updated_at from csr_activities.
    validation_approved_at = getattr(plan, "unlock_since", None)
    if not validation_approved_at:
        last_approved = (
            ChangeRequest.query.filter_by(
                entity_type="PLAN", entity_id=plan.id, status="APPROVED"
            ).filter(ChangeRequest.reviewed_at.isnot(None)).order_by(ChangeRequest.reviewed_at.desc()).first()
        )
        if last_approved and last_approved.reviewed_at:
            validation_approved_at = last_approved.reviewed_at

    def _naive(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

    ref_ts = _naive(validation_approved_at)
    from datetime import timedelta
    plan_created = _naive(getattr(plan, "created_at", None))
    if ref_ts is not None and plan_created is not None and ref_ts < plan_created - timedelta(days=1):
        ref_ts = None  # reject ref older than plan (avoid marking all as added)

    user_id = getattr(request, "user_id", None)
    out["activities"] = []
    for a in activities:
        added_during_unlock = False
        modified_during_unlock = False
        if ref_ts is not None:
            created_ts = _naive(a.created_at)
            updated_ts = _naive(a.updated_at)
            # Compare validation_approved_at with activity created_at / updated_at:
            # Added: activity row was inserted AFTER the validation was approved (created_at > ref)
            if created_ts is not None and created_ts > ref_ts:
                added_during_unlock = True
            # Modified: activity existed before approval (created_at < ref) and was updated after (updated_at > ref)
            elif (
                created_ts is not None
                and updated_ts is not None
                and created_ts < ref_ts
                and updated_ts > ref_ts
            ):
                modified_during_unlock = True

        # RealizedCsr no longer has year/month columns; order by realization_date (newest first),
        # then by created_at as a fallback. MySQL/MariaDB do not support "NULLS LAST",
        # so we emulate it by sorting on an IS NULL flag first (False before True),
        # which pushes NULL realization_date rows to the end.
        realizations = (
            RealizedCsr.query.filter_by(activity_id=a.id)
            .order_by(
                RealizedCsr.realization_date.is_(None),
                RealizedCsr.realization_date.desc(),
                RealizedCsr.created_at.desc(),
            )
            .all()
        )
        first_real = realizations[0] if realizations else None
        has_realization = len(realizations) > 0
        off_real = next((r for r in realizations if getattr(r, "is_off_plan", False)), None)
        is_off_plan_activity = off_real is not None
        out["activities"].append({
            "id": a.id,
            "activity_number": _compose_activity_number(plan, a.activity_number),
            "has_realization": has_realization,
            "primary_realization_id": first_real.id if first_real else None,
            "title": a.title or "",
            "description": a.description or "",
            "status": a.status,
            "is_off_plan": is_off_plan_activity,
            "category_name": a.category.name if a.category else "",
            "collaboration_nature": a.collaboration_nature or "",
            # Legacy fields retained in JSON for compatibility; underlying columns were removed.
            "organization": getattr(a, "organization", None) or "INTERNAL",
            "contract_type": getattr(a, "contract_type", None) or "ONE_SHOT",
            "organizer": a.organizer or "",
            "edition": a.edition,
            "start_year": a.start_year,
            "external_partner_name": a.external_partner.name if a.external_partner else None,
            "planned_budget": float(a.planned_budget) if a.planned_budget is not None else None,
            "planned_volunteers": getattr(a, "planned_volunteers", None),
            "action_impact_target": float(a.action_impact_target) if a.action_impact_target is not None else None,
            "action_impact_unit": a.action_impact_unit or "",
            "realized_budget": float(first_real.realized_budget) if first_real and first_real.realized_budget is not None else None,
            "participants": first_real.participants if first_real else None,
            "total_hc": getattr(plan, "total_hc", None),
            # Legacy fields retained in JSON for compatibility; underlying columns may have been removed.
            "percentage_employees": float(getattr(first_real, "percentage_employees", None)) if first_real and getattr(first_real, "percentage_employees", None) is not None else None,
            # Number of external partners is derived from the stored external partner names.
            "number_external_partners": (
                len([p for p in (a.external_partner.name or "").split(",") if p.strip()])
                if a.external_partner and a.external_partner.name
                else None
            ),
            "action_impact_actual": float(first_real.action_impact_actual) if first_real and first_real.action_impact_actual is not None else None,
            "action_impact_unit_realized": first_real.action_impact_unit if first_real else "",
            "added_during_unlock": added_during_unlock,
            "modified_during_unlock": modified_during_unlock,
            "activity_editable": _activity_is_editable(a, is_off_plan_activity),
            "off_plan_validation_mode": (
                getattr(off_real, "off_plan_validation_mode", None) if off_real else None
            ),
            "off_plan_validation_step": (
                getattr(off_real, "off_plan_validation_step", None) if off_real else None
            ),
            "can_approve_off_plan": bool(
                user_id and _compute_can_approve_off_plan_activity(a, user_id, role_str)
            ),
            "can_reject_off_plan": bool(
                user_id and _compute_can_approve_off_plan_activity(a, user_id, role_str)
            ),
            "can_submit_modification_review": bool(
                has_permission(user_id, role_str, "activity", "submit_modification_review")
                and
                plan.status == "VALIDATED"
                and not _plan_is_editable(plan, role_str)
                and not is_off_plan_activity
                and a.status != "SUBMITTED"
                and getattr(a, "unlock_until", None) is not None
                and now <= getattr(a, "unlock_until"),
            ),
            "can_resubmit_modification_review": bool(
                plan.status == "VALIDATED"
                and not _plan_is_editable(plan, role_str)
                and not is_off_plan_activity
                and a.status == "REJECTED"
            ),
        })
    return jsonify(out), 200


@bp.patch("/<string:plan_id>/submit")
@token_required
def submit_plan(plan_id):
    """Passer un plan à SUBMITTED (envoi pour validation). Accepte DRAFT, REJECTED, ou VALIDATED avec unlock_until (modifications à valider)."""
    denied = _require_plan_permission("submit")
    if denied:
        return denied
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    unlock_until = getattr(plan, "unlock_until", None)
    can_submit = plan.status in ("DRAFT", "REJECTED") or (
        plan.status == "VALIDATED" and unlock_until and datetime.utcnow() <= unlock_until
    )
    if not can_submit:
        return jsonify({"message": "Seuls les plans en brouillon, rejetés, ou ouverts pour modification peuvent être envoyés pour validation"}), 400

    role = (getattr(request, "role", "") or "").upper()
    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    now = datetime.utcnow()
    if _is_corporate(role):
        plan.status = "VALIDATED"
        plan.submitted_at = now
        plan.validated_at = now
        plan.unlock_until = None
        plan.validation_step = None
        write_audit(
            request.user_id,
            plan.site_id,
            "APPROVE",
            "PLAN",
            plan_id,
            f"Plan {plan.year} validé",
        )
    else:
        plan.status = "SUBMITTED"
        plan.submitted_at = now
        plan.submitted_by = request.user_id
        # When re-submitting after change request, clear unlock_until so plan is not editable during validation
        plan.unlock_until = None
        _configure_plan_validation_after_site_submit(plan, request.user_id)
        write_audit(
            request.user_id,
            plan.site_id,
            "UPDATE",
            "PLAN",
            plan_id,
            f"Soumission plan {plan.year}",
        )
    db.session.commit()
         # ── Notification corporate ────────────────────────────────────────────
    site_name = plan.site.name if plan.site else "Site inconnu"
    notify_corporate(
        title="Nouveau plan soumis",
        message=f"Le site {site_name} a soumis son plan annuel CSR {plan.year} pour validation.",
        type="info",
        site_id=plan.site_id,
        entity_type="PLAN",
        entity_id=plan.id,
        notification_category="csr_plan",
    )
    return jsonify(_plan_json_with_approval_flags(plan, request.user_id, getattr(request, "role", ""))), 200


@bp.patch("/<string:plan_id>/approve")
@token_required
def approve_plan(plan_id):
    denied = _require_plan_permission("approve")
    if denied:
        return denied
    """Approuver un plan soumis avec workflow dynamique (max 4 étapes incluant corporate)."""
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if plan.status != "SUBMITTED":
        return jsonify({"message": "Seuls les plans soumis peuvent être approuvés"}), 400

    role = (getattr(request, "role", "") or "").upper()
    step = _plan_validation_step_int(plan)
    site_steps = _plan_required_site_steps(plan)

    grade = _plan_validation_grade(plan)
    v = _get_or_create_plan_validation(plan_id, plan.site_id, grade)

    if step is None:
        return jsonify({"message": "Étape de validation invalide"}), 400
    if step <= site_steps:
        required_grade = f"level_{step}"
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Accès refusé"}), 403
        if not _user_has_grade(request.user_id, plan.site_id, required_grade):
            return jsonify({"message": f"Seul un validateur {required_grade} de ce site peut approuver à cette étape"}), 403
        v.status = "APPROVED"
        v.validated_by = request.user_id
        v.validated_at = datetime.utcnow()
        next_step = step + 1
        plan.validation_step = next_step
        next_grade = f"level_{next_step}" if next_step <= site_steps else "level_corporate"
        _get_or_create_plan_validation(plan_id, plan.site_id, next_grade)  # next step PENDING
        write_audit(
            request.user_id, plan.site_id, "APPROVE", "PLAN", plan_id,
            f"Validation {required_grade}",
        )
        db.session.commit()
        emit_tasks_refresh_for_request_actor()
        return jsonify(_plan_json_with_approval_flags(plan, request.user_id, getattr(request, "role", ""))), 200

    # Final step: corporate approves.
    if role not in ("CORPORATE_USER", "CORPORATE"):
        return jsonify({"message": "Seul un utilisateur corporate peut effectuer la validation finale"}), 403

    v.status = "APPROVED"
    v.validated_by = request.user_id
    v.validated_at = datetime.utcnow()
    plan.status = "VALIDATED"
    plan.validated_at = datetime.utcnow()
    plan.validation_step = None
    write_audit(
        request.user_id, plan.site_id, "APPROVE", "PLAN", plan_id,
        f"Plan {plan.year} validé",
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    notify_site_users(
        plan.site_id,
        title="Plan valide",
        message=f"Le plan annuel CSR {plan.year} du site {site_name} a ete valide.",
        type="success",
        entity_type="PLAN",
        entity_id=plan.id,
        notification_category="csr_plan",
    )
    return jsonify(_plan_json_with_approval_flags(plan, request.user_id, getattr(request, "role", ""))), 200


@bp.patch("/<string:plan_id>/reject")
@token_required
def reject_plan(plan_id):
    """Rejeter un plan soumis. Obligatoire: motif (comment). Optionnel: activity_ids (liste d'activités à modifier)."""
    denied = _require_plan_permission("reject")
    if denied:
        return denied
    data = request.get_json() or {}
    motif = (data.get("comment") or data.get("motif") or "").strip()
    if not motif:
        return jsonify({"message": "Un motif de rejet est obligatoire"}), 400

    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if plan.status != "SUBMITTED":
        return jsonify({"message": "Seuls les plans soumis peuvent être rejetés"}), 400

    role = (getattr(request, "role", "") or "").upper()
    step = _plan_validation_step_int(plan)
    site_steps = _plan_required_site_steps(plan)
    if step is None:
        return jsonify({"message": "Étape de validation invalide"}), 400
    if step <= site_steps:
        required_grade = f"level_{step}"
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Accès refusé"}), 403
        if not _user_has_grade(request.user_id, plan.site_id, required_grade):
            return jsonify({"message": f"Seul un validateur {required_grade} de ce site peut rejeter à cette étape"}), 403
    else:
        # Final step: corporate can reject.
        if role not in ("CORPORATE_USER", "CORPORATE"):
            return jsonify({"message": "Seul un utilisateur corporate peut rejeter à cette étape"}), 403

    raw_ids = data.get("activity_ids") or data.get("activity_id")
    if isinstance(raw_ids, str):
        raw_ids = [raw_ids] if raw_ids.strip() else []
    if not isinstance(raw_ids, list):
        raw_ids = []
    activity_ids = [str(x).strip() for x in raw_ids if x]
    if activity_ids:
        from models import CsrActivity
        valid = [
            a.id for a in CsrActivity.query.filter(
                CsrActivity.id.in_(activity_ids), CsrActivity.plan_id == plan_id
            ).all()
        ]
        activity_ids = valid

    grade = _plan_validation_grade(plan)
    v = _get_or_create_plan_validation(plan_id, plan.site_id, grade)
    v.status = "REJECTED"
    v.comment = motif
    v.rejected_activity_ids = json.dumps(activity_ids) if activity_ids else None
    v.validated_by = request.user_id
    v.validated_at = datetime.utcnow()

    plan.status = "REJECTED"
    plan.rejected_comment = motif
    plan.rejected_activity_ids = json.dumps(activity_ids) if activity_ids else None
    plan.validation_step = None
    write_audit(
        request.user_id, plan.site_id, "REJECT", "PLAN", plan_id,
        f"Plan rejeté: {motif[:200]}",
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    notify_site_users(
        plan.site_id,
        title="Plan rejete",
        message=(
            f"Le plan annuel CSR {plan.year} du site {site_name} a ete rejete. "
            f"Motif: {motif}"
        ),
        type="error",
        entity_type="PLAN",
        entity_id=plan.id,
        notification_category="csr_plan",
    )
    return jsonify(_plan_json_with_approval_flags(plan, request.user_id, getattr(request, "role", ""))), 200


@bp.delete("/<string:plan_id>")
@token_required
def delete_plan(plan_id):
    """Delete a plan. Allowed only when editable (DRAFT/REJECTED and not past unlock_until)."""
    denied = _require_plan_permission("delete")
    if denied:
        return denied
    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    role = (getattr(request, "role", "") or "").upper()
    if not _plan_is_editable(plan, role):
        return jsonify({"message": "Plan non modifiable (verrouillé ou période d'ouverture expirée)"}), 400

    if role in ("SITE_USER", "SITE"):
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    old_snapshot = snapshot_plan(plan)
    audit_delete(
        user_id=request.user_id,
        site_id=plan.site_id,
        entity_type="PLAN",
        entity_id=plan_id,
        description=f"Suppression plan {plan.year}",
        old_snapshot=old_snapshot,
    )
    # Explicitly delete activities first to avoid SQLAlchemy trying to NULL plan_id
    # (plan_id is NOT NULL on csr_activities).
    from models import CsrActivity
    db.session.query(CsrActivity).filter_by(plan_id=plan.id).delete(synchronize_session=False)
    db.session.delete(plan)
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify({"message": "Plan supprimé"}), 200
