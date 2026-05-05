"""
User management endpoints: CRUD users, assign site access (corporate only).

Endpoints (all require CORPORATE_USER role):
  GET    /api/users              - List all users
  GET    /api/users/<id>         - Get user with site assignments
  POST   /api/users              - Create SITE_USER
  PATCH  /api/users/<id>         - Update user
  POST   /api/users/<id>/sites   - Replace site access (assign_sites)
  DELETE /api/users/<id>/sites/<site_id> - Revoke site access
  POST   /api/users/<id>/reset-password  - Generate new password
"""
import secrets
import string
from datetime import datetime

from flask import Blueprint, request, jsonify

from core import db, token_required, role_required
from core.permissions import effective_corporate_permissions, normalize_permissions
from core.user_avatar import user_avatar_serve_url
from models import User, UserSite, Site

bp = Blueprint("users", __name__, url_prefix="/api/users")


def _user_to_json(user: User, with_sites: bool = False):
    """
    Convert User model to JSON dict.
    If with_sites=True, includes active site assignments (id, site_id, site_name, grade, granted_at).
    level: level_1 if any site has grade level_1, else level_0 if any has level_0, else None (for list display).
    """
    data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "avatar_url": user_avatar_serve_url(user),
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    data["permissions"] = (
        effective_corporate_permissions(user)
        if user.role == "CORPORATE_USER" or user.get_permissions()
        else None
    )
    sites = UserSite.query.filter_by(user_id=user.id, is_active=True).all()
    if sites:
        grades = [(us.grade or "").strip().lower() for us in sites]
        if "level_3" in grades:
            data["level"] = "level_3"
        elif "level_2" in grades:
            data["level"] = "level_2"
        elif "level_1" in grades:
            data["level"] = "level_1"
        elif any(g in ("", "level_0") for g in grades):
            data["level"] = "level_0"
        else:
            data["level"] = None
    else:
        data["level"] = None
    if with_sites:
        data["sites"] = [
            {
                "id": us.id,
                "site_id": us.site_id,
                "site_name": Site.query.get(us.site_id).name if Site.query.get(us.site_id) else None,
                "grade": us.grade or None,
                "access_types": us.get_access_types() if hasattr(us, "get_access_types") else [],
                "granted_at": us.granted_at.isoformat() if us.granted_at else None,
            }
            for us in sites
        ]
    return data


@bp.get("")
@token_required
@role_required("CORPORATE_USER", "corporate")
def list_users():
    """List all users, ordered by email. Returns id, first_name, last_name, email, role, is_active, created_at."""
    users = User.query.order_by(User.email).all()
    return jsonify([_user_to_json(u) for u in users])


