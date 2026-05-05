"""
Dashboard endpoints: real data from DB (site summary, activities chart, KPIs, categories, timeline, site performance, top activities, notifications).
"""
from dataclasses import asdict, dataclass
from datetime import datetime, date
from typing import List, Optional

from flask import Blueprint, request, jsonify
from sqlalchemy import func, distinct
from sqlalchemy.orm import joinedload

from core import db, token_required, role_required
from models import (
    CsrPlan,
    CsrActivity,
    RealizedCsr,
    Category,
    Site,
    UserSite,
    ChangeRequest,
)
from features.change_request_management.change_requests_routes import (
    _change_request_awaiting_corporate_unlock,
    _in_plan_mod_awaits_corporate_validation,
    _off_plan_awaits_corporate_validation,
    activity_has_off_plan_realization_sql,
)


bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _allowed_site_ids():
    """Site IDs the current user can access. Empty = corporate sees all."""
    role = (getattr(request, "role", "") or "").upper()
    if role in ("CORPORATE_USER", "CORPORATE"):
        return None  # all sites
    user_sites = UserSite.query.filter_by(user_id=request.user_id, is_active=True).all()
    return [us.site_id for us in user_sites] if user_sites else []


def _site_user_can_validate() -> bool:
    """True when current site user has validator grade on at least one active site."""
    role = (getattr(request, "role", "") or "").upper()
    if role not in ("SITE_USER", "SITE"):
        return True
    rows = UserSite.query.filter_by(user_id=request.user_id, is_active=True).all()
    grades = [(r.grade or "").strip().lower() for r in rows]
    return any(g in ("level_1", "level_2", "level_3") for g in grades)


def _dashboard_filters():
    """Read optional query params: site_id, year, category_id.
    Returns (effective_site_ids or None, year or None, category_id or None).
    When effective_site_ids is None, use _allowed_site_ids() in queries."""
    allowed = _allowed_site_ids()
    site_ids = None
    site_id = request.args.get("site_id")
    if site_id:
        if allowed is None or site_id in allowed:
            site_ids = [site_id]
    year = request.args.get("year", type=int)
    category_id = request.args.get("category_id")
    return (site_ids, year, category_id)


def _apply_plan_filters(q, site_ids, year):
    if site_ids is not None:
        if len(site_ids) == 0:
            return q.filter(False)
        q = q.filter(CsrPlan.site_id.in_(site_ids))
    if year is not None:
        q = q.filter(CsrPlan.year == year)
    return q


def _apply_activity_filters(q, site_ids, year, category_id):
    q = _apply_plan_filters(q, site_ids, year)
    if category_id is not None:
        q = q.filter(CsrActivity.category_id == category_id)
    return q


def _apply_realized_filters(q, site_ids, year, category_id):
    if site_ids is not None and len(site_ids) == 0:
        return q.filter(False)
    if site_ids is not None:
        q = q.filter(CsrPlan.site_id.in_(site_ids))
    if year is not None:
        q = q.filter(RealizedCsr.year == year)
    if category_id is not None:
        q = q.filter(CsrActivity.category_id == category_id)
    return q


def _plan_query():
    q = CsrPlan.query
    site_ids = _allowed_site_ids()
    if site_ids is not None and len(site_ids) == 0:
        return q.filter(False)
    if site_ids:
        q = q.filter(CsrPlan.site_id.in_(site_ids))
    return q


def _activities_query():
    """CsrActivity joined with plan, filtered by allowed sites."""
    site_ids = _allowed_site_ids()
    if site_ids is not None and len(site_ids) == 0:
        return CsrActivity.query.filter(False)
    q = CsrActivity.query.join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    if site_ids:
        q = q.filter(CsrPlan.site_id.in_(site_ids))
    return q


