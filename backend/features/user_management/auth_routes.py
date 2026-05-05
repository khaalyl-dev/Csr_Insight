"""
Auth API routes - login, logout, profile, change password, profile photo.

This file defines all authentication-related API endpoints. When the frontend needs to
log in, get user profile, or change settings, it calls these routes.

Endpoints:
  POST /api/auth/login          - Authenticate user, create session, return JWT
  POST /api/auth/logout         - Revoke token and delete session
  GET  /api/auth/me             - Validate token, return minimal user info
  GET  /api/auth/profile         - Return full user profile
  PUT  /api/auth/profile         - Update current user's profile/settings
  PUT  /api/auth/change-password - Change current user's password
  POST /api/auth/profile-photo  - Upload profile photo (multipart file)
"""
import os
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

import jwt

from core import db, generate_access_token, token_required, revoke_jti
from core.permissions import effective_corporate_permissions
from core.jwt_utils import ACCESS_TOKEN_EXPIRATION_HOURS, SECRET_KEY
from models import User, UserSession, UserSite, Site, Document

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _latest_login_iso(user_id: str):
    """Get the user's most recent login timestamp as ISO string, or None if no session."""
    session = UserSession.query.filter_by(user_id=user_id).order_by(UserSession.created_at.desc()).first()
    return session.created_at.isoformat() if session and session.created_at else None


def _avatar_serve_url(user: User):
    """Public API path for profile photo (requires auth via same-origin + JWT header)."""
    if not user or not getattr(user, "avatar_url", None) or not user.avatar_url:
        return None
    return f"/api/documents/serve/{user.avatar_url}"


def _user_site_level(user_id: str):
    """Highest active site grade for a site user."""
    rows = UserSite.query.filter_by(user_id=user_id, is_active=True).all()
    grades = [(r.grade or "").strip().lower() for r in rows]
    if "level_3" in grades:
        return "level_3"
    if "level_2" in grades:
        return "level_2"
    if "level_1" in grades:
        return "level_1"
    if any(g in ("", "level_0") for g in grades):
        return "level_0"
    return None


def _profile_payload(user: User):
    """Build the full profile JSON (info, sites for SITE_USER, notification settings) to send to frontend."""
    data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "language": user.language or "en",
        "theme": user.theme or "light",
        "notifications": {
            "csr_plan_validation": bool(user.notify_csr_plan_validation),
            "activity_validation": bool(user.notify_activity_validation),
            "activity_reminders": bool(user.notify_activity_reminders),
            "weekly_summary_email": bool(user.notify_weekly_summary_email),
        },
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "last_login": _latest_login_iso(user.id),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "avatar_url": _avatar_serve_url(user),
        "permissions": effective_corporate_permissions(user) if user.role == "CORPORATE_USER" or user.get_permissions() else None,
    }

    if user.role == "SITE_USER":
        sites = UserSite.query.filter_by(user_id=user.id, is_active=True).all()
        data["sites"] = [
            {
                "id": us.id,
                "site_id": us.site_id,
                "site_name": Site.query.get(us.site_id).name if Site.query.get(us.site_id) else None,
                "site_code": Site.query.get(us.site_id).code if Site.query.get(us.site_id) else None,
                "granted_at": us.granted_at.isoformat() if us.granted_at else None,
            }
            for us in sites
        ]
    else:
        data["sites"] = []
    return data


def _get_client_info():
    """Extract client IP and User-Agent from request headers for session tracking."""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()
    user_agent = request.headers.get("User-Agent", "")[:512]
    return ip or None, user_agent or None


