"""
Planned CSR activities (annual plan lines) — CRUD, off-plan flow, modification review.
"""
from datetime import date, datetime
import re
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, request, jsonify
from sqlalchemy import exists

from core import db, token_required
from core.permissions import has_permission
from models import (
    CsrActivity,
    CsrPlan,
    UserSite,
    RealizedCsr,
    Category,
    ExternalPartner,
    Validation,
    CsrObjective,
    CsrCompletedObjective,
)
from features.notification_management.notification_helper import notify_corporate, notify_site_users
from features.notification_management.socketio_emit import emit_tasks_refresh_for_request_actor
from features.audit_history_management.audit_helper import (
    audit_create,
    audit_update,
    audit_delete,
    snapshot_activity,
    write_audit,
)
from features.planned_activity_management.activity_effective_status import (
    build_cr_effective_context as _build_cr_effective_context,
    effective_planned_activity_status as _effective_planned_activity_status,
)
from features.csr_plan_management.csr_plans_routes import (
    _plan_validation_mode_str,
    _user_can_access_site,
    _user_has_grade,
)
from features.change_request_management.change_requests_routes import (
    _activity_has_off_plan_realization,
    _latest_off_plan_realization,
)


def _is_corporate(role: str) -> bool:
    return (role or "").upper() in ("CORPORATE_USER", "CORPORATE")


def _compose_activity_number(plan: Optional[CsrPlan], raw_activity_number: Optional[str]) -> str:
    """Normalize activity number to SITE-YEAR-NUMBER when site/year are known."""
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


def _activity_is_editable(activity: CsrActivity, role: str = "") -> bool:
    """True if this activity can be edited: corporate always, otherwise plan editable OR activity individually unlocked."""
    if _is_corporate(role):
        return True
    if not activity or not activity.plan:
        return False
    is_off = _activity_has_off_plan_realization(activity)
    now = datetime.utcnow()
    unlock_until = getattr(activity, "unlock_until", None)
    activity_unlock_active = unlock_until is not None and now <= unlock_until
    # SUBMITTED = en revue corporate (modif / hors plan). Bloqué sauf si une demande de modif activité a été approuvée (unlock).
    if is_off and activity.status == "SUBMITTED":
        return activity_unlock_active
    if not is_off and activity.status == "SUBMITTED":
        return activity_unlock_active
    if is_off and activity.status == "REJECTED":
        return True
    if not is_off and activity.status == "REJECTED":
        return True
    if _plan_is_editable(activity.plan, role):
        return True
    # Activity-level unlock (change request approved for this activity only)
    if activity_unlock_active:
        return True
    return False


bp = Blueprint("csr_activities", __name__, url_prefix="/api/csr-activities")


def _require_activity_permission(action: str):
    role = (getattr(request, "role", "") or "").upper()
    if has_permission(getattr(request, "user_id", ""), role, "activity", action):
        return None
    return jsonify({"message": f"Permission refusée: activity.{action}"}), 403


