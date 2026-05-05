"""
Realized CSR activities endpoints.
List and create realized CSR records (saisie réalisations).
Create/update/delete only when the activity's plan is editable (user must submit a change request for locked plans).
"""
from datetime import datetime
import re
from typing import Optional

from flask import Blueprint, request, jsonify

from core import db, token_required
from models import RealizedCsr, CsrActivity, CsrPlan, CsrObjective, CsrCompletedObjective
from features.csr_plan_management.plan_visibility import data_scope_site_ids
from features.audit_history_management.audit_helper import audit_delete
from features.notification_management.notification_helper import notify_corporate
from features.notification_management.socketio_emit import emit_tasks_refresh_for_request_actor

bp = Blueprint("realized_csr", __name__, url_prefix="/api/realized-csr")


def _compose_activity_number(plan: Optional[CsrPlan], raw_activity_number: Optional[str]) -> str:
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


def _is_corporate(role: str) -> bool:
    return (role or "").upper() in ("CORPORATE", "CORPORATE_USER")


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
    """True if this activity can be edited: plan editable OR activity individually unlocked.
    Parity with planned_csr_routes (incl. in-plan modification review SUBMITTED/REJECTED)."""
    if not activity or not activity.plan:
        return False
    if getattr(activity, "is_off_plan", False) and activity.status == "SUBMITTED":
        return False
    if not getattr(activity, "is_off_plan", False) and activity.status == "SUBMITTED":
        return False
    if getattr(activity, "is_off_plan", False) and activity.status == "REJECTED":
        return True
    if not getattr(activity, "is_off_plan", False) and activity.status == "REJECTED":
        return True
    if _plan_is_editable(activity.plan, role):
        return True
    unlock_until = getattr(activity, "unlock_until", None)
    if unlock_until and datetime.utcnow() <= unlock_until:
        return True
    return False


def _realized_to_json(r: RealizedCsr, role: str = ""):
    act = r.activity
    plan = act.plan if act else None
    plan_editable = _activity_is_editable(act, role) if act else (plan and _plan_is_editable(plan, role))
    planned_objectives = [
        row.objective
        for row in CsrObjective.query.filter_by(activity_id=r.activity_id).order_by(CsrObjective.created_at.asc()).all()
    ]
    completed_objectives = [
        row.objective
        for row in CsrCompletedObjective.query.filter_by(activity_id=r.activity_id, achieved=True)
        .order_by(CsrCompletedObjective.created_at.asc())
        .all()
    ]
    return {
        "id": r.id,
        "activity_id": r.activity_id,
        "activity_title": act.title if act else None,
        "activity_number": _compose_activity_number(plan, (act.activity_number if act else None)),
        "activity_description": act.description if act else None,
        "category_id": act.category_id if act else None,
        "category_name": act.category.name if act and getattr(act, "category", None) else None,
        "collaboration_nature": act.collaboration_nature if act else None,
        "periodicity": getattr(act, "periodicity", None) if act else None,
        "start_year": act.start_year if act else None,
        "edition": getattr(act, "edition", None) if act else None,
        "planned_budget": float(act.planned_budget) if act and act.planned_budget is not None else None,
        "action_impact_target": float(act.action_impact_target) if act and act.action_impact_target is not None else None,
        "action_impact_unit_target": getattr(act, "action_impact_unit", None) if act else None,
        "action_impact_duration": getattr(act, "action_impact_duration", None) if act else None,
        "organizer": getattr(act, "organizer", None) if act else None,
        "external_partner_name": act.external_partner.name if act and getattr(act, "external_partner", None) else None,
        "number_external_partners": (
            len([p for p in (act.external_partner.name or "").split(",") if p.strip()])
            if act and getattr(act, "external_partner", None) and act.external_partner.name
            else None
        ),
        "plan_id": act.plan_id if act else None,
        "site_name": plan.site.name if plan and plan.site else None,
        "site_region": plan.site.region if plan and plan.site else None,
        "site_country": plan.site.country if plan and plan.site else None,
        # Backward-friendly aliases used by some frontend exports.
        "region": plan.site.region if plan and plan.site else None,
        "country": plan.site.country if plan and plan.site else None,
        "plan_status": plan.status if plan else None,
        "plan_editable": plan_editable,
        "realized_budget": float(r.realized_budget) if r.realized_budget is not None else None,
        "participants": r.participants,
        "employees_actual": r.participants,
        "total_hc": (plan.total_hc if plan and getattr(plan, "total_hc", None) is not None else r.total_hc),
        "action_impact_actual": float(r.action_impact_actual) if r.action_impact_actual is not None else None,
        "actual_action_impact": float(r.action_impact_actual) if r.action_impact_actual is not None else None,
        "action_impact_unit": r.action_impact_unit or None,
        "corporate_image_improved": getattr(r, "corporate_image_improved", None),
        "incidents_number": getattr(r, "incidents_number", None),
        "planned_objectives": planned_objectives,
        "completed_objectives": completed_objectives,
        "is_off_plan": bool(getattr(r, "is_off_plan", False)),
        "off_plan_validation_mode": getattr(r, "off_plan_validation_mode", None),
        "off_plan_validation_step": getattr(r, "off_plan_validation_step", None),
        "realization_date": r.realization_date.isoformat() if r.realization_date else None,
        "comment": r.comment or None,
        "contact_name": r.contact_name or None,
        "contact_email": r.contact_email or None,
        "contact_department": getattr(r, "contact_department", None) or None,
        "status": getattr(r, "status", None),
        "created_by": r.created_by,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
        "unlock_until": r.unlock_until.isoformat() if getattr(r, "unlock_until", None) else None,
        "unlock_since": r.unlock_since.isoformat() if getattr(r, "unlock_since", None) else None,
    }