def _realized_query():
    """RealizedCsr via CsrActivity -> CsrPlan, filtered by allowed sites."""
    site_ids = _allowed_site_ids()
    if site_ids is not None and len(site_ids) == 0:
        return RealizedCsr.query.filter(False)
    q = (
        RealizedCsr.query.join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    if site_ids:
        q = q.filter(CsrPlan.site_id.in_(site_ids))
    return q


# ---------- Filter options (for dashboard dropdowns) ----------
@bp.get("/filter-options")
@token_required
@role_required("site", "corporate")
def dashboard_filter_options():
    """Returns years, sites, and categories for dashboard filter dropdowns. Years = all distinct from plans and realized, plus current year."""
    now = datetime.utcnow()
    site_ids = _allowed_site_ids()
    years_from_plans = (
        db.session.query(distinct(CsrPlan.year)).filter(CsrPlan.year.isnot(None))
    )
    if site_ids is not None and len(site_ids) == 0:
        years_from_plans = years_from_plans.filter(False)
    elif site_ids:
        years_from_plans = years_from_plans.filter(CsrPlan.site_id.in_(site_ids))
    years_from_realized = (
        db.session.query(distinct(RealizedCsr.year)).filter(RealizedCsr.year.isnot(None))
    )
    if site_ids is not None and len(site_ids) == 0:
        years_from_realized = years_from_realized.filter(False)
    elif site_ids:
        years_from_realized = (
            years_from_realized.join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(CsrPlan.site_id.in_(site_ids))
        )
    year_set = {row[0] for row in years_from_plans.all()}
    year_set.update(row[0] for row in years_from_realized.all())
    year_set.add(now.year)
    years = sorted(year_set, reverse=True)
    sites_q = Site.query.filter(Site.is_active == True)
    if site_ids is not None and len(site_ids) == 0:
        sites_q = sites_q.filter(False)
    elif site_ids:
        sites_q = sites_q.filter(Site.id.in_(site_ids))
    sites = [{"id": s.id, "name": s.name or s.code or s.id} for s in sites_q.all()]
    categories = [{"id": str(c.id), "name": c.name} for c in Category.query.order_by(Category.name).all()]
    return jsonify({"years": years, "sites": sites, "categories": categories})


# ---------- Summary ----------
@dataclass
class DashboardSummary:
    siteId: Optional[str]
    plansCount: int
    validatedPlansCount: int
    activitiesThisMonth: int
    totalCost: float


@bp.get("/site/summary")
@token_required
@role_required("site", "corporate")
def site_summary():
    """Returns site dashboard metrics from DB."""
    site_ids, year, _ = _dashboard_filters()
    plan_q = _apply_plan_filters(_plan_query(), site_ids, year)
    plans_count = plan_q.count()
    validated_plans_count = plan_q.filter(CsrPlan.status.in_(["VALIDATED", "LOCKED"])).count()

    now = datetime.utcnow()
    realized_q = _realized_query()
    realized_q = _apply_realized_filters(realized_q, site_ids, year, None)
    realized_q = realized_q.filter(
        RealizedCsr.year == now.year,
        RealizedCsr.month == now.month,
    )
    activities_this_month = realized_q.count()

    total_cost = (
        db.session.query(func.coalesce(func.sum(RealizedCsr.realized_budget), 0))
        .select_from(RealizedCsr)
        .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    eff_site_ids = site_ids if site_ids is not None else _allowed_site_ids()
    if eff_site_ids:
        total_cost = total_cost.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        total_cost = total_cost.filter(RealizedCsr.year == year)
    total_cost = float(total_cost.scalar() or 0)

    summary = DashboardSummary(
        siteId=None,
        plansCount=plans_count,
        validatedPlansCount=validated_plans_count,
        activitiesThisMonth=activities_this_month,
        totalCost=round(total_cost, 2),
    )
    return jsonify(asdict(summary))


# ---------- Activities chart (last 6 months) ----------
@dataclass
class ActivitiesChart:
    labels: List[str]
    data: List[int]


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


@bp.get("/site/activities-chart")
@token_required
@role_required("site", "corporate")
def site_activities_chart():
    """Returns realized activities count per month for last 6 months."""
    site_ids, year, category_id = _dashboard_filters()
    now = datetime.utcnow()
    labels = []
    data = []
    for i in range(5, -1, -1):
        if now.month - i <= 0:
            y = now.year - 1
            m = now.month - i + 12
        else:
            y = now.year
            m = now.month - i
        labels.append(MONTH_NAMES[m - 1])
        q = _realized_query()
        q = _apply_realized_filters(q, site_ids, year, category_id)
        count = q.filter(RealizedCsr.year == y, RealizedCsr.month == m).count()
        data.append(count)
    chart = ActivitiesChart(labels=labels, data=data)
    return jsonify(asdict(chart))


# ---------- KPIs ----------
@bp.get("/kpis")
@token_required
@role_required("site", "corporate")
def dashboard_kpis():
    """Full KPIs from DB: total planned, completed, in progress, completion rate, budgets, participants, volunteer hours."""
    site_ids, year, category_id = _dashboard_filters()
    eff_site_ids = site_ids if site_ids is not None else _allowed_site_ids()
    plan_q = _apply_plan_filters(_plan_query(), site_ids, year)
    plans_count = plan_q.count()
    validated_count = plan_q.filter(CsrPlan.status.in_(["VALIDATED", "LOCKED"])).count()

    activities_q = _apply_activity_filters(_activities_query(), site_ids, year, category_id)
    total_planned = activities_q.count()
    activity_ids_with_realized = (
        db.session.query(RealizedCsr.activity_id).distinct().subquery()
    )
    completed_activities = (
        _apply_activity_filters(_activities_query(), site_ids, year, category_id)
        .filter(CsrActivity.id.in_(db.session.query(activity_ids_with_realized)))
        .count()
    )
    in_progress = max(0, total_planned - completed_activities)
    completion_rate = round((completed_activities / total_planned * 100), 1) if total_planned else 0

    budget_planned = (
        db.session.query(func.coalesce(func.sum(CsrActivity.planned_budget), 0))
        .select_from(CsrActivity)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    if eff_site_ids:
        budget_planned = budget_planned.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        budget_planned = budget_planned.filter(CsrPlan.year == year)
    if category_id is not None:
        budget_planned = budget_planned.filter(CsrActivity.category_id == category_id)
    budget_planned = float(budget_planned.scalar() or 0)

    budget_spent = (
        db.session.query(func.coalesce(func.sum(RealizedCsr.realized_budget), 0))
        .select_from(RealizedCsr)
        .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    if eff_site_ids:
        budget_spent = budget_spent.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        budget_spent = budget_spent.filter(RealizedCsr.year == year)
    if category_id is not None:
        budget_spent = budget_spent.filter(CsrActivity.category_id == category_id)
    budget_spent = float(budget_spent.scalar() or 0)

    participants_result = (
        db.session.query(func.coalesce(func.sum(RealizedCsr.participants), 0))
        .select_from(RealizedCsr)
        .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    if eff_site_ids:
        participants_result = participants_result.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        participants_result = participants_result.filter(RealizedCsr.year == year)
    if category_id is not None:
        participants_result = participants_result.filter(CsrActivity.category_id == category_id)
    total_participants = int(participants_result.scalar() or 0)

    volunteer_result = (
        db.session.query(func.coalesce(func.sum(RealizedCsr.volunteer_hours), 0))
        .select_from(RealizedCsr)
        .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
    )
    if eff_site_ids:
        volunteer_result = volunteer_result.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        volunteer_result = volunteer_result.filter(RealizedCsr.year == year)
    if category_id is not None:
        volunteer_result = volunteer_result.filter(CsrActivity.category_id == category_id)
    volunteer_hours = float(volunteer_result.scalar() or 0)

    return jsonify({
        "totalPlanned": total_planned,
        "completed": completed_activities,
        "inProgress": in_progress,
        "completionRate": completion_rate,
        "budgetPlanned": round(budget_planned, 2),
        "budgetSpent": round(budget_spent, 2),
        "totalParticipants": total_participants,
        "volunteerHours": round(volunteer_hours, 2),
    })


# ---------- Categories (activities by category) ----------
_CATEGORY_COLORS = ["#0d9488", "#2563eb", "#7c3aed", "#059669", "#1d4ed8", "#a855f7", "#0f766e", "#4338ca"]
# teal, blue, violet, emerald, indigo, purple, teal-800, indigo-800 (no grey)


@bp.get("/categories")
@token_required
@role_required("site", "corporate")
def dashboard_categories():
    """Count of realized activities by category (Environment, Social, Governance)."""
    site_ids, year, category_id = _dashboard_filters()
    eff_site_ids = site_ids if site_ids is not None else _allowed_site_ids()
    q = (
        db.session.query(Category.id, Category.name, func.count(RealizedCsr.id))
        .join(CsrActivity, CsrActivity.category_id == Category.id)
        .join(RealizedCsr, RealizedCsr.activity_id == CsrActivity.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
        .group_by(Category.id, Category.name)
    )
    if eff_site_ids:
        q = q.filter(CsrPlan.site_id.in_(eff_site_ids))
    if year is not None:
        q = q.filter(RealizedCsr.year == year)
    if category_id is not None:
        q = q.filter(Category.id == category_id)
    rows = q.all()
    return jsonify([
        {"label": name, "value": count, "color": _CATEGORY_COLORS[i % len(_CATEGORY_COLORS)]}
        for i, (_, name, count) in enumerate(rows)
    ])


# ---------- Monthly timeline (12 months) ----------
@bp.get("/monthly-timeline")
@token_required
@role_required("site", "corporate")
def monthly_timeline():
    """Realized activities count per month for last 12 months."""
    site_ids, year, category_id = _dashboard_filters()
    now = datetime.utcnow()
    labels = []
    data = []
    for i in range(11, -1, -1):
        if now.month - i <= 0:
            y = now.year - 1
            m = now.month - i + 12
        else:
            y = now.year
            m = now.month - i
        labels.append(MONTH_NAMES[m - 1])
        q = _realized_query()
        q = _apply_realized_filters(q, site_ids, year, category_id)
        count = q.filter(RealizedCsr.year == y, RealizedCsr.month == m).count()
        data.append(count)
    return jsonify({"labels": labels, "data": data})


# ---------- Site performance ----------
@bp.get("/site-performance")
@token_required
@role_required("site", "corporate")
def site_performance():
    """Per-site: planned activities count, completed count, budget planned, budget spent."""
    filter_site_ids, year, category_id = _dashboard_filters()
    eff_site_ids = filter_site_ids if filter_site_ids is not None else _allowed_site_ids()
    if eff_site_ids is not None and len(eff_site_ids) == 0:
        return jsonify([])

    sites = Site.query.filter(Site.is_active == True)
    if eff_site_ids:
        sites = sites.filter(Site.id.in_(eff_site_ids))
    sites = sites.all()

    result = []
    for site in sites:
        planned_q = (
            CsrActivity.query.join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(CsrPlan.site_id == site.id)
        )
        if year is not None:
            planned_q = planned_q.filter(CsrPlan.year == year)
        if category_id is not None:
            planned_q = planned_q.filter(CsrActivity.category_id == category_id)
        planned = planned_q.count()
        activity_ids_q = (
            db.session.query(CsrActivity.id)
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(CsrPlan.site_id == site.id)
        )
        if year is not None:
            activity_ids_q = activity_ids_q.filter(CsrPlan.year == year)
        if category_id is not None:
            activity_ids_q = activity_ids_q.filter(CsrActivity.category_id == category_id)
        completed_q = (
            db.session.query(func.count(distinct(RealizedCsr.activity_id)))
            .filter(RealizedCsr.activity_id.in_(activity_ids_q))
        )
        if year is not None:
            completed_q = completed_q.filter(RealizedCsr.year == year)
        completed = completed_q.scalar() or 0
        budget_planned_q = (
            db.session.query(func.coalesce(func.sum(CsrActivity.planned_budget), 0))
            .select_from(CsrActivity)
            .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
            .filter(CsrPlan.site_id == site.id)
        )
        if year is not None:
            budget_planned_q = budget_planned_q.filter(CsrPlan.year == year)
        if category_id is not None:
            budget_planned_q = budget_planned_q.filter(CsrActivity.category_id == category_id)
        budget_planned = budget_planned_q.scalar()
        budget_spent_q = (
            db.session.query(func.coalesce(func.sum(RealizedCsr.realized_budget), 0))
            .select_from(RealizedCsr)
            .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
            .filter(CsrActivity.plan_id.in_(
                db.session.query(CsrPlan.id).filter(CsrPlan.site_id == site.id)
            ))
        )
        if year is not None:
            budget_spent_q = budget_spent_q.filter(RealizedCsr.year == year)
        if category_id is not None:
            budget_spent_q = budget_spent_q.filter(CsrActivity.category_id == category_id)
        budget_spent = budget_spent_q.scalar()
        result.append({
            "siteName": site.name or site.code or site.id,
            "planned": planned,
            "completed": completed,
            "budgetPlanned": float(budget_planned or 0),
            "budgetSpent": float(budget_spent or 0),
        })
    return jsonify(result)


# ---------- Top activities (realized, by participants desc) ----------
@bp.get("/top-activities")
@token_required
@role_required("site", "corporate")
def top_activities():
    """Top realized activities (by participants), with category and status."""
    site_ids, year, category_id = _dashboard_filters()
    eff_site_ids = site_ids if site_ids is not None else _allowed_site_ids()
    q = (
        db.session.query(
            CsrActivity.title,
            Category.name,
            func.coalesce(func.sum(RealizedCsr.participants), 0).label("participants"),
            func.max(RealizedCsr.action_impact_actual).label("impact_actual"),
            CsrActivity.status,
        )
        .join(CsrActivity, RealizedCsr.activity_id == CsrActivity.id)
        .join(Category, CsrActivity.category_id == Category.id)
        .join(CsrPlan, CsrActivity.plan_id == CsrPlan.id)
        .group_by(CsrActivity.id, CsrActivity.title, Category.name, CsrActivity.status)
    )
    if eff_site_ids:
        q = q.filter(CsrPlan.site_id.in_(eff_site_ids))
    if eff_site_ids is not None and len(eff_site_ids) == 0:
        return jsonify([])
    if year is not None:
        q = q.filter(RealizedCsr.year == year)
    if category_id is not None:
        q = q.filter(CsrActivity.category_id == category_id)
    rows = q.order_by(func.coalesce(func.sum(RealizedCsr.participants), 0).desc()).limit(10).all()

    def status_map(s):
        if s == "COMPLETED" or s == "VALIDATED":
            return "completed"
        if s == "IN_PROGRESS" or s == "DRAFT":
            return "in_progress"
        return "planned"

    def impact_str(val):
        if val is None:
            return "—"
        try:
            v = float(val)
            return "High" if v >= 50 else "Medium" if v >= 10 else "Low"
        except (TypeError, ValueError):
            return "—"

    return jsonify([
        {
            "name": title or "—",
            "category": cat_name or "—",
            "participants": int(participants or 0),
            "impact": impact_str(impact_actual),
            "status": status_map(status),
        }
        for title, cat_name, participants, impact_actual, status in rows
    ])


# ---------- Notifications ----------
@bp.get("/notifications")
@token_required
@role_required("site", "corporate")
def dashboard_notifications():
    """Alerts: activities overdue, plans waiting validation, change requests pending."""
    notifications = []
    today = date.today()

    site_ids, year, category_id = _dashboard_filters()
    # Activities overdue (planned activities with end_date < today and status not completed)
    overdue_q = _apply_activity_filters(
        _activities_query(), site_ids, year, category_id
    ).filter(
        CsrActivity.end_date.isnot(None),
        CsrActivity.end_date < today,
        ~CsrActivity.status.in_(["COMPLETED", "VALIDATED", "CANCELLED"]),
    )
    overdue_count = overdue_q.count()
    if overdue_count > 0:
        notifications.append({
            "id": "overdue",
            "type": "overdue",
            "title": "Activities overdue",
            "message": f"{overdue_count} activities past due date",
            "count": overdue_count,
            "link": "/planned-activities",
        })

    # Plans waiting validation (SUBMITTED)
    role = (getattr(request, "role", "") or "").upper()
    can_validate = _site_user_can_validate()
    validation_q = _apply_plan_filters(_plan_query(), site_ids, year).filter(CsrPlan.status == "SUBMITTED")
    validation_count = validation_q.count()
    if validation_count > 0 and (role in ("CORPORATE_USER", "CORPORATE") or can_validate):
        notifications.append({
            "id": "validation",
            "type": "validation",
            "title": "Plans waiting validation",
            "message": f"{validation_count} plans require validation",
            "count": validation_count,
            "link": "/annual-plans/validation",
        })

    # Change requests pending (corporate sees all PENDING; site user sees own?)
    cr_q = ChangeRequest.query.filter(ChangeRequest.status == "PENDING")
    if role in ("SITE_USER", "SITE"):
        site_ids = _allowed_site_ids() or []
        if site_ids:
            cr_q = cr_q.filter(ChangeRequest.site_id.in_(site_ids))
        else:
            cr_q = cr_q.filter(False)
    if role in ("CORPORATE_USER", "CORPORATE"):
        pending_count = sum(1 for cr in cr_q.all() if _change_request_awaiting_corporate_unlock(cr))
    else:
        pending_count = cr_q.count()
    if role in ("CORPORATE_USER", "CORPORATE"):
        off_acts = CsrActivity.query.filter(
            activity_has_off_plan_realization_sql,
            CsrActivity.status == "SUBMITTED",
        ).all()
        pending_count += sum(1 for a in off_acts if _off_plan_awaits_corporate_validation(a))
        in_mod_acts = (
            CsrActivity.query.options(joinedload(CsrActivity.plan))
            .filter(~activity_has_off_plan_realization_sql, CsrActivity.status == "SUBMITTED")
            .all()
        )
        pending_count += sum(1 for a in in_mod_acts if _in_plan_mod_awaits_corporate_validation(a))
    if pending_count > 0 and (role in ("CORPORATE_USER", "CORPORATE") or can_validate):
        notifications.append({
            "id": "change_request",
            "type": "change_request",
            "title": "Change requests pending",
            "message": f"{pending_count} item(s) awaiting corporate review (change requests and/or off-plan activities)",
            "count": pending_count,
            "link": "/changes/pending",
        })

    return jsonify(notifications)