@bp.post("/login")
def login():
    """
    Login: validate credentials, create session, return JWT token.
    Blocks inactive users with 403. Stores session with access token jti.
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"message": "Email et mot de passe sont obligatoires."}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.verify_password(password):
        return jsonify({"message": "Email ou mot de passe incorrect."}), 401
    if not user.is_active:
        return jsonify({"message": "Compte désactivé. Contactez l'administrateur."}), 403

    token = generate_access_token(user.id, user.email, user.role)
    payload = _decode_token_for_session(token)
    if not payload:
        return jsonify({"message": "Erreur interne lors de la génération du token."}), 500

    ip_address, user_agent = _get_client_info()
    expires_at = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRATION_HOURS)

    session = UserSession(
        user_id=user.id,
        refresh_token=payload["jti"],
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        "token": token,
        "email": user.email,
        "role": user.role,
        "level": _user_site_level(user.id) if user.role == "SITE_USER" else None,
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar_url": _avatar_serve_url(user),
        "permissions": effective_corporate_permissions(user) if user.role == "CORPORATE_USER" or user.get_permissions() else None,
        "expires_at": expires_at.isoformat(),
    })


def _decode_token_for_session(token: str):
    """Decode JWT without revocation check to extract jti (token not yet stored)."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


@bp.post("/logout")
@token_required
def logout():
    """Revoke JWT and delete session."""
    jti = getattr(request, "jti", None)
    if not jti:
        return jsonify({"message": "Token identifier not found"}), 400

    try:
        revoke_jti(jti)
        UserSession.query.filter_by(refresh_token=jti).delete()
        db.session.commit()
        return jsonify({"message": "Déconnexion réussie"})
    except Exception:
        db.session.rollback()
        return jsonify({"message": "Failed to revoke token"}), 500