def _allowed_activity_ids(user_id: str, role: str) -> Optional[list]:
    """Return activity IDs the user can access, or None if unrestricted (global corporate)."""
    scope = data_scope_site_ids(user_id, role)
    if scope is None:
        return None
    if not scope:
        return []
    plan_ids = [p.id for p in CsrPlan.query.filter(CsrPlan.site_id.in_(scope)).with_entities(CsrPlan.id).all()]
    return [a.id for a in CsrActivity.query.filter(CsrActivity.plan_id.in_(plan_ids)).all()]


@bp.get("")
@token_required
def list_realized():
    """List realized CSR. Optional: activity_id. SITE_USER only sees their sites' activities."""
    activity_id = request.args.get("activity_id")

    q = RealizedCsr.query
    role = getattr(request, "role", "") or ""
    allowed = _allowed_activity_ids(request.user_id, role)
    if allowed is not None:
        if not allowed:
            return jsonify([]), 200
        q = q.filter(RealizedCsr.activity_id.in_(allowed))

    if activity_id:
        q = q.filter_by(activity_id=activity_id)

    # Keep dashboard/list behavior (validated plans only), but when querying
    # a specific activity (edit screen), return its realizations regardless of plan status.
    q = q.join(RealizedCsr.activity).join(CsrActivity.plan)
    if not activity_id:
        q = q.filter(CsrPlan.status == "VALIDATED")

    # RealizedCsr no longer has year/month columns; order by realization_date (newest first),
    # then by created_at as a fallback. MySQL/MariaDB do not support "NULLS LAST",
    # so emulate nulls-last via an IS NULL sort key.
    records = (
        q.order_by(
            RealizedCsr.realization_date.is_(None),
            RealizedCsr.realization_date.desc(),
            RealizedCsr.created_at.desc(),
        )
        .all()
    )
    return jsonify([_realized_to_json(r, role) for r in records]), 200


@bp.get("/<realized_id>")
@token_required
def get_realized(realized_id: str):
    """Get a single realized CSR record by id. SITE_USER only if activity belongs to their sites."""
    from sqlalchemy.orm import joinedload
    r = (
        RealizedCsr.query.options(
            joinedload(RealizedCsr.activity).joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
        )
        .filter_by(id=realized_id)
        .first()
    )
    if not r:
        return jsonify({"message": "Réalisation introuvable"}), 404
    allowed = _allowed_activity_ids(request.user_id, getattr(request, "role", ""))
    if allowed is not None and r.activity_id not in allowed:
        return jsonify({"message": "Vous n'avez pas accès à cette réalisation"}), 403
    return jsonify(_realized_to_json(r, getattr(request, "role", ""))), 200