def _parse_activity_validation_step(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _mode_site_steps(mode: str) -> int:
    return {"101": 0, "111": 1, "211": 2, "311": 3}.get(mode, 0)


def _normalize_organization(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    if s in ("INTERNAL", "EXTERNAL"):
        return s
    return None


def _normalize_contract_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().upper()
    if not s:
        return None
    if s in ("ONE_SHOT", "SUCCESSIVE_PERFORMANCE"):
        return s
    return None


def _activity_validation_mode_and_step(a: CsrActivity, plan: CsrPlan) -> Tuple[str, Optional[int]]:
    """
    (mode, step) for activity validation with dynamic step count.
    In-plan modification review: if columns on planned_activity are empty, use plan.validation_mode
    and infer step from pending Validation rows so mode 111 still goes to L1 first.
    """
    is_off = _activity_has_off_plan_realization(a)
    off_r = _latest_off_plan_realization(a) if is_off else None
    if is_off and off_r is not None:
        mode_raw = getattr(off_r, "off_plan_validation_mode", None)
        mode = str(mode_raw if mode_raw is not None else "101").strip()
        if mode not in ("101", "111", "211", "311"):
            mode = "101"
        step = _parse_activity_validation_step(getattr(off_r, "off_plan_validation_step", None))
        return mode, step
    mode_raw = getattr(a, "off_plan_validation_mode", None) or _plan_validation_mode_str(plan)
    mode = str(mode_raw if mode_raw is not None else "101").strip()
    if mode not in ("101", "111", "211", "311"):
        mode = "101"
    step = _parse_activity_validation_step(getattr(a, "off_plan_validation_step", None))
    site_steps = _mode_site_steps(mode)
    if step is None:
        for s in range(1, site_steps + 1):
            vp = Validation.query.filter_by(
                entity_type="ACTIVITY",
                entity_id=a.id,
                grade=f"level_{s}",
                status="PENDING",
            ).first()
            if vp is not None:
                step = s
                break
        if step is None:
            step = site_steps + 1
    return mode, step


def _get_or_create_activity_validation(activity_id: str, site_id: str, grade: str) -> Validation:
    v = Validation.query.filter_by(
        entity_type="ACTIVITY", entity_id=activity_id, grade=grade
    ).first()
    if v:
        return v
    v = Validation(
        entity_type="ACTIVITY",
        entity_id=activity_id,
        site_id=site_id,
        grade=grade,
        status="PENDING",
    )
    db.session.add(v)
    return v


def _activity_validation_grade(a: CsrActivity) -> str:
    """Grade for current activity validation step."""
    if not a.plan:
        return "level_corporate"
    mode, step = _activity_validation_mode_and_step(a, a.plan)
    site_steps = _mode_site_steps(mode)
    if step is not None and step <= site_steps:
        return f"level_{step}"
    return "level_corporate"


def _list_text_values(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out: List[str] = []
        for v in raw:
            s = str(v).strip()
            if s and s.lower() not in [x.lower() for x in out]:
                out.append(s)
        return out
    s = str(raw).strip()
    return [s] if s else []


def _replace_planned_objectives(activity_id: str, values: List[str]) -> None:
    CsrObjective.query.filter_by(activity_id=activity_id).delete()
    for value in values:
        db.session.add(CsrObjective(activity_id=activity_id, objective=value))


def _replace_completed_objectives(activity_id: str, values: List[str]) -> None:
    CsrCompletedObjective.query.filter_by(activity_id=activity_id).delete()
    for value in values:
        db.session.add(CsrCompletedObjective(activity_id=activity_id, objective=value, achieved=True))


def _activity_to_json(a: CsrActivity, cr_context: Optional[Dict[str, Any]] = None):
    off_r = _latest_off_plan_realization(a)
    is_off = off_r is not None
    plan = getattr(a, "plan", None)
    if plan is None and getattr(a, "plan_id", None):
        plan = CsrPlan.query.get(a.plan_id)
    compose_plan = getattr(a, "plan", None) or plan
    ctx = cr_context if cr_context is not None else _build_cr_effective_context([a])
    effective = _effective_planned_activity_status(a, plan, ctx)
    planned_objectives = [
        row.objective
        for row in CsrObjective.query.filter_by(activity_id=a.id).order_by(CsrObjective.created_at.asc()).all()
    ]
    completed_objectives = [
        row.objective
        for row in CsrCompletedObjective.query.filter_by(activity_id=a.id, achieved=True)
        .order_by(CsrCompletedObjective.created_at.asc())
        .all()
    ]
    return {
        "id": a.id,
        "plan_id": a.plan_id,
        "activity_number": _compose_activity_number(compose_plan, a.activity_number),
        "title": a.title or "",
        "description": a.description or None,
        "organization": getattr(a, "organization", None),
        "contract_type": getattr(a, "contract_type", None),
        "category_id": a.category_id,
        "status": a.status,
        "effective_status": effective,
        "is_off_plan": is_off,
        "planned_budget": float(a.planned_budget) if a.planned_budget is not None else None,
        "collaboration_nature": a.collaboration_nature or None,
        "periodicity": a.periodicity or None,
        "action_impact_target": float(a.action_impact_target) if a.action_impact_target is not None else None,
        "action_impact_unit": a.action_impact_unit or None,
        "action_impact_duration": a.action_impact_duration or None,
        "organizer": a.organizer or None,
        "edition": a.edition,
        "edition_year": getattr(a, "edition_year", None),
        "start_year": a.start_year,
        "employees_planned": getattr(a, "employees_planned", None),
        "planned_objectives": planned_objectives,
        "completed_objectives": completed_objectives,
        "external_partner_name": a.external_partner.name if getattr(a, "external_partner", None) else None,
        "off_plan_validation_mode": (
            getattr(off_r, "off_plan_validation_mode", None) if off_r else getattr(a, "off_plan_validation_mode", None)
        ),
        "off_plan_validation_step": (
            getattr(off_r, "off_plan_validation_step", None) if off_r else getattr(a, "off_plan_validation_step", None)
        ),
    }


def _activity_to_json_with_plan(a: CsrActivity, role: str = "", cr_context: Optional[Dict[str, Any]] = None):
    """Include plan and category info for list views."""
    out = _activity_to_json(a, cr_context)
    if a.plan:
        out["site_id"] = a.plan.site_id
        out["site_name"] = a.plan.site.name if a.plan.site else None
        out["site_code"] = a.plan.site.code if a.plan.site else None
        out["site_region"] = a.plan.site.region if a.plan.site else None
        out["site_country"] = a.plan.site.country if a.plan.site else None
        # Backward-friendly aliases used by some frontend exports.
        out["region"] = out["site_region"]
        out["country"] = out["site_country"]
        out["year"] = a.plan.year
        out["plan_status"] = a.plan.status
        out["plan_editable"] = _activity_is_editable(a, role)
        out["total_hc"] = getattr(a.plan, "total_hc", None)
    else:
        out["site_id"] = None
        out["site_name"] = out["site_code"] = None
        out["site_region"] = out["site_country"] = None
        out["region"] = out["country"] = None
        out["year"] = None
        out["plan_status"] = None
        out["plan_editable"] = False
        out["total_hc"] = None
    out["category_name"] = a.category.name if a.category else None
    return out


@bp.get("")
@token_required
def list_activities():
    denied = _require_activity_permission("read")
    if denied:
        return denied
    """List CSR activities. Optional: plan_id, year, exclude_realized.

    exclude_realized: when true, omits activities that already have at least one ``realized_activity`` row.
    Default: true when plan_id is absent (global planned-activities list); false when plan_id is set.
    When plan_id is absent and exclusion is on, results are also limited to current/future plan years
    and plans in VALIDATED status. SITE_USER only sees activities of their sites' plans."""
    plan_id = request.args.get("plan_id")
    year = request.args.get("year", type=int)
    # By default exclude realized when listing all; when plan_id is set (e.g. plan detail) include all.
    exclude_realized_val = request.args.get("exclude_realized")
    if exclude_realized_val is not None:
        exclude_realized = exclude_realized_val == "1"
    else:
        exclude_realized = not plan_id

    q = CsrActivity.query.options(
        db.joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
        db.joinedload(CsrActivity.category),
    )
    role = (getattr(request, "role", "") or "").upper()

    from features.csr_plan_management.plan_visibility import data_scope_site_ids

    scope = data_scope_site_ids(request.user_id, getattr(request, "role", "") or "")
    if scope is not None:
        if not scope:
            return jsonify([]), 200
        plan_ids = [p.id for p in CsrPlan.query.filter(CsrPlan.site_id.in_(scope)).with_entities(CsrPlan.id).all()]
        if not plan_ids:
            return jsonify([]), 200
        q = q.filter(CsrActivity.plan_id.in_(plan_ids))

    if plan_id:
        q = q.filter_by(plan_id=plan_id)
    if year is not None:
        q = q.join(CsrPlan).filter(CsrPlan.year == year)
    else:
        q = q.join(CsrPlan)

    if exclude_realized:
        # Hide plan lines that already have at least one realization (planned list = still to be filled).
        has_realization = exists().where(RealizedCsr.activity_id == CsrActivity.id)
        q = q.filter(~has_realization)
        # Global list (no plan_id): only current/future years and validated plans (work queue).
        if not plan_id:
            current_year = date.today().year
            q = q.filter(CsrPlan.year >= current_year)
            q = q.filter(CsrPlan.status == "VALIDATED")

    activities = q.order_by(CsrPlan.year.desc(), CsrActivity.plan_id, CsrActivity.activity_number).all()
    cr_ctx = _build_cr_effective_context(activities)
    return jsonify([_activity_to_json_with_plan(a, role, cr_ctx) for a in activities]), 200


def _user_can_access_plan(user_id: str, plan_id: str, role: str) -> bool:
    role = (role or "").upper()
    if role not in ("SITE_USER", "SITE"):
        return True
    user_sites = UserSite.query.filter_by(user_id=user_id, is_active=True).all()
    allowed_site_ids = [us.site_id for us in user_sites]
    plan = CsrPlan.query.get(plan_id)
    return plan and plan.site_id in allowed_site_ids


def _get_or_create_uncategorized():
    """Get or create the default 'Uncategorized' category for draft activities."""
    cat = Category.query.filter(db.func.lower(Category.name) == "uncategorized").first()
    if cat:
        return cat
    cat = Category(name="Uncategorized")
    db.session.add(cat)
    db.session.flush()
    return cat


@bp.post("")
@token_required
def create_activity():
    """Create a new CSR activity within a plan. When draft=true, only plan_id and title are required."""
    denied = _require_activity_permission("create")
    if denied:
        return denied
    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    if data.get("organization") not in (None, "") and _normalize_organization(data.get("organization")) is None:
        return jsonify({"message": "organization doit être INTERNAL ou EXTERNAL"}), 400
    if data.get("contract_type") not in (None, "") and _normalize_contract_type(data.get("contract_type")) is None:
        return jsonify({"message": "contract_type doit être ONE_SHOT ou SUCCESSIVE_PERFORMANCE"}), 400

    plan_id = data.get("plan_id")
    title = (data.get("title") or "").strip()
    draft = data.get("draft") is True

    if not plan_id or not title:
        return jsonify({"message": "plan_id et title sont obligatoires"}), 400

    if not _user_can_access_plan(request.user_id, plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if not _plan_is_editable(plan, getattr(request, "role", "")):
        return jsonify(
            {
                "message": "Création d’activité autorisée uniquement pour un plan modifiable (brouillon, rejeté, ou validé pendant la période d’ouverture).",
            }
        ), 403

    if draft:
        category_id = (data.get("category_id") or "").strip()
        if not category_id:
            uncat = _get_or_create_uncategorized()
            category_id = uncat.id
        activity_number = _compose_activity_number(plan, (data.get("activity_number") or "").strip())
        if not activity_number:
            import uuid
            activity_number = _compose_activity_number(plan, "Brouillon-" + str(uuid.uuid4())[:8])
        existing = CsrActivity.query.filter_by(plan_id=plan_id, activity_number=activity_number).first()
        if existing:
            import uuid
            activity_number = _compose_activity_number(plan, "Brouillon-" + str(uuid.uuid4())[:8])
    else:
        category_id = data.get("category_id")
        activity_number = _compose_activity_number(plan, (data.get("activity_number") or "").strip())
        if not category_id or not activity_number:
            return jsonify({"message": "category_id et activity_number sont obligatoires pour une création complète"}), 400
        existing = CsrActivity.query.filter_by(plan_id=plan_id, activity_number=activity_number).first()
        if existing:
            return jsonify({"message": "Une activité avec ce numéro existe déjà dans ce plan"}), 400

    def _num(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    a = CsrActivity(
        plan_id=plan_id,
        category_id=category_id,
        activity_number=activity_number,
        title=title,
        organization=_normalize_organization(data.get("organization")),
        contract_type=_normalize_contract_type(data.get("contract_type")),
        description=(data.get("description") or "").strip() or None,
        collaboration_nature=(data.get("collaboration_nature") or "").strip() or None,
        periodicity=(data.get("periodicity") or "").strip() or None,
        planned_budget=_num("planned_budget"),
        action_impact_target=_num("action_impact_target"),
        action_impact_unit=(data.get("action_impact_unit") or "").strip() or None,
        action_impact_duration=(data.get("action_impact_duration") or "").strip() or None,
        employees_planned=data.get("employees_planned") if isinstance(data.get("employees_planned"), int) else None,
        start_year=data.get("start_year") if isinstance(data.get("start_year"), int) else None,
        edition=data.get("edition") if isinstance(data.get("edition"), int) else None,
        edition_year=data.get("edition_year") if isinstance(data.get("edition_year"), int) else None,
        organizer=(data.get("organizer") or "").strip() or None,
        status="DRAFT",
    )
    # Optional external partners list (or legacy single external_partner)
    external_partners = _list_text_values(data.get("external_partners"))
    ext_name = ", ".join(external_partners) if external_partners else (data.get("external_partner") or "").strip() or None
    if ext_name:
        key = ext_name.lower()
        ep = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == key).first()
        if not ep:
            ep = ExternalPartner(name=ext_name, type="OTHER")
            db.session.add(ep)
            db.session.flush()
        a.external_partner_id = ep.id
    db.session.add(a)
    db.session.flush()
    _replace_planned_objectives(a.id, _list_text_values(data.get("planned_objectives")))
    audit_create(
        user_id=request.user_id,
        site_id=plan.site_id,
        entity_type="ACTIVITY",
        entity_id=a.id,
        description=f"Création activité {a.title or a.activity_number}",
        new_snapshot=snapshot_activity(a),
    )
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify(_activity_to_json(a)), 201


@bp.post("/plan-realized-draft")
@token_required
def create_plan_realized_draft_with_realization():
    denied = _require_activity_permission("create")
    if denied:
        return denied
    """
    Plan d'une année civile passée, modifiable : activité en DRAFT (pas hors plan) + ligne realized_csr.
    Pas de validation par activité ni notification (l'utilisateur soumet le plan entier ensuite).
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    if data.get("organization") not in (None, "") and _normalize_organization(data.get("organization")) is None:
        return jsonify({"message": "organization doit être INTERNAL ou EXTERNAL"}), 400
    if data.get("contract_type") not in (None, "") and _normalize_contract_type(data.get("contract_type")) is None:
        return jsonify({"message": "contract_type doit être ONE_SHOT ou SUCCESSIVE_PERFORMANCE"}), 400

    plan_id = data.get("plan_id")
    if not plan_id:
        return jsonify({"message": "plan_id est obligatoire"}), 400

    if not _user_can_access_plan(request.user_id, plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if not _plan_is_editable(plan, getattr(request, "role", "")):
        return jsonify({"message": "Plan non modifiable"}), 403

    plan_year = plan.year
    current_year = datetime.utcnow().year
    if plan_year >= current_year:
        return jsonify(
            {"message": "Cette création enrichie est réservée aux plans d'une année civile passée."},
        ), 400

    def _num(key, default=None):
        v = data.get(key)
        if v is None or v == "":
            return default
        try:
            return float(v) if isinstance(v, (int, float)) else float(v)
        except (TypeError, ValueError):
            return default

    def _int_val(key, default=None):
        v = data.get(key)
        if v is None or v == "":
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _str_val(key, default=None):
        v = data.get(key)
        return str(v).strip() if v is not None and str(v).strip() else default

    def _bool_val(key, default=False):
        v = data.get(key)
        if v is None:
            return default
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        s = str(v).strip().lower()
        return s in ("1", "true", "yes", "on")

    activity_number = _compose_activity_number(plan, (data.get("activity_number") or "").strip())
    title = (data.get("title") or "").strip()
    if not activity_number or not title:
        return jsonify({"message": "activity_number et title sont obligatoires"}), 400
    if len(title) > 255:
        title = title[:255]
    if len(activity_number) > 50:
        return jsonify({"message": "activity_number ne doit pas dépasser 50 caractères"}), 400

    existing = CsrActivity.query.filter_by(plan_id=plan_id, activity_number=activity_number).first()
    if existing:
        return jsonify({"message": "Une activité avec ce numéro existe déjà dans ce plan"}), 400

    description = (data.get("description") or "").strip() or None
    if description and len(description) > 65535:
        description = description[:65535]

    category_id = (data.get("category_id") or "").strip()
    if not category_id:
        return jsonify({"message": "category_id est obligatoire"}), 400
    if not Category.query.get(category_id):
        return jsonify({"message": "Catégorie introuvable"}), 400

    include_planned_details = True
    collaboration_nature = _str_val("collaboration_nature")
    if collaboration_nature and len(collaboration_nature) > 30:
        collaboration_nature = collaboration_nature[:30]

    edition = _int_val("edition")
    edition_year = _int_val("edition_year")
    start_year = _int_val("start_year")
    organizer = _str_val("organizer")

    raw_external_partners = data.get("external_partners")
    external_partners = []
    if isinstance(raw_external_partners, list):
        for item in raw_external_partners:
            s = str(item).strip()
            if s and s.lower() not in [x.lower() for x in external_partners]:
                external_partners.append(s)
    external_partner_name = ", ".join(external_partners) if external_partners else _str_val("external_partner")
    external_partner_id = None
    if external_partner_name:
        key = external_partner_name.strip().lower()
        ep = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == key).first()
        if not ep:
            ep = ExternalPartner(name=external_partner_name, type="OTHER")
            db.session.add(ep)
            db.session.flush()
        external_partner_id = ep.id

    comment = _str_val("comment")
    contact_name = _str_val("contact_name")

    # For past-year enriched creation, both planned and realized sections are mandatory.
    required_text = [
        ("description", "description est obligatoire"),
        ("organization", "organization est obligatoire"),
        ("contract_type", "contract_type est obligatoire"),
        ("periodicity", "periodicity est obligatoire"),
        ("collaboration_nature", "collaboration_nature est obligatoire"),
        ("action_impact_duration", "action_impact_duration est obligatoire"),
        ("action_impact_unit_realized", "action_impact_unit_realized est obligatoire"),
        ("organizer", "organizer est obligatoire"),
        ("comment", "comment est obligatoire"),
        ("contact_name", "contact_name est obligatoire"),
        ("contact_email", "contact_email est obligatoire"),
        ("contact_department", "contact_department est obligatoire"),
    ]
    if not external_partner_name:
        return jsonify({"message": "external_partner est obligatoire"}), 400
    for key, err in required_text:
        if not _str_val(key):
            return jsonify({"message": err}), 400

    consumed_budget_raw = data.get("consumed_budget")
    planned_budget_raw = data.get("planned_budget")
    if (consumed_budget_raw is None or consumed_budget_raw == "") and (
        planned_budget_raw is None or planned_budget_raw == ""
    ):
        return jsonify({"message": "consumed_budget est obligatoire"}), 400

    required_numbers = [
        ("action_impact_target", "action_impact_target est obligatoire"),
        ("start_year", "start_year est obligatoire"),
        ("edition", "edition est obligatoire"),
        ("participants", "participants est obligatoire"),
        ("employees_actual", "employees_actual est obligatoire"),
        ("realized_budget", "realized_budget est obligatoire"),
        ("action_impact_actual", "action_impact_actual est obligatoire"),
        ("incidents_number", "incidents_number est obligatoire"),
    ]
    for key, err in required_numbers:
        raw_v = data.get(key)
        if raw_v is None or raw_v == "":
            return jsonify({"message": err}), 400

    if not data.get("realization_date"):
        return jsonify({"message": "realization_date est obligatoire"}), 400

    realization_date = None
    rd = data.get("realization_date")
    if rd:
        try:
            realization_date = datetime.strptime(str(rd)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            realization_date = None

    year = plan_year
    if realization_date:
        if realization_date.year != plan_year:
            return jsonify(
                {"message": f"La date de réalisation doit être comprise dans l'année du plan ({plan_year})."},
            ), 400
        month = realization_date.month
    else:
        month = data.get("month")
        if month is not None:
            try:
                month = int(month)
            except (TypeError, ValueError):
                return jsonify({"message": "month doit être un entier"}), 400
        else:
            month = 12
        if month < 1 or month > 12:
            return jsonify({"message": "month doit être entre 1 et 12"}), 400

    rb = _num("realized_budget")
    planned_budget = _num("consumed_budget")
    if planned_budget is None:
        planned_budget = _num("planned_budget")
    action_impact_target = _num("action_impact_target")

    a = CsrActivity(
        plan_id=plan_id,
        category_id=category_id,
        activity_number=activity_number,
        title=title,
        description=description,
        organization=_normalize_organization(data.get("organization")),
        contract_type=_normalize_contract_type(data.get("contract_type")),
        collaboration_nature=collaboration_nature,
        periodicity=_str_val("periodicity"),
        organizer=organizer,
        edition=edition,
        edition_year=edition_year,
        start_year=start_year,
        planned_budget=planned_budget if planned_budget is not None else rb,
        action_impact_target=action_impact_target,
        action_impact_unit=_str_val("action_impact_unit"),
        action_impact_duration=_str_val("action_impact_duration"),
        employees_planned=_int_val("employees_planned"),
        external_partner_id=external_partner_id,
        status="DRAFT",
    )
    db.session.add(a)
    db.session.flush()
    _replace_planned_objectives(a.id, _list_text_values(data.get("planned_objectives")))

    r = RealizedCsr(
        activity_id=a.id,
        realized_budget=rb,
        participants=_int_val("employees_actual") if _int_val("employees_actual") is not None else _int_val("participants"),
        corporate_image_improved=_bool_val("corporate_image_improved", default=False),
        incidents_number=_int_val("incidents_number"),
        total_hc=getattr(plan, "total_hc", None),
        action_impact_actual=_num("action_impact_actual"),
        action_impact_unit=_str_val("action_impact_unit_realized"),
        is_off_plan=False,
        off_plan_validation_mode=None,
        off_plan_validation_step=None,
        status="DRAFT",
        realization_date=realization_date,
        comment=comment,
        contact_name=contact_name,
        contact_email=_str_val("contact_email"),
        contact_department=_str_val("contact_department"),
        created_by=request.user_id,
    )
    db.session.add(r)
    _replace_completed_objectives(a.id, _list_text_values(data.get("completed_objectives")))

    audit_create(
        user_id=request.user_id,
        site_id=plan.site_id,
        entity_type="ACTIVITY",
        entity_id=a.id,
        description=f"Création activité (plan année réalisée, brouillon) {a.title or a.activity_number}",
        new_snapshot=snapshot_activity(a),
    )
    db.session.commit()
    emit_tasks_refresh_for_request_actor()

    out = _activity_to_json(a)
    out["site_id"] = plan.site_id
    return jsonify({"activity": out, "realization": {"id": r.id, "activity_id": a.id}}), 201


@bp.post("/off-plan-realization")
@token_required
def create_off_plan_realization():
    """Create an off-plan activity and one RealizedCsr row; notify corporate with chosen validation mode."""
    denied = _require_activity_permission("create")
    if denied:
        return denied
    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    if data.get("organization") not in (None, "") and _normalize_organization(data.get("organization")) is None:
        return jsonify({"message": "organization doit être INTERNAL ou EXTERNAL"}), 400
    if data.get("contract_type") not in (None, "") and _normalize_contract_type(data.get("contract_type")) is None:
        return jsonify({"message": "contract_type doit être ONE_SHOT ou SUCCESSIVE_PERFORMANCE"}), 400

    plan_id = data.get("plan_id")
    if not plan_id:
        return jsonify({"message": "plan_id est obligatoire"}), 400

    role = (getattr(request, "role", "") or "").upper()
    corporate_submit = _is_corporate(role)

    if not _user_can_access_plan(request.user_id, plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à ce plan"}), 403

    plan = CsrPlan.query.get(plan_id)
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    # Off-plan activities are allowed only for current year and past years.
    current_year = datetime.utcnow().year
    plan_year_val = getattr(plan, "year", None)
    if plan_year_val is not None and plan_year_val > current_year:
        return jsonify({"message": "Les activités hors plan ne peuvent être soumises que pour l'année en cours ou les années passées."}), 403
    # Off-plan on current/future-year plans: site users need a VALIDATED plan. Past-year plans can stay DRAFT/etc. for catch-up.
    is_past_plan_year = plan_year_val is not None and plan_year_val < current_year
    if getattr(plan, "status", None) != "VALIDATED" and not corporate_submit and not is_past_plan_year:
        return jsonify({"message": f"Les activités hors plan ne peuvent être soumises que pour un plan validé. Statut actuel: {getattr(plan, 'status', None)}"}), 403

    plan_year = plan.year

    vm = (data.get("validation_mode") or "101").strip()
    if vm not in ("101", "111", "211", "311"):
        vm = "101"
    mode_label = (
        "Corporate uniquement (101)"
        if vm == "101"
        else "Tous niveaux — manager puis corporate (111)"
    )

    def _num(key, default=None):
        v = data.get(key)
        if v is None or v == "":
            return default
        try:
            return float(v) if isinstance(v, (int, float)) else float(v)
        except (TypeError, ValueError):
            return default

    def _int_val(key, default=None):
        v = data.get(key)
        if v is None or v == "":
            return default
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def _str_val(key, default=None):
        v = data.get(key)
        return str(v).strip() if v is not None and str(v).strip() else default

    activity_number = _compose_activity_number(plan, (data.get("activity_number") or "").strip())
    title = (data.get("title") or "").strip()
    if not activity_number or not title:
        return jsonify({"message": "activity_number et title sont obligatoires"}), 400
    if len(title) > 255:
        title = title[:255]
    if len(activity_number) > 50:
        return jsonify({"message": "activity_number ne doit pas dépasser 50 caractères"}), 400

    existing = CsrActivity.query.filter_by(plan_id=plan_id, activity_number=activity_number).first()
    if existing:
        return jsonify({"message": "Une activité avec ce numéro existe déjà dans ce plan"}), 400

    description = (data.get("description") or "").strip() or None
    if description and len(description) > 65535:
        description = description[:65535]

    category_id = (data.get("category_id") or "").strip()
    if not category_id:
        return jsonify({"message": "category_id est obligatoire"}), 400
    if not Category.query.get(category_id):
        return jsonify({"message": "Catégorie introuvable"}), 400

    collaboration_nature = _str_val("collaboration_nature")
    if collaboration_nature and len(collaboration_nature) > 30:
        collaboration_nature = collaboration_nature[:30]

    edition = _int_val("edition")
    edition_year = _int_val("edition_year")
    start_year = _int_val("start_year")
    organizer = _str_val("organizer")

    raw_external_partners = data.get("external_partners")
    external_partners = []
    if isinstance(raw_external_partners, list):
        for item in raw_external_partners:
            s = str(item).strip()
            if s and s.lower() not in [x.lower() for x in external_partners]:
                external_partners.append(s)
    external_partner_name = ", ".join(external_partners) if external_partners else _str_val("external_partner")
    external_partner_id = None
    if external_partner_name:
        key = external_partner_name.strip().lower()
        ep = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == key).first()
        if not ep:
            ep = ExternalPartner(name=external_partner_name, type="OTHER")
            db.session.add(ep)
            db.session.flush()
        external_partner_id = ep.id

    comment = _str_val("comment")
    contact_name = _str_val("contact_name")

    realization_date = None
    rd = data.get("realization_date")
    if rd:
        try:
            realization_date = datetime.strptime(str(rd)[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            realization_date = None

    # Année de réalisation = année du plan ; la date (si fournie) doit être dans cette année civile.
    year = plan_year
    if realization_date:
        if realization_date.year != plan_year:
            return jsonify(
                {"message": f"La date de réalisation doit être comprise dans l'année du plan ({plan_year})."},
            ), 400
        month = realization_date.month
    else:
        month = data.get("month")
        if month is not None:
            try:
                month = int(month)
            except (TypeError, ValueError):
                return jsonify({"message": "month doit être un entier"}), 400
        else:
            month = datetime.utcnow().month
        if month < 1 or month > 12:
            return jsonify({"message": "month doit être entre 1 et 12"}), 400

    consumed_budget = _num("consumed_budget")
    if consumed_budget is None:
        consumed_budget = _num("planned_budget")
    realized_budget = _num("realized_budget")
    if is_past_plan_year:
        if consumed_budget is None:
            return jsonify({"message": "consumed_budget est obligatoire pour un plan d'année passée"}), 400
        if realized_budget is None:
            return jsonify({"message": "realized_budget est obligatoire pour un plan d'année passée"}), 400

    a = CsrActivity(
        plan_id=plan_id,
        category_id=category_id,
        activity_number=activity_number,
        title=title,
        description=description,
        organization=_normalize_organization(data.get("organization")),
        contract_type=_normalize_contract_type(data.get("contract_type")),
        collaboration_nature=collaboration_nature,
        periodicity=_str_val("periodicity"),
        organizer=organizer,
        edition=edition,
        edition_year=edition_year,
        start_year=start_year,
        planned_budget=consumed_budget,
        action_impact_target=_num("action_impact_target"),
        action_impact_unit=_str_val("action_impact_unit"),
        action_impact_duration=_str_val("action_impact_duration"),
        employees_planned=_int_val("employees_planned"),
        external_partner_id=external_partner_id,
        status="VALIDATED" if corporate_submit else "SUBMITTED",
    )
    db.session.add(a)
    db.session.flush()
    _replace_planned_objectives(a.id, _list_text_values(data.get("planned_objectives")))

    r = RealizedCsr(
        activity_id=a.id,
        realized_budget=realized_budget,
        participants=_int_val("employees_actual") if _int_val("employees_actual") is not None else _int_val("participants"),
        corporate_image_improved=data.get("corporate_image_improved"),
        incidents_number=_int_val("incidents_number"),
        total_hc=getattr(plan, "total_hc", None),
        action_impact_actual=_num("action_impact_actual"),
        action_impact_unit=_str_val("action_impact_unit_realized"),
        is_off_plan=True,
        off_plan_validation_mode=None if corporate_submit else vm,
        off_plan_validation_step=None if corporate_submit else (_mode_site_steps(vm) + 1 if _mode_site_steps(vm) == 0 else 1),
        status="VALIDATED" if corporate_submit else "SUBMITTED",
        realization_date=realization_date,
        comment=comment,
        contact_name=contact_name,
        contact_email=_str_val("contact_email"),
        contact_department=_str_val("contact_department"),
        created_by=request.user_id,
    )
    db.session.add(r)
    _replace_completed_objectives(a.id, _list_text_values(data.get("completed_objectives")))

    if not corporate_submit:
        first_grade = "level_1" if _mode_site_steps(vm) > 0 else "level_corporate"
        _get_or_create_activity_validation(a.id, plan.site_id, first_grade)

    audit_create(
        user_id=request.user_id,
        site_id=plan.site_id,
        entity_type="ACTIVITY",
        entity_id=a.id,
        description=f"Création activité hors plan {a.title or a.activity_number}",
        new_snapshot=snapshot_activity(a),
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    if corporate_submit:
        notify_site_users(
            plan.site_id,
            title="Activité hors plan validée",
            message=(
                f"L'activité hors plan {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) a été validée."
            ),
            type="success",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    elif vm == "111":
        notify_site_users(
            site_id=plan.site_id,
            title="Activité hors plan — validation niveau 1",
            message=(
                f"Une activité hors plan ({a.activity_number}: {a.title}) pour le plan {plan.year} "
                f"({site_name}) attend la validation niveau 1."
            ),
            type="info",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    else:
        notify_corporate(
            title="Activité hors plan — validation corporate",
            message=(
                f"Le site {site_name} a déclaré une activité hors plan pour le plan {plan.year} "
                f"({a.activity_number}: {a.title}). Mode 101 (corporate uniquement). "
                f"Réalisation : {month}/{year}."
            ),
            type="info",
            site_id=plan.site_id,
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )

    out = _activity_to_json(a)
    out["site_id"] = plan.site_id
    return jsonify({"activity": out, "realization": {"id": r.id, "activity_id": a.id}}), 201


@bp.patch("/<string:activity_id>/submit-modification-review")
@token_required
def submit_activity_modification_review(activity_id: str):
    """Après déverrouillage d'une activité seule (plan validé, pas unlock plan) : envoyer les changements pour validation (101/111)."""
    denied = _require_activity_permission("submit_modification_review")
    if denied:
        return denied
    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    plan = a.plan
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404
    if plan.status != "VALIDATED":
        return jsonify({"message": "Le plan doit être validé"}), 400
    if _plan_is_editable(plan, getattr(request, "role", "")):
        return jsonify({"message": "Utilisez la soumission du plan pour les modifications globales"}), 400
    if _activity_has_off_plan_realization(a):
        return jsonify({"message": "Réservé aux activités du plan annuel"}), 400
    if a.status == "SUBMITTED":
        return jsonify({"message": "Cette activité est déjà en attente de validation"}), 400
    if not _user_can_access_plan(request.user_id, a.plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403
    now = datetime.utcnow()
    unlock_until = getattr(a, "unlock_until", None)
    if unlock_until is None or now > unlock_until:
        return jsonify({"message": "La fenêtre de modification de cette activité a expiré"}), 400

    role = (getattr(request, "role", "") or "").upper()
    vm = _plan_validation_mode_str(plan)
    if vm not in ("101", "111", "211", "311"):
        vm = "101"
    if _is_corporate(role):
        a.off_plan_validation_mode = None
        a.off_plan_validation_step = None
        a.status = "VALIDATED"
    else:
        a.off_plan_validation_mode = vm
        a.off_plan_validation_step = (_mode_site_steps(vm) + 1) if _mode_site_steps(vm) == 0 else 1
        a.status = "SUBMITTED"
    a.unlock_until = None
    a.unlock_since = None

    if not _is_corporate(role):
        Validation.query.filter_by(entity_type="ACTIVITY", entity_id=activity_id).delete(synchronize_session=False)
        first_grade = "level_1" if _mode_site_steps(vm) > 0 else "level_corporate"
        _get_or_create_activity_validation(a.id, plan.site_id, first_grade)

    write_audit(
        request.user_id,
        plan.site_id,
        "UPDATE",
        "ACTIVITY",
        activity_id,
        "Soumission modification activité (plan validé) pour validation",
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    if _is_corporate(role):
        notify_site_users(
            plan.site_id,
            title="Modification d'activité validée",
            message=(
                f"La modification de l'activité {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) "
                f"a été validée."
            ),
            type="success",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    elif vm == "111":
        notify_site_users(
            site_id=plan.site_id,
            title="Modification d'activité — validation niveau 1",
            message=(
                f"Une modification d'activité ({a.activity_number}: {a.title}) pour le plan {plan.year} "
                f"({site_name}) attend la validation niveau 1."
            ),
            type="info",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    else:
        notify_corporate(
            title="Modification d'activité — validation corporate",
            message=(
                f"Le site {site_name} a soumis une modification d'activité pour le plan {plan.year} "
                f"({a.activity_number}: {a.title}). Mode 101."
            ),
            type="info",
            site_id=plan.site_id,
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    return jsonify(_activity_to_json(a)), 200


@bp.patch("/<string:activity_id>/approve")
@token_required
def approve_off_plan_activity(activity_id: str):
    denied = _require_activity_permission("approve")
    if denied:
        return denied
    """
    Approuver une activité hors plan soumise, ou une modification d'activité sur plan validé (SUBMITTED).
    Mode 101: corporate valide (étape 2).
    Mode 111: niveau 1 site puis corporate (étape 2).
    """
    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if a.status != "SUBMITTED":
        return jsonify({"message": "Seules les activités en attente de validation peuvent être approuvées"}), 400

    plan = a.plan
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404

    is_off = _activity_has_off_plan_realization(a)
    in_plan_mod_review = not is_off and plan.status == "VALIDATED"
    if not is_off and not in_plan_mod_review:
        return jsonify({"message": "Réservé aux activités hors plan ou aux modifications soumises sur plan validé"}), 400

    role = (getattr(request, "role", "") or "").upper()
    off_r = _latest_off_plan_realization(a) if is_off else None
    mode, step = _activity_validation_mode_and_step(a, plan)

    grade = _activity_validation_grade(a)
    v = _get_or_create_activity_validation(a.id, plan.site_id, grade)

    site_steps = _mode_site_steps(mode)
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
        if off_r is not None:
            off_r.off_plan_validation_step = next_step
        else:
            a.off_plan_validation_step = next_step
        next_grade = f"level_{next_step}" if next_step <= site_steps else "level_corporate"
        _get_or_create_activity_validation(a.id, plan.site_id, next_grade)
        audit_msg = (
            f"Validation {required_grade} modification activité (plan validé)"
            if in_plan_mod_review
            else f"Validation {required_grade} activité hors plan"
        )
        write_audit(request.user_id, plan.site_id, "APPROVE", "ACTIVITY", activity_id, audit_msg)
        db.session.commit()
        site_name = plan.site.name if plan.site else "Site inconnu"
        title = (
            "Modification d'activité — validation corporate"
            if in_plan_mod_review
            else "Activité hors plan — validation corporate"
        )
        msg = (
            f"La modification ({a.activity_number}: {a.title}), plan {plan.year}, site {site_name}, "
            f"attend la validation corporate."
            if in_plan_mod_review
            else (
                f"L'activité hors plan ({a.activity_number}: {a.title}), plan {plan.year}, site {site_name}, "
                f"attend la validation corporate."
            )
        )
        notify_corporate(
            title=title,
            message=msg,
            type="info",
            site_id=plan.site_id,
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
        return jsonify(_activity_to_json(a)), 200

    if role not in ("CORPORATE_USER", "CORPORATE"):
        return jsonify({"message": "Seul un utilisateur corporate peut valider à cette étape"}), 403

    v.status = "APPROVED"
    v.validated_by = request.user_id
    v.validated_at = datetime.utcnow()
    a.status = "VALIDATED"
    if off_r is not None:
        off_r.off_plan_validation_step = None
        off_r.off_plan_validation_mode = None
        off_r.status = "VALIDATED"
    else:
        a.off_plan_validation_step = None
        a.off_plan_validation_mode = None
    audit_desc = (
        f"Modification activité validée: {a.title or a.activity_number}"
        if in_plan_mod_review
        else f"Activité hors plan validée: {a.title or a.activity_number}"
    )
    write_audit(request.user_id, plan.site_id, "APPROVE", "ACTIVITY", activity_id, audit_desc)
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    if in_plan_mod_review:
        notify_site_users(
            plan.site_id,
            title="Modification d'activité validée",
            message=(
                f"La modification de l'activité {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) "
                f"a été validée."
            ),
            type="success",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    else:
        notify_site_users(
            plan.site_id,
            title="Activité hors plan validée",
            message=(
                f"L'activité hors plan {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) a été validée."
            ),
            type="success",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    return jsonify(_activity_to_json(a)), 200


@bp.patch("/<string:activity_id>/reject")
@token_required
def reject_off_plan_activity(activity_id: str):
    """Rejeter une activité hors plan soumise (motif obligatoire)."""
    denied = _require_activity_permission("reject")
    if denied:
        return denied
    data = request.get_json() or {}
    motif = (data.get("comment") or data.get("motif") or "").strip()
    if not motif:
        return jsonify({"message": "Un motif de rejet est obligatoire"}), 400

    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if a.status != "SUBMITTED":
        return jsonify({"message": "Seules les activités en attente de validation peuvent être rejetées"}), 400

    plan = a.plan
    if not plan:
        return jsonify({"message": "Plan introuvable"}), 404

    is_off = _activity_has_off_plan_realization(a)
    in_plan_mod_review = not is_off and plan.status == "VALIDATED"
    if not is_off and not in_plan_mod_review:
        return jsonify({"message": "Réservé aux activités hors plan ou aux modifications soumises sur plan validé"}), 400

    role = (getattr(request, "role", "") or "").upper()
    off_r = _latest_off_plan_realization(a) if is_off else None
    mode, step = _activity_validation_mode_and_step(a, plan)

    site_steps = _mode_site_steps(mode)
    if step is None:
        return jsonify({"message": "Étape de validation invalide"}), 400
    if step <= site_steps:
        required_grade = f"level_{step}"
        if not _user_can_access_site(request.user_id, plan.site_id):
            return jsonify({"message": "Accès refusé"}), 403
        if not _user_has_grade(request.user_id, plan.site_id, required_grade):
            return jsonify({"message": f"Seul un validateur {required_grade} de ce site peut rejeter à cette étape"}), 403
    else:
        if role not in ("CORPORATE_USER", "CORPORATE"):
            return jsonify({"message": "Seul un utilisateur corporate peut rejeter à cette étape"}), 403

    grade = _activity_validation_grade(a)
    v = _get_or_create_activity_validation(a.id, plan.site_id, grade)
    v.status = "REJECTED"
    v.comment = motif
    v.rejected_activity_ids = None
    v.validated_by = request.user_id
    v.validated_at = datetime.utcnow()

    a.status = "REJECTED"
    if off_r is not None:
        off_r.off_plan_validation_step = None
        off_r.off_plan_validation_mode = None
        off_r.status = "REJECTED"
    else:
        a.off_plan_validation_step = None
        a.off_plan_validation_mode = None
    if in_plan_mod_review:
        a.unlock_until = None
        a.unlock_since = None
    write_audit(
        request.user_id,
        plan.site_id,
        "REJECT",
        "ACTIVITY",
        activity_id,
        (
            f"Modification activité rejetée: {motif[:200]}"
            if in_plan_mod_review
            else f"Activité hors plan rejetée: {motif[:200]}"
        ),
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    if in_plan_mod_review:
        notify_site_users(
            plan.site_id,
            title="Modification d'activité rejetée",
            message=(
                f"La modification de l'activité {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) "
                f"a été rejetée. Motif: {motif}"
            ),
            type="error",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    else:
        notify_site_users(
            plan.site_id,
            title="Activité hors plan rejetée",
            message=(
                f"L'activité hors plan {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) a été rejetée. "
                f"Motif: {motif}"
            ),
            type="error",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    return jsonify(_activity_to_json(a)), 200


@bp.patch("/<string:activity_id>/resubmit-off-plan")
@token_required
def resubmit_off_plan_activity(activity_id: str):
    """Après rejet : renvoyer en validation (activité hors plan ou modification sur plan validé)."""
    denied = _require_activity_permission("resubmit")
    if denied:
        return denied
    data = request.get_json() or {}
    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if a.status != "REJECTED":
        return jsonify({"message": "Seules les activités rejetées peuvent être renvoyées"}), 400

    plan = a.plan
    if not plan or getattr(plan, "status", None) != "VALIDATED":
        return jsonify({"message": "Le plan doit être validé"}), 400

    if not _user_can_access_plan(request.user_id, a.plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403

    is_off = _activity_has_off_plan_realization(a)
    in_plan_mod = not is_off
    if in_plan_mod and _plan_is_editable(plan, getattr(request, "role", "")):
        return jsonify({"message": "Utilisez la soumission du plan pour les modifications globales"}), 400

    off_r = _latest_off_plan_realization(a) if is_off else None
    default_vm = _plan_validation_mode_str(plan) if in_plan_mod else "101"
    raw_vm = (
        data.get("validation_mode")
        or (getattr(off_r, "off_plan_validation_mode", None) if off_r is not None else None)
        or getattr(a, "off_plan_validation_mode", None)
        or default_vm
    )
    vm = str(raw_vm or "101").strip()
    if vm not in ("101", "111", "211", "311"):
        vm = "101"
    role = (getattr(request, "role", "") or "").upper()
    if _is_corporate(role):
        if off_r is not None:
            off_r.off_plan_validation_mode = None
            off_r.off_plan_validation_step = None
            off_r.status = "VALIDATED"
        else:
            a.off_plan_validation_mode = None
            a.off_plan_validation_step = None
        a.status = "VALIDATED"
    else:
        if off_r is not None:
            off_r.off_plan_validation_mode = vm
            off_r.off_plan_validation_step = (_mode_site_steps(vm) + 1) if _mode_site_steps(vm) == 0 else 1
            off_r.status = "SUBMITTED"
        else:
            a.off_plan_validation_mode = vm
            a.off_plan_validation_step = (_mode_site_steps(vm) + 1) if _mode_site_steps(vm) == 0 else 1
        a.status = "SUBMITTED"

        Validation.query.filter_by(entity_type="ACTIVITY", entity_id=activity_id).delete(
            synchronize_session=False
        )
        first_grade = "level_1" if _mode_site_steps(vm) > 0 else "level_corporate"
        _get_or_create_activity_validation(a.id, plan.site_id, first_grade)

    audit_desc = (
        "Renvoi modification activité (plan validé) pour validation"
        if in_plan_mod
        else "Renvoi activité hors plan pour validation"
    )
    write_audit(
        request.user_id,
        plan.site_id,
        "UPDATE",
        "ACTIVITY",
        activity_id,
        audit_desc,
    )
    db.session.commit()

    site_name = plan.site.name if plan.site else "Site inconnu"
    if _is_corporate(role):
        notify_site_users(
            plan.site_id,
            title=(
                "Modification d'activité validée"
                if in_plan_mod
                else "Activité hors plan validée"
            ),
            message=(
                f"La modification de l'activité {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) a été validée."
                if in_plan_mod
                else f"L'activité hors plan {a.activity_number}: {a.title} (plan {plan.year}, {site_name}) a été validée."
            ),
            type="success",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    elif vm == "111":
        notify_site_users(
            site_id=plan.site_id,
            title=(
                "Modification d'activité — validation niveau 1"
                if in_plan_mod
                else "Activité hors plan — validation niveau 1"
            ),
            message=(
                f"Une modification d'activité ({a.activity_number}: {a.title}) pour le plan {plan.year} "
                f"({site_name}) attend la validation niveau 1."
                if in_plan_mod
                else (
                    f"Une activité hors plan ({a.activity_number}: {a.title}) pour le plan {plan.year} "
                    f"({site_name}) attend la validation niveau 1."
                )
            ),
            type="info",
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    else:
        notify_corporate(
            title=(
                "Modification d'activité — validation corporate"
                if in_plan_mod
                else "Activité hors plan — validation corporate"
            ),
            message=(
                f"Le site {site_name} a renvoyé une modification d'activité pour le plan {plan.year} "
                f"({a.activity_number}: {a.title}). Mode 101."
                if in_plan_mod
                else (
                    f"Le site {site_name} a renvoyé une activité hors plan pour le plan {plan.year} "
                    f"({a.activity_number}: {a.title}). Mode 101."
                )
            ),
            type="info",
            site_id=plan.site_id,
            entity_type="ACTIVITY",
            entity_id=a.id,
            notification_category="activity_validation",
        )
    return jsonify(_activity_to_json(a)), 200


@bp.get("/<activity_id>")
@token_required
def get_activity(activity_id: str):
    """Get a single CSR activity by id (for edit). SITE_USER only if plan's site is allowed."""
    denied = _require_activity_permission("read")
    if denied:
        return denied
    from sqlalchemy.orm import joinedload
    a = (
        CsrActivity.query.options(
            db.joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
            db.joinedload(CsrActivity.category),
            db.joinedload(CsrActivity.external_partner),
        )
        .filter_by(id=activity_id)
        .first()
    )
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if not _user_can_access_plan(request.user_id, a.plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403
    return jsonify(_activity_to_json_with_plan(a, getattr(request, "role", ""))), 200


def _activity_site_id(a: CsrActivity):
    return a.plan.site_id if a.plan else None


@bp.put("/<activity_id>")
@token_required
def update_activity(activity_id: str):
    """Update a CSR activity. SITE_USER only if plan's site is allowed. Plan must not be VALIDATED (locked)."""
    denied = _require_activity_permission("update")
    if denied:
        return denied
    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if not _user_can_access_plan(request.user_id, a.plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403
    if not _activity_is_editable(a, getattr(request, "role", "")):
        return jsonify({"message": "Plan validé (verrouillé) ou période d'ouverture expirée. Utilisez une demande de modification."}), 403

    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400

    category_id = data.get("category_id")
    activity_number = _compose_activity_number(a.plan, (data.get("activity_number") or "").strip())
    title = (data.get("title") or "").strip()
    if "organization" in data and _normalize_organization(data.get("organization")) is None:
        return jsonify({"message": "organization doit être INTERNAL ou EXTERNAL"}), 400
    if "contract_type" in data and _normalize_contract_type(data.get("contract_type")) is None:
        return jsonify({"message": "contract_type doit être ONE_SHOT ou SUCCESSIVE_PERFORMANCE"}), 400

    if not category_id or not activity_number or not title:
        return jsonify({"message": "category_id, activity_number et title sont obligatoires"}), 400

    existing = CsrActivity.query.filter_by(plan_id=a.plan_id, activity_number=activity_number).first()
    if existing and existing.id != activity_id:
        return jsonify({"message": "Une activité avec ce numéro existe déjà dans ce plan"}), 400

    old_snapshot = snapshot_activity(a)
    def _num(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _int_val(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _str_val(key):
        v = data.get(key)
        return (v.strip() if isinstance(v, str) and v.strip() else None) or None

    a.category_id = category_id
    a.activity_number = activity_number
    a.title = title
    a.description = (data.get("description") or "").strip() or None
    if "organization" in data:
        a.organization = _normalize_organization(data.get("organization"))
    if "contract_type" in data:
        a.contract_type = _normalize_contract_type(data.get("contract_type"))
    a.planned_budget = _num("planned_budget")
    if "collaboration_nature" in data:
        a.collaboration_nature = _str_val("collaboration_nature")
    if "periodicity" in data:
        a.periodicity = _str_val("periodicity")
    if "organizer" in data:
        a.organizer = _str_val("organizer")
    if "action_impact_target" in data:
        a.action_impact_target = _num("action_impact_target")
    if "action_impact_unit" in data:
        a.action_impact_unit = _str_val("action_impact_unit")
    if "action_impact_duration" in data:
        a.action_impact_duration = _str_val("action_impact_duration")
    if "employees_planned" in data:
        a.employees_planned = _int_val("employees_planned")
    if "edition" in data:
        a.edition = _int_val("edition")
    if "edition_year" in data:
        a.edition_year = _int_val("edition_year")
    if "start_year" in data:
        a.start_year = _int_val("start_year")
    if "external_partners" in data:
        partners = _list_text_values(data.get("external_partners"))
        if partners:
            combined = ", ".join(partners)
            key = combined.strip().lower()
            ep = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == key).first()
            if not ep:
                ep = ExternalPartner(name=combined, type="OTHER")
                db.session.add(ep)
                db.session.flush()
            a.external_partner_id = ep.id
        else:
            a.external_partner_id = None
    if "external_partner" in data:
        ext_name = _str_val("external_partner")
        if ext_name:
            key = ext_name.strip().lower()
            ep = ExternalPartner.query.filter(db.func.lower(ExternalPartner.name) == key).first()
            if not ep:
                ep = ExternalPartner(name=ext_name, type="OTHER")
                db.session.add(ep)
                db.session.flush()
            a.external_partner_id = ep.id
        else:
            a.external_partner_id = None
    if "planned_objectives" in data:
        _replace_planned_objectives(a.id, _list_text_values(data.get("planned_objectives")))
    audit_update(
        user_id=request.user_id,
        site_id=_activity_site_id(a),
        entity_type="ACTIVITY",
        entity_id=activity_id,
        description=f"Modification activité {a.title or a.activity_number}",
        old_snapshot=old_snapshot,
        new_snapshot=snapshot_activity(a),
    )
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify(_activity_to_json(a)), 200


@bp.delete("/<activity_id>")
@token_required
def delete_activity(activity_id: str):
    """Delete a CSR activity. SITE_USER only if plan's site is allowed. Plan must not be VALIDATED (locked)."""
    denied = _require_activity_permission("delete")
    if denied:
        return denied
    a = CsrActivity.query.get(activity_id)
    if not a:
        return jsonify({"message": "Activité introuvable"}), 404
    if not _user_can_access_plan(request.user_id, a.plan_id, getattr(request, "role", "")):
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403
    if not _activity_is_editable(a, getattr(request, "role", "")):
        return jsonify({"message": "Plan validé (verrouillé) ou période d'ouverture expirée. Utilisez une demande de modification."}), 403
    old_snapshot = snapshot_activity(a)
    audit_delete(
        user_id=request.user_id,
        site_id=_activity_site_id(a),
        entity_type="ACTIVITY",
        entity_id=activity_id,
        description=f"Suppression activité {a.title or a.activity_number}",
        old_snapshot=old_snapshot,
    )
    # Ensure realizations are removed (ORM/DB FK may otherwise try to null activity_id).
    RealizedCsr.query.filter_by(activity_id=activity_id).delete(synchronize_session=False)
    db.session.delete(a)
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify({"message": "Activité supprimée"}), 200
