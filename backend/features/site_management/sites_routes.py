"""
Sites API routes - list, create, update sites; assign users to sites.

All routes require a valid token. Only corporate users can create/update sites
and toggle status. Site users see only sites they have access to.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from core import db, token_required
from models import Site, User, UserSite

bp = Blueprint("sites", __name__, url_prefix="/api/sites")

def _site_to_json(site: Site):
    """Convert a Site model to a JSON dict for API responses."""
    return {
        "id": site.id,
        "name": site.name,
        "code": site.code,
        "region": site.region or "",
        "country": site.country or "",
        "location": site.location or "",
        "description": site.description or "",
        "is_active": site.is_active,
        "created_at": site.created_at.isoformat() if site.created_at else None,
        "updated_at": site.updated_at.isoformat() if site.updated_at else None,
    }

@bp.get("")
@token_required
def list_sites():
    """List all sites (optionally only active ones). Use ?active=true to filter."""
    active_only = request.args.get("active") == "true"
    q = Site.query
    if active_only:
        q = q.filter_by(is_active=True)
    sites = q.order_by(Site.name).all()
    return jsonify([_site_to_json(s) for s in sites])

@bp.post("")
@token_required
def create_site():
    """Create a new site. Requires name and code. Corporate only for full access."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "Données manquantes"}), 400
    if not data.get("name") or not data.get("code"):
        return jsonify({"message": "Nom et code sont obligatoires"}), 400
    if Site.query.filter_by(code=data["code"]).first():
        return jsonify({"message": "Code site déjà existant"}), 400

    site = Site(
        name=data["name"],
        code=data["code"],
        region=data.get("region"),
        country=data.get("country"),
        location=data.get("location"),
        description=data.get("description"),
        is_active=True
    )
    db.session.add(site)
    db.session.commit()
    return jsonify(_site_to_json(site)), 201


@bp.get("/<string:site_id>")
@token_required
def get_site(site_id):
    """Récupérer les détails d'un site par son ID."""
    site = Site.query.get(site_id)
    if not site:
        return jsonify({"message": "Site introuvable"}), 404
    return jsonify(_site_to_json(site)), 200

@bp.patch("/<string:site_id>/status")
@token_required
def toggle_site_status(site_id):
    """Enable or disable a site (toggle is_active). Corporate only."""
    if request.role.upper() != "CORPORATE_USER":
        return jsonify({"message": "Accès interdit"}), 403
    site = Site.query.get(site_id)
    if not site:
        return jsonify({"message": "Site introuvable"}), 404
    site.is_active = not site.is_active
    db.session.commit()
    return jsonify({"message": "Statut du site mis à jour", "is_active": site.is_active})

@bp.put("/<string:site_id>")
@token_required
def update_site(site_id):
    site = Site.query.get(site_id)
    if not site:
        return jsonify({"message": "Site introuvable"}), 404
    data = request.get_json()
    site.name = data.get("name", site.name)
    site.code = data.get("code", site.code)
    site.region = data.get("region", site.region)
    site.country = data.get("country", site.country)
    site.location = data.get("location", site.location)
    site.description = data.get("description", site.description)
    db.session.commit()
    return jsonify({"message": "Site mis à jour avec succès", "site": _site_to_json(site)}), 200






# ─── helpers ────────────────────────────────────────────────────────────────

def _user_site_to_json(us: UserSite):
    return {
        "id": us.id,
        "user_id": us.user_id,
        "site_id": us.site_id,
        "grade": us.grade or "",
        "is_active": us.is_active,
        "granted_by": us.granted_by or "",
        "granted_at": us.granted_at.isoformat() if us.granted_at else None,
        # infos user pour affichage frontend
        "user_first_name": us.user.first_name if us.user else "",
        "user_last_name": us.user.last_name if us.user else "",
        "user_email": us.user.email if us.user else "",
        "user_role": us.user.role if us.user else "",
    }

# ─── GET /api/sites/<site_id>/users ─────────────────────────────────────────

@bp.get("/<string:site_id>/users")
@token_required
def list_site_users(site_id):
    """Lister tous les users affectés à un site."""
    site = Site.query.get(site_id)
    if not site:
        return jsonify({"message": "Site introuvable"}), 404

    user_sites = (
        UserSite.query
        .filter_by(site_id=site_id, is_active=True)
        .all()
    )
    return jsonify([_user_site_to_json(us) for us in user_sites]), 200



# ─── POST /api/sites/<site_id>/users ────────────────────────────────────────

@bp.post("/<string:site_id>/users")
@token_required
def assign_user_to_site(site_id):
    """Affecter un user à un site."""
    if request.role.upper() != "CORPORATE_USER":
        return jsonify({"message": "Accès interdit"}), 403

    site = Site.query.get(site_id)
    if not site:
        return jsonify({"message": "Site introuvable"}), 404

    data = request.get_json()
    if not data or not data.get("user_id"):
        return jsonify({"message": "user_id est obligatoire"}), 400

    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    # Vérifier si l'affectation existe déjà
    existing = UserSite.query.filter_by(
        user_id=data["user_id"], site_id=site_id
    ).first()

    if existing:
        if existing.is_active:
            return jsonify({"message": "Utilisateur déjà affecté à ce site"}), 400
        else:
            # Réactiver si révoqué précédemment
            existing.is_active = True
            existing.grade = data.get("grade")
            existing.granted_by = request.user_id
            existing.granted_at = datetime.utcnow()
            db.session.commit()
            return jsonify(_user_site_to_json(existing)), 200

    grade = data.get("grade")
    if grade and grade not in ("level_0", "level_1", "level_2", "level_3"):
        return jsonify({"message": "grade invalide (level_0, level_1, level_2, level_3)"}), 400

    user_site = UserSite(
        user_id=data["user_id"],
        site_id=site_id,
        grade=grade,
        granted_by=request.user_id,
        granted_at=datetime.utcnow(),
    )
    db.session.add(user_site)
    db.session.commit()
    return jsonify(_user_site_to_json(user_site)), 201

# ─── PUT /api/sites/<site_id>/users/<user_id> ───────────────────────────────

@bp.put("/<string:site_id>/users/<string:user_id>")
@token_required
def update_user_site(site_id, user_id):
    """Modifier le grade d'un user sur un site."""
    if request.role.upper() != "CORPORATE_USER":
        return jsonify({"message": "Accès interdit"}), 403

    user_site = UserSite.query.filter_by(
        site_id=site_id, user_id=user_id, is_active=True
    ).first()
    if not user_site:
        return jsonify({"message": "Affectation introuvable"}), 404

    data = request.get_json()

    if "grade" in data:
        if data["grade"] and data["grade"] not in ("level_0", "level_1", "level_2", "level_3"):
            return jsonify({"message": "grade invalide"}), 400
        user_site.grade = data["grade"]

    db.session.commit()
    return jsonify(_user_site_to_json(user_site)), 200

# ─── DELETE /api/sites/<site_id>/users/<user_id> ────────────────────────────

@bp.delete("/<string:site_id>/users/<string:user_id>")
@token_required
def revoke_user_from_site(site_id, user_id):
    """Révoquer l'accès d'un user à un site (soft delete)."""
    if request.role.upper() != "CORPORATE_USER":
        return jsonify({"message": "Accès interdit"}), 403

    user_site = UserSite.query.filter_by(
        site_id=site_id, user_id=user_id, is_active=True
    ).first()
    if not user_site:
        return jsonify({"message": "Affectation introuvable"}), 404

    user_site.is_active = False
    db.session.commit()
    return jsonify({"message": "Accès révoqué avec succès"}), 200