@bp.post("")
@token_required
def create_realized():
    """Create a realized CSR record."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400

    activity_id = data.get("activity_id")
    if not activity_id:
        return jsonify({"message": "activity_id est obligatoire"}), 400

    activity = CsrActivity.query.options(db.joinedload(CsrActivity.plan)).get(activity_id)
    if not activity:
        return jsonify({"message": "Activité introuvable"}), 404

    plan_obj = activity.plan
    if not plan_obj:
        return jsonify({"message": "Plan introuvable pour cette activité"}), 404
    plan_year = plan_obj.year

    allowed = _allowed_activity_ids(request.user_id, getattr(request, "role", ""))
    if allowed is not None and activity_id not in allowed:
        return jsonify({"message": "Vous n'avez pas accès à cette activité"}), 403

    # Allow creating realizations even when plan is locked: submitting realized data records what was done,
    # it does not modify the planned activity. Activities with realizations are excluded from planned list.

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

    def _list_text_values(raw):
        if raw is None:
            return []
        if isinstance(raw, list):
            out = []
            for v in raw:
                s = str(v).strip()
                if s and s.lower() not in [x.lower() for x in out]:
                    out.append(s)
            return out
        s = str(raw).strip()
        return [s] if s else []

    realization_date = None
    rd = data.get("realization_date")
    if rd:
        try:
            from datetime import datetime
            realization_date = datetime.strptime(rd[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    if realization_date is not None and realization_date.year != plan_year:
        return jsonify(
            {"message": f"La date de réalisation doit être comprise dans l'année du plan ({plan_year})."},
        ), 400

    r = RealizedCsr(
        activity_id=activity_id,
        realized_budget=_num("realized_budget"),
        participants=_int_val("employees_actual") if _int_val("employees_actual") is not None else _int_val("participants"),
        corporate_image_improved=data.get("corporate_image_improved"),
        incidents_number=_int_val("incidents_number"),
        total_hc=getattr(plan_obj, "total_hc", None),
        action_impact_actual=_num("action_impact_actual"),
        action_impact_unit=_str_val("action_impact_unit"),
        is_off_plan=bool(data.get("is_off_plan")) if data.get("is_off_plan") is not None else bool(getattr(activity, "is_off_plan", False)),
        off_plan_validation_mode=_str_val("off_plan_validation_mode", getattr(activity, "off_plan_validation_mode", None)),
        off_plan_validation_step=_int_val("off_plan_validation_step", getattr(activity, "off_plan_validation_step", None)),
        realization_date=realization_date,
        comment=_str_val("comment"),
        contact_name=_str_val("contact_name"),
        contact_email=_str_val("contact_email"),
        contact_department=_str_val("contact_department"),
        created_by=request.user_id,
    )
    db.session.add(r)
    CsrCompletedObjective.query.filter_by(activity_id=activity_id).delete()
    for objective in _list_text_values(data.get("completed_objectives")):
        db.session.add(CsrCompletedObjective(activity_id=activity_id, objective=objective, achieved=True))
    db.session.commit()
    # Notify corporate only when the plan is not in DRAFT (e.g. VALIDATED plan)
    plan = r.activity.plan if r.activity else None
    if plan and getattr(plan, "status", None) != "DRAFT":
        site_name = plan.site.name if plan.site else "Site inconnu"
        activity_title = r.activity.title if r.activity else "Activité inconnue"
        when = r.realization_date.isoformat() if r.realization_date else "—"
        notify_corporate(
            title="Activité réalisée soumise",
            message=f"Le site {site_name} a soumis une réalisation pour l'activité '{activity_title}' (date: {when}).",
            type="success",
            site_id=plan.site_id,
            notification_category="activity_validation",
        )
    emit_tasks_refresh_for_request_actor()
    return jsonify(_realized_to_json(r, getattr(request, "role", ""))), 201


@bp.put("/<realized_id>")
@token_required
def update_realized(realized_id: str):
    """Update a realized CSR record. Plan must be editable (submit a change request if locked)."""
    r = RealizedCsr.query.options(
        db.joinedload(RealizedCsr.activity).joinedload(CsrActivity.plan),
    ).get(realized_id)
    if not r:
        return jsonify({"message": "Réalisation introuvable"}), 404
    allowed = _allowed_activity_ids(request.user_id, getattr(request, "role", ""))
    if allowed is not None and r.activity_id not in allowed:
        return jsonify({"message": "Vous n'avez pas accès à cette réalisation"}), 403
    if not _activity_is_editable(r.activity, getattr(request, "role", "")):
        return jsonify({
            "message": "Le plan est verrouillé. Soumettez une demande de modification pour modifier cette réalisation."
        }), 403

    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400

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

    realization_date = None
    rd = data.get("realization_date")
    if rd:
        try:
            from datetime import datetime
            realization_date = datetime.strptime(rd[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
    if realization_date is not None:
        r.realization_date = realization_date

    plan_year = r.activity.plan.year if r.activity and r.activity.plan else None
    if plan_year is not None:
        if r.realization_date is not None and r.realization_date.year != plan_year:
            return jsonify(
                {"message": f"La date de réalisation doit être comprise dans l'année du plan ({plan_year})."},
            ), 400

    r.realized_budget = _num("realized_budget", r.realized_budget)
    r.participants = _int_val("employees_actual", r.participants) if "employees_actual" in data else _int_val("participants", r.participants)
    # total_hc is managed at annual-plan level; keep realization row aligned.
    plan_total_hc = r.activity.plan.total_hc if r.activity and r.activity.plan else None
    r.total_hc = plan_total_hc
    r.action_impact_actual = _num("action_impact_actual", r.action_impact_actual)
    r.action_impact_unit = _str_val("action_impact_unit", r.action_impact_unit)
    if "corporate_image_improved" in data:
        r.corporate_image_improved = data.get("corporate_image_improved")
    if "incidents_number" in data:
        r.incidents_number = _int_val("incidents_number", r.incidents_number)
    if "is_off_plan" in data:
        r.is_off_plan = bool(data.get("is_off_plan"))
    if "off_plan_validation_mode" in data:
        r.off_plan_validation_mode = _str_val("off_plan_validation_mode", r.off_plan_validation_mode)
    if "off_plan_validation_step" in data:
        r.off_plan_validation_step = _int_val("off_plan_validation_step", r.off_plan_validation_step)
    r.comment = _str_val("comment", r.comment)
    r.contact_name = _str_val("contact_name", r.contact_name)
    r.contact_email = _str_val("contact_email", r.contact_email)
    r.contact_department = _str_val("contact_department", r.contact_department)
    if "completed_objectives" in data:
        CsrCompletedObjective.query.filter_by(activity_id=r.activity_id).delete()
        raw_list = data.get("completed_objectives")
        values = raw_list if isinstance(raw_list, list) else ([raw_list] if raw_list else [])
        dedup = []
        for value in values:
            s = str(value).strip()
            if s and s.lower() not in [x.lower() for x in dedup]:
                dedup.append(s)
        for objective in dedup:
            db.session.add(CsrCompletedObjective(activity_id=r.activity_id, objective=objective, achieved=True))

    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify(_realized_to_json(r, getattr(request, "role", ""))), 200


@bp.delete("/<realized_id>")
@token_required
def delete_realized(realized_id: str):
    """Delete a realized CSR record. Plan must be editable (submit a change request if locked)."""
    r = RealizedCsr.query.options(
        db.joinedload(RealizedCsr.activity).joinedload(CsrActivity.plan),
    ).get(realized_id)
    if not r:
        return jsonify({"message": "Réalisation introuvable"}), 404
    allowed = _allowed_activity_ids(request.user_id, getattr(request, "role", ""))
    if allowed is not None and r.activity_id not in allowed:
        return jsonify({"message": "Vous n'avez pas accès à cette réalisation"}), 403
    if not _activity_is_editable(r.activity, getattr(request, "role", "")):
        return jsonify({
            "message": "Le plan est verrouillé. Soumettez une demande de modification pour supprimer cette réalisation."
        }), 403
    activity = r.activity
    plan = activity.plan if activity else None
    site_id = plan.site_id if plan else None
    act_label = ""
    if activity:
        act_label = (activity.title or activity.activity_number or "").strip() or activity.id
    audit_delete(
        user_id=request.user_id,
        site_id=site_id,
        entity_type="REALIZATION",
        entity_id=activity.id if activity else realized_id,
        description=f"Suppression réalisation pour activité {act_label or '—'}",
        old_snapshot={},
    )
    db.session.delete(r)
    db.session.commit()
    emit_tasks_refresh_for_request_actor()
    return jsonify({"message": "Réalisation supprimée"}), 200