@bp.get("/<user_id>")
@token_required
@role_required("CORPORATE_USER", "corporate")
def get_user(user_id: str):
    """Get user by ID with site assignments (id, site_id, site_name, granted_at)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404
    return jsonify(_user_to_json(user, with_sites=True))


@bp.post("")
@token_required
@role_required("CORPORATE_USER", "corporate")
def create_user():
    """
    Create a new user (SITE_USER or CORPORATE_USER).
    Requires: email, password, first_name, last_name.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    role = (data.get("role") or "SITE_USER").strip().upper()
    if role not in ("SITE_USER", "CORPORATE_USER"):
        return jsonify({"message": "role invalide (SITE_USER ou CORPORATE_USER)"}), 400
    normalized_permissions = normalize_permissions(data.get("permissions"))
    if data.get("permissions") is not None and normalized_permissions is None:
        return jsonify({"message": "permissions invalide"}), 400

    if not email or not password:
        return jsonify({"message": "Email et mot de passe obligatoires"}), 400
    if not first_name or not last_name:
        return jsonify({"message": "Prénom et nom obligatoires"}), 400
    if len(password) < 6:
        return jsonify({"message": "Le mot de passe doit contenir au moins 6 caractères"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Un utilisateur avec cet email existe déjà"}), 409

    user = User(
        email=email,
        password_hash=User.hash_password(password),
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
    )
    if role == "CORPORATE_USER":
        if "is_corporate_global" in data:
            user.is_corporate_global = bool(data.get("is_corporate_global"))
        else:
            user.is_corporate_global = True
    user.set_permissions(normalized_permissions)
    db.session.add(user)
    db.session.commit()
    return jsonify(_user_to_json(user)), 201


@bp.patch("/<user_id>")
@token_required
@role_required("CORPORATE_USER", "corporate")
def update_user(user_id: str):
    """Update user. Supports: first_name, last_name, is_active, role, password."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    if "first_name" in data:
        user.first_name = (data["first_name"] or "").strip() or user.first_name
    if "last_name" in data:
        user.last_name = (data["last_name"] or "").strip() or user.last_name
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "role" in data:
        r = (data["role"] or "").strip().upper()
        if r in ("SITE_USER", "CORPORATE_USER"):
            user.role = r
    if "password" in data and data["password"]:
        if len(data["password"]) >= 6:
            user.password_hash = User.hash_password(data["password"])
        else:
            return jsonify({"message": "Le mot de passe doit contenir au moins 6 caractères"}), 400
    if "permissions" in data:
        normalized_permissions = normalize_permissions(data.get("permissions"))
        if data.get("permissions") is not None and normalized_permissions is None:
            return jsonify({"message": "permissions invalide"}), 400
        user.set_permissions(normalized_permissions)
    if "is_corporate_global" in data and user.role == "CORPORATE_USER":
        user.is_corporate_global = bool(data.get("is_corporate_global"))

    db.session.commit()
    return jsonify(_user_to_json(user))


@bp.post("/<user_id>/sites")
@token_required
@role_required("CORPORATE_USER", "corporate")
def assign_sites(user_id: str):
    """
    Replace user's site access. Body: { site_ids: string[] }.
    - Deactivates UserSite records not in site_ids
    - Adds or reactivates UserSite for each site_id in the list
    - Uses replace semantics: full selection overwrites previous
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    data = request.get_json(silent=True) or {}
    site_ids = data.get("site_ids") or []
    site_accesses = data.get("site_accesses") or []
    default_grade = (data.get("default_grade") or "").strip() or None
    if default_grade and default_grade not in ("level_0", "level_1", "level_2", "level_3"):
        default_grade = None

    if site_accesses and not isinstance(site_accesses, list):
        return jsonify({"message": "site_accesses doit être une liste"}), 400
    if not site_accesses and not isinstance(site_ids, list):
        return jsonify({"message": "site_ids doit être une liste"}), 400

    parsed_accesses = []
    if site_accesses:
        for row in site_accesses:
            if not isinstance(row, dict):
                continue
            sid = str(row.get("site_id") or "").strip()
            if not sid:
                continue
            grade = (row.get("grade") or "").strip() or None
            if grade not in ("level_0", "level_1", "level_2", "level_3"):
                grade = default_grade
            access_types = row.get("access_types") or []
            if not isinstance(access_types, list):
                access_types = []
            parsed_accesses.append({
                "site_id": sid,
                "grade": grade,
                "access_types": [str(x).strip() for x in access_types if x is not None and str(x).strip()],
            })
        wanted_ids = [r["site_id"] for r in parsed_accesses]
    else:
        # Normalize to list of non-empty strings
        wanted_ids = [str(s).strip() for s in site_ids if s is not None and str(s).strip()]
        parsed_accesses = [{"site_id": sid, "grade": default_grade, "access_types": []} for sid in wanted_ids]

    granted_by = getattr(request, "user_id", None)

    # Deactivate sites no longer in the selection
    to_deactivate = UserSite.query.filter(
        UserSite.user_id == user_id,
        UserSite.is_active == True,
    )
    if wanted_ids:
        to_deactivate = to_deactivate.filter(~UserSite.site_id.in_(wanted_ids))
    to_deactivate.update({"is_active": False}, synchronize_session=False)

    # Add or reactivate wanted sites
    for row in parsed_accesses:
        sid = row["site_id"]
        site = Site.query.get(sid)
        if not site:
            continue
        existing = UserSite.query.filter_by(user_id=user_id, site_id=sid).first()
        if existing:
            existing.is_active = True
            existing.granted_by = granted_by
            existing.granted_at = datetime.utcnow()
            if row["grade"] is not None:
                existing.grade = row["grade"]
            if hasattr(existing, "set_access_types"):
                existing.set_access_types(row["access_types"])
        else:
            us = UserSite(
                user_id=user_id,
                site_id=sid,
                is_active=True,
                grade=row["grade"],
                granted_by=granted_by,
                granted_at=datetime.utcnow(),
            )
            if hasattr(us, "set_access_types"):
                us.set_access_types(row["access_types"])
            db.session.add(us)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Erreur lors de la mise à jour: {str(e)}"}), 500
    return jsonify({"message": "Accès aux sites mis à jour", "sites": _user_to_json(user, with_sites=True)["sites"]})


@bp.post("/<user_id>/reset-password")
@token_required
@role_required("CORPORATE_USER", "corporate")
def reset_password(user_id: str):
    """Generate a new random 12-char password. Returns it for one-time display to the user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 404

    alphabet = string.ascii_letters + string.digits + "!@#$%"
    new_password = "".join(secrets.choice(alphabet) for _ in range(12))
    user.password_hash = User.hash_password(new_password)
    db.session.commit()
    return jsonify({"password": new_password, "message": "Mot de passe généré. Transmettez-le de manière sécurisée."})


@bp.delete("/<user_id>/sites/<site_id>")
@token_required
@role_required("CORPORATE_USER", "corporate")
def revoke_site_access(user_id: str, site_id: str):
    """Revoke site access by setting UserSite.is_active = False."""
    us = UserSite.query.filter_by(user_id=user_id, site_id=site_id).first()
    if not us:
        return jsonify({"message": "Accès non trouvé"}), 404
    us.is_active = False
    db.session.commit()
    return jsonify({"message": "Accès révoqué"})


@bp.delete("/<user_id>")
@token_required
@role_required("CORPORATE_USER", "corporate")
def delete_user(user_id: str):
    """User deletion is disabled."""
    return jsonify({"message": "Suppression d'utilisateur désactivée"}), 403
