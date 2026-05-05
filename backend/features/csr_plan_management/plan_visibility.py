"""
Which CSR plans a user may list — same rules as GET /api/csr-plans (before optional filters).

- Site users: plans for active user_sites only.
- Corporate with is_corporate_global True (or missing user row): all plans.
- Corporate with is_corporate_global False: plans for sites in user_sites only (same shape as site users).
  If no active user_sites rows exist yet, treat as unrestricted (same as global) so the plan list is not empty by misconfiguration.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import false as sql_false

from models import CsrPlan, User, UserSite


def data_scope_site_ids(user_id: str, role: str) -> Optional[List[str]]:
    """
    None = unrestricted (all sites).
    [] = no sites visible.
    Non-empty = restrict to these site_id values.
    """
    uid = (user_id or "").strip()
    r = (role or "").strip().upper()

    if r in ("SITE_USER", "SITE"):
        rows = UserSite.query.filter_by(user_id=uid, is_active=True).all()
        return [x.site_id for x in rows if x.site_id]

    if r in ("CORPORATE_USER", "CORPORATE"):
        user = User.query.get(uid)
        if user is None or bool(getattr(user, "is_corporate_global", False)):
            return None
        rows = UserSite.query.filter_by(user_id=uid, is_active=True).all()
        site_ids = [x.site_id for x in rows if x.site_id]
        if not site_ids:
            return None
        return site_ids

    return None


def csr_plans_visible_query(user_id: str, role: str):
    """Base query for plans visible to this user (matches list_plans before site_id/year/status)."""
    q = CsrPlan.query
    scope = data_scope_site_ids(user_id, role)
    if scope is None:
        return q
    if not scope:
        return q.filter(sql_false())
    return q.filter(CsrPlan.site_id.in_(scope))
