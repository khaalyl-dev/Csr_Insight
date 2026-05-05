"""
Categories API routes - list and create CSR activity categories.

Categories (Environment, Social, Education, etc.) are used to classify activities.
Used in dropdowns when creating activities. Create is idempotent (returns existing if name exists).
Delete: shows related activities, optionally deletes them (only if plan editable).
"""
from datetime import datetime
import re

from flask import Blueprint, jsonify, request

from core import db, token_required, role_required
from models import Category, CsrActivity, CsrPlan
from features.audit_history_management.audit_helper import audit_delete, snapshot_activity

bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def _plan_is_editable(plan: CsrPlan) -> bool:
    """True if plan can be edited: DRAFT/REJECTED always, or VALIDATED with unlock_until in the future."""
    unlock_until = getattr(plan, "unlock_until", None)
    now = datetime.utcnow()
    if plan.status in ("DRAFT", "REJECTED"):
        return True
    if plan.status == "VALIDATED" and unlock_until and now <= unlock_until:
        return True
    return False


def _get_or_create_uncategorized() -> Category:
    cat = Category.query.filter(db.func.lower(Category.name) == "uncategorized").first()
    if cat:
        return cat
    cat = Category(name="Uncategorized")
    db.session.add(cat)
    db.session.flush()
    return cat


def _compose_activity_number(activity: CsrActivity) -> str:
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


@bp.get("")
@token_required
def list_categories():
    """List all CSR categories (for activity dropdown)."""
    categories = Category.query.order_by(Category.name).all()
    return jsonify([{"id": c.id, "name": c.name} for c in categories]), 200


@bp.post("")
@token_required
def create_category():
    """Create a new category. Body: { name: string }."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"message": "Le nom de la catégorie est obligatoire"}), 400
    existing = Category.query.filter_by(name=name).first()
    if existing:
        return jsonify({"id": existing.id, "name": existing.name}), 201
    cat = Category(name=name)
    db.session.add(cat)
    db.session.commit()
    return jsonify({"id": cat.id, "name": cat.name}), 201


@bp.get("/<category_id>/related-activities")
@token_required
@role_required("CORPORATE_USER", "corporate")
def get_related_activities(category_id: str):
    """List activities using this category. Corporate only."""
    cat = Category.query.get(category_id)
    if not cat:
        return jsonify({"message": "Catégorie introuvable"}), 404
    activities = (
        CsrActivity.query.options(
            db.joinedload(CsrActivity.plan).joinedload(CsrPlan.site),
        )
        .filter_by(category_id=category_id)
        .all()
    )
    out = []
    for a in activities:
        plan = a.plan
        editable = plan and _plan_is_editable(plan)
        out.append({
            "id": a.id,
            "activity_number": _compose_activity_number(a),
            "title": a.title or "",
            "plan_id": a.plan_id,
            "plan_status": plan.status if plan else None,
            "plan_editable": editable,
            "site_name": plan.site.name if plan and plan.site else None,
            "year": plan.year if plan else None,
        })
    return jsonify({"activities": out}), 200


@bp.delete("/<category_id>")
@token_required
@role_required("CORPORATE_USER", "corporate")
def delete_category(category_id: str):
    """
    Delete a category. Corporate only.
    Body: { "delete_related_activities": true|false }
    - If false: reassign all activities to Uncategorized.
    - If true: delete activities whose plan is editable; reassign the rest to Uncategorized.
    """
    cat = Category.query.get(category_id)
    if not cat:
        return jsonify({"message": "Catégorie introuvable"}), 404
    uncategorized = _get_or_create_uncategorized()
    if uncategorized.id == category_id:
        return jsonify({"message": "La catégorie 'Uncategorized' ne peut pas être supprimée"}), 400

    data = request.get_json(silent=True) or {}
    delete_related = data.get("delete_related_activities") is True

    activities = CsrActivity.query.options(
        db.joinedload(CsrActivity.plan),
    ).filter_by(category_id=category_id).all()

    deleted_count = 0
    reassigned_count = 0

    for a in activities:
        plan = a.plan
        editable = plan and _plan_is_editable(plan)
        if delete_related and editable:
            old_snapshot = snapshot_activity(a)
            audit_delete(
                user_id=request.user_id,
                site_id=plan.site_id if plan else None,
                entity_type="ACTIVITY",
                entity_id=a.id,
                description=f"Suppression activité {a.title or a.activity_number}",
                old_snapshot=old_snapshot,
            )
            db.session.delete(a)
            deleted_count += 1
        else:
            a.category_id = uncategorized.id
            reassigned_count += 1

    db.session.flush()  # apply reassignments and activity deletes before deleting the category
    db.session.delete(cat)
    db.session.commit()

    return jsonify({
        "message": "Catégorie supprimée",
        "deleted_activities": deleted_count,
        "reassigned_activities": reassigned_count,
    }), 200