@bp.get("/me")
@token_required
def me():
    """Validate token and session, return minimal user info (user_id, email, role) for session check."""
    user_id = getattr(request, "user_id", None)
    jti = getattr(request, "jti", None)
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    session = UserSession.query.filter_by(refresh_token=jti, user_id=user_id).first()
    if not session or session.expires_at < datetime.utcnow():
        if session:
            db.session.delete(session)
            db.session.commit()
        return jsonify({"message": "Session expirée"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 401

    return jsonify({
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "level": _user_site_level(user.id) if user.role == "SITE_USER" else None,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar_url": _avatar_serve_url(user),
        "permissions": effective_corporate_permissions(user) if user.role == "CORPORATE_USER" or user.get_permissions() else None,
    })


@bp.get("/profile")
@token_required
def profile():
    """
    Return full profile of the current user (read-only).
    Requires valid JWT. Returns: id, first_name, last_name, email, role, is_active,
    created_at, and sites (for SITE_USER) with site_name, site_code, granted_at.
    """
    user_id = getattr(request, "user_id", None)
    jti = getattr(request, "jti", None)
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    session = UserSession.query.filter_by(refresh_token=jti, user_id=user_id).first()
    if not session or session.expires_at < datetime.utcnow():
        if session:
            db.session.delete(session)
            db.session.commit()
        return jsonify({"message": "Session expirée"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 401

    return jsonify(_profile_payload(user))


@bp.put("/profile")
@token_required
def update_profile():
    """
    Update the current user's editable profile fields.
    Supports partial updates:
      - first_name, last_name, phone
      - language (fr/en), theme (light/dark)
      - notifications: csr_plan_validation, activity_validation, activity_reminders, weekly_summary_email
    """
    user_id = getattr(request, "user_id", None)
    jti = getattr(request, "jti", None)
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    session = UserSession.query.filter_by(refresh_token=jti, user_id=user_id).first()
    if not session or session.expires_at < datetime.utcnow():
        if session:
            db.session.delete(session)
            db.session.commit()
        return jsonify({"message": "Session expirée"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 401

    data = request.get_json(silent=True) or {}
    if "first_name" in data:
        first_name = (data.get("first_name") or "").strip()
        if not first_name:
            return jsonify({"message": "Le prénom est obligatoire."}), 400
        user.first_name = first_name

    if "last_name" in data:
        last_name = (data.get("last_name") or "").strip()
        if not last_name:
            return jsonify({"message": "Le nom est obligatoire."}), 400
        user.last_name = last_name

    if "phone" in data:
        user.phone = (data.get("phone") or "").strip() or None

    if "language" in data:
        language = (data.get("language") or "").strip().lower()
        if language not in ("fr", "en"):
            return jsonify({"message": "language invalide (fr/en)."}), 400
        user.language = language

    if "theme" in data:
        theme = (data.get("theme") or "").strip().lower()
        if theme not in ("light", "dark"):
            return jsonify({"message": "theme invalide (light/dark)."}), 400
        user.theme = theme

    notifications = data.get("notifications")
    if notifications is not None:
        if not isinstance(notifications, dict):
            return jsonify({"message": "notifications doit être un objet."}), 400
        if "csr_plan_validation" in notifications:
            user.notify_csr_plan_validation = bool(notifications.get("csr_plan_validation"))
        if "activity_validation" in notifications:
            user.notify_activity_validation = bool(notifications.get("activity_validation"))
        if "activity_reminders" in notifications:
            user.notify_activity_reminders = bool(notifications.get("activity_reminders"))

    db.session.commit()
    return jsonify(_profile_payload(user))


@bp.put("/change-password")
@token_required
def change_password():
    """
    Change the current user's password.
    Requires: current_password, new_password (min 8 chars) in JSON body.
    Validates current password before updating.
    """
    user_id = getattr(request, "user_id", None)
    jti = getattr(request, "jti", None)
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    session = UserSession.query.filter_by(refresh_token=jti, user_id=user_id).first()
    if not session or session.expires_at < datetime.utcnow():
        if session:
            db.session.delete(session)
            db.session.commit()
        return jsonify({"message": "Session expirée"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 401

    data = request.get_json(silent=True) or {}
    current_password = (data.get("current_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()

    if not current_password:
        return jsonify({"message": "Le mot de passe actuel est obligatoire."}), 400
    if not new_password:
        return jsonify({"message": "Le nouveau mot de passe est obligatoire."}), 400
    if len(new_password) < 8:
        return jsonify({"message": "Le nouveau mot de passe doit contenir au moins 8 caractères."}), 400

    if not user.verify_password(current_password):
        return jsonify({"message": "Mot de passe actuel incorrect."}), 401

    user.password_hash = User.hash_password(new_password)
    db.session.commit()
    return jsonify({"message": "Mot de passe modifié avec succès."})


# Profile photo: store under media/profile_photos (same MEDIA_FOLDER as documents)
_PROFILE_PHOTOS_SUBFOLDER = "profile_photos"
_ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "gif", "webp"}


def _get_profile_photos_dir():
    """Return absolute path to media/profile_photos (same MEDIA_FOLDER as documents route)."""
    from config import get_media_folder
    return os.path.join(get_media_folder(), _PROFILE_PHOTOS_SUBFOLDER)


@bp.post("/profile-photo")
@token_required
def upload_profile_photo():
    """
    Upload current user's profile photo. Multipart: file (image).
    Saves to media/profile_photos/{user_id}.{ext}, updates user.avatar_url.
    """
    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"message": "Unauthorized"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "Utilisateur introuvable"}), 401

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"message": "Aucun fichier fourni."}), 400

    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in _ALLOWED_PHOTO_EXT:
        return jsonify({"message": "Format non autorisé. Utilisez PNG, JPG, JPEG, GIF ou WEBP."}), 400

    photos_dir = _get_profile_photos_dir()
    os.makedirs(photos_dir, exist_ok=True)

    # Remove old profile photo document and file if any
    if getattr(user, "avatar_url", None) and user.avatar_url:
        old_path = os.path.join(_get_profile_photos_dir(), os.path.basename(user.avatar_url))
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    Document.query.filter_by(entity_type="USER_PROFILE", entity_id=user_id).delete()

    filename = f"{user_id}.{ext}"
    relative_path = f"{_PROFILE_PHOTOS_SUBFOLDER}/{filename}"
    save_path = os.path.join(photos_dir, filename)
    file.save(save_path)

    user.avatar_url = relative_path
    # Store as document (excluded from documents list in UI via entity_type USER_PROFILE)
    doc = Document(
        site_id=None,
        file_name=f"photo_profil.{ext}",
        file_path=relative_path,
        file_type=ext.upper(),
        is_pinned=False,
        uploaded_by=user_id,
        entity_type="USER_PROFILE",
        entity_id=user_id,
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({
        "message": "Photo de profil mise à jour.",
        "avatar_url": f"/api/documents/serve/{relative_path}",
    })
