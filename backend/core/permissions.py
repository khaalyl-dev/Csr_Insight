"""
Corporate RBAC helpers.

Supports legacy matrix format and key-based permissions:
{"keys": ["plan.read", "activity.validate", ...]}
"""
from models import User


PERMISSION_CATALOG = {
    "dashboard": ("read",),
    "task": ("read",),
    "plan": (
        "read",
        "create",
        "update",
        "delete",
        "submit",
        "approve",
        "reject",
        "validate",
        "upload_excel",
        "bulk_submit",
        "bulk_delete",
    ),
    "activity": (
        "read",
        "create",
        "update",
        "delete",
        "approve",
        "reject",
        "validate",
        "submit_modification_review",
        "resubmit",
    ),
    "realized_activity": ("read", "create", "update", "delete"),
    "document": ("read", "update", "delete"),
    "change_request": ("read", "create", "review", "history"),
    "site": ("read", "create", "update", "delete"),
    "category": ("read", "create", "update", "delete"),
    "user": ("read", "create", "update"),
    "audit_log": ("read", "export"),
    "notification": ("read", "manage"),
}
ALLOWED_PERMISSION_KEYS = {
    f"{resource}.{action}"
    for resource, actions in PERMISSION_CATALOG.items()
    for action in actions
}
PERMISSION_ACTIONS = ("create", "read", "update", "delete", "approve", "reject")
PERMISSION_RESOURCES = ("plan", "activity")

SITE_USER_CREATOR_KEYS = {
    "dashboard.read",
    "task.read",
    "plan.read", "plan.create", "plan.update", "plan.delete", "plan.submit", "plan.upload_excel", "plan.bulk_delete",
    "activity.read", "activity.create", "activity.update", "activity.delete", "activity.submit_modification_review", "activity.resubmit",
    "realized_activity.read", "realized_activity.create", "realized_activity.update", "realized_activity.delete",
    "document.read", "document.update", "document.delete",
    "change_request.read", "change_request.create", "change_request.history",
}
SITE_USER_VALIDATOR_KEYS = {
    "dashboard.read",
    "task.read",
    "plan.read", "plan.validate",
    "activity.read", "activity.validate",
    "document.read",
    "change_request.read", "change_request.review", "change_request.history",
}


def _site_user_allowed_keys(user_id: str):
    """Default allowed keys for site users based on grade."""
    from models import UserSite
    grades = [
        (us.grade or "").strip().lower()
        for us in UserSite.query.filter_by(user_id=user_id, is_active=True).all()
    ]
    if any(g in ("", "level_0") for g in grades):
        return SITE_USER_CREATOR_KEYS
    if any(g in ("level_1", "level_2", "level_3") for g in grades):
        return SITE_USER_VALIDATOR_KEYS
    return set()

def normalize_permissions(value):
    """Return a normalized permissions dict, or None when invalid."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    # Global key-based permissions model: {"keys": ["plan.read", ...]}
    if "keys" in value:
        keys = value.get("keys")
        if not isinstance(keys, list):
            return None
        normalized_keys = []
        for k in keys:
            if k is None:
                continue
            key = str(k).strip()
            if not key:
                continue
            if key in ALLOWED_PERMISSION_KEYS:
                normalized_keys.append(key)
        return {"keys": sorted(set(normalized_keys))}
    out = {}
    for resource in PERMISSION_RESOURCES:
        raw_resource = value.get(resource)
        if raw_resource is None:
            continue
        if not isinstance(raw_resource, dict):
            return None
        out[resource] = {}
        for action in PERMISSION_ACTIONS:
            if action in raw_resource:
                out[resource][action] = bool(raw_resource[action])
    return out


def effective_corporate_permissions(user: User):
    """Effective permissions for a corporate user.

    Default corporate behavior: full access to all permission keys.
    """
    base = {"keys": sorted(ALLOWED_PERMISSION_KEYS)}
    custom = normalize_permissions(user.get_permissions())
    if custom is None:
        return base
    if "keys" in custom:
        return {"keys": custom["keys"]}
    for resource, actions in custom.items():
        if resource not in base:
            continue
        for action, allowed in actions.items():
            if action in base[resource]:
                base[resource][action] = bool(allowed)
    return base


def has_permission(user_id: str, role: str, resource: str, action: str) -> bool:
    key = f"{resource}.{action}"
    if key not in ALLOWED_PERMISSION_KEYS:
        return False
    user = User.query.get(user_id)
    if not user:
        return False
    role_norm = (role or "").upper()
    # For non-corporate users: keep backward compatibility (allowed) unless explicit key-based permissions exist.
    if role_norm not in ("CORPORATE_USER", "CORPORATE"):
        allowed_keys = _site_user_allowed_keys(user_id)
        base_allowed = (
            key in allowed_keys
            or (action in ("approve", "reject") and f"{resource}.validate" in allowed_keys)
        )
        if not base_allowed:
            return False
        explicit = normalize_permissions(user.get_permissions())
        if not explicit or "keys" not in explicit:
            return True
        keys = set(explicit.get("keys") or [])
        if key in keys:
            return True
        if action in ("approve", "reject") and f"{resource}.validate" in keys:
            return True
        return False
    perms = effective_corporate_permissions(user)
    if isinstance(perms, dict) and "keys" in perms:
        keys = set(perms.get("keys") or [])
        if key in keys:
            return True
        # Unified validation key: one permission controls both approve and reject.
        if action in ("approve", "reject") and f"{resource}.validate" in keys:
            return True
        return False
    return bool(perms.get(resource, {}).get(action, False))
