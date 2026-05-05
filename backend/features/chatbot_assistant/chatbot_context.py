"""
Build a permission- and site-aware snapshot for the chatbot.

Only sections relevant to the user's message are loaded (infer_chatbot_focus).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from collections import Counter
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from core.db import db
from core.permissions import ALLOWED_PERMISSION_KEYS, has_permission
from features.csr_plan_management.plan_visibility import (
    csr_plans_visible_query,
    data_scope_site_ids,
)
from models import CsrActivity, CsrPlan, Document, RealizedCsr, Site, User

from features.planned_activity_management.activity_effective_status import (
    build_cr_effective_context,
    effective_planned_activity_status,
)

from .chatbot_focus import infer_chatbot_focus

MAX_PLAN_SAMPLES = 6
MAX_ACTIVITY_SAMPLES = 4
MAX_SITE_CODES_INLINE = 12
MAX_PERMISSION_KEYS_INLINE = 18
MAX_CONTEXT_CHARS = 6000

# Canonical status order for chatbot answers (zeros included so each type is explicit).
PLAN_STATUS_ORDER: Tuple[str, ...] = ("DRAFT", "SUBMITTED", "VALIDATED", "REJECTED", "LOCKED")
ACTIVITY_STATUS_ORDER: Tuple[str, ...] = (
    "PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "UNDER_REVIEW",
    "REJECTED",
    "CANCELLED",
    "DRAFT",
    "SUBMITTED",
    "VALIDATED",
)

_PLAN_STATUS_HELP = {
    "DRAFT": "draft / brouillon",
    "SUBMITTED": "under review (submitted) / en attente de validation",
    "VALIDATED": "validated / validé",
    "REJECTED": "rejected / rejeté",
    "LOCKED": "locked / verrouillé",
}
_ACTIVITY_STATUS_HELP = {
    "PLANNED": "planned (future plan year) / planifiée",
    "IN_PROGRESS": "in progress (current plan year) / en cours",
    "COMPLETED": "completed (past plan year) / terminée",
    "UNDER_REVIEW": "under review (change request or submission) / en revue",
    "REJECTED": "rejected / rejetée",
    "CANCELLED": "cancelled / annulée",
    "DRAFT": "workflow draft (plan not yet validated) / brouillon",
    "SUBMITTED": "submitted (workflow) / soumise",
    "VALIDATED": "validated (workflow) / validée",
}


def _ordered_counts_from_rows(
    rows: List[Tuple[Any, int]],
    canonical: Tuple[str, ...],
) -> Tuple[int, str, List[Tuple[str, int]]]:
    """Merge SQL group_by rows into canonical order; returns (total, breakdown_str, ordered_pairs)."""
    raw: Dict[str, int] = {}
    for s, c in rows:
        key = (str(s or "UNKNOWN")).strip().upper()
        raw[key] = raw.get(key, 0) + int(c or 0)
    total = sum(raw.values())
    ordered: List[Tuple[str, int]] = []
    seen: set[str] = set()
    for st in canonical:
        ordered.append((st, raw.get(st, 0)))
        seen.add(st)
    for k in sorted(raw.keys()):
        if k not in seen and raw[k] > 0:
            ordered.append((k, raw[k]))
    breakdown = ", ".join(f"{s}: {n}" for s, n in ordered)
    # Callers unpack as (total, breakdown, ordered_items).
    return total, breakdown, ordered


def _plan_aggregates_for_user(
    user_id: str, role: str, *, site_id: Optional[str] = None
) -> Tuple[int, str, List[Tuple[str, int]]]:
    """Same rows as GET /api/csr-plans (no UI filters)."""
    base = csr_plans_visible_query(user_id, role)
    if site_id:
        base = base.filter(CsrPlan.site_id == site_id)
    rows = base.with_entities(CsrPlan.status, func.count(CsrPlan.id)).group_by(CsrPlan.status).all()
    return _ordered_counts_from_rows(rows, PLAN_STATUS_ORDER)


def _plans_by_year_summary(user_id: str, role: str) -> str:
    base = csr_plans_visible_query(user_id, role)
    rows = (
        base.with_entities(CsrPlan.year, func.count(CsrPlan.id))
        .group_by(CsrPlan.year)
        .order_by(CsrPlan.year.desc())
        .limit(10)
        .all()
    )
    if not rows:
        return "none"
    return ", ".join(f"{int(y)}: {int(c)}" for y, c in rows)


def _realized_row_count(user_id: str, role: str) -> int:
    scope = data_scope_site_ids(user_id, role)
    if scope is not None and not scope:
        return 0
    q = (
        db.session.query(RealizedCsr)
        .join(CsrActivity, CsrActivity.id == RealizedCsr.activity_id)
        .join(CsrPlan, CsrPlan.id == CsrActivity.plan_id)
    )
    if scope is not None:
        q = q.filter(CsrPlan.site_id.in_(scope))
    return int(q.count() or 0)


def _document_site_linked_count(user_id: str, role: str) -> int:
    scope = data_scope_site_ids(user_id, role)
    if scope is not None and not scope:
        return 0
    q = Document.query.filter(Document.site_id.isnot(None))
    if scope is not None:
        q = q.filter(Document.site_id.in_(scope))
    return int(q.count() or 0)


def _activity_aggregates_for_user(
    user_id: str, role: str, *, site_id: Optional[str] = None
) -> Tuple[int, str, List[Tuple[str, int]]]:
    """Counts by **effective** activity status (same rules as GET /api/csr-activities JSON)."""
    scope = data_scope_site_ids(user_id, role)
    if scope is not None and not scope:
        ordered = [(st, 0) for st in ACTIVITY_STATUS_ORDER]
        return 0, ", ".join(f"{s}: 0" for s, _ in ordered), ordered
    q = (
        db.session.query(CsrActivity)
        .options(joinedload(CsrActivity.plan))
        .join(CsrPlan, CsrPlan.id == CsrActivity.plan_id)
    )
    if scope is not None:
        q = q.filter(CsrPlan.site_id.in_(scope))
    if site_id:
        q = q.filter(CsrPlan.site_id == site_id)
    activities = q.all()
    if not activities:
        ordered = [(st, 0) for st in ACTIVITY_STATUS_ORDER]
        return 0, ", ".join(f"{s}: 0" for s, _ in ordered), ordered
    cr_ctx = build_cr_effective_context(activities)
    ctr: Counter[str] = Counter()
    for a in activities:
        eff = effective_planned_activity_status(a, a.plan, cr_ctx)
        ctr[eff] += 1
    rows = list(ctr.items())
    return _ordered_counts_from_rows(rows, ACTIVITY_STATUS_ORDER)


_SITE_STOPWORDS = frozenset(
    {
        "how",
        "many",
        "much",
        "have",
        "has",
        "the",
        "for",
        "with",
        "from",
        "your",
        "you",
        "are",
        "there",
        "what",
        "when",
        "where",
        "which",
        "site",
        "sites",
        "plant",
        "plants",
        "csr",
        "plan",
        "plans",
        "activity",
        "activities",
        "activitie",
        "planned",
        "realized",
        "does",
        "number",
        "count",
        "counts",
        "total",
        "all",
        "any",
        "some",
        "this",
        "that",
        "our",
        "can",
        "please",
        "tell",
        "give",
        "show",
        "list",
        "combien",
        "nombre",
        "des",
        "les",
        "une",
        "sur",
        "dans",
        "pour",
        "quel",
        "quelle",
        "est",
        "sont",
        "vous",
        "mes",
        "mon",
        "ma",
        "need",
        "want",
        "about",
        "into",
        "they",
        "them",
        "their",
        "draft",
        "submitted",
        "validated",
        "rejected",
        "locked",
        "brouillon",
        "valide",
        "validé",
        "soumis",
    }
)


def _resolve_single_site_for_prompt(
    user_prompt: str, scope: Optional[List[str]]
) -> Tuple[Optional[str], Optional[Site], str]:
    """
    If the user names one site (code or name fragment) in scope, return its id.
    Otherwise (none, ambiguous) return (None, None, short reason for USER_DATA).
    """
    sites = _format_sites(scope)
    if not sites:
        return None, None, "no_sites"
    pl = (user_prompt or "").lower()
    if len(sites) == 1:
        return sites[0].id, sites[0], "single_site_scope"

    m = re.search(r"\bsite\s+of\s+([a-z0-9][a-z0-9\s-]{1,40})", pl, re.I)
    if m:
        hint = m.group(1).strip().lower()
        hint = re.split(r"\s+", hint)[0] if hint else ""
        if hint and len(hint) >= 2:
            matched_sites = [
                s
                for s in sites
                if hint in (s.code or "").lower() or hint in (s.name or "").lower()
            ]
            if len(matched_sites) == 1:
                s0 = matched_sites[0]
                if scope is None or s0.id in scope:
                    return s0.id, s0, "site_of_phrase"

    tokens = [t for t in re.findall(r"\b[a-z][a-z0-9]{2,}\b", pl) if t not in _SITE_STOPWORDS]
    # "how many plans in serbia" → pick up place after in/for/sur/… (no need for the word "site").
    for m in re.finditer(
        r"\b(?:in|inside|for|at|on|near|from|sur|sous|à|chez|pour|aux?|en)\s+([a-z][a-z0-9]{2,50})\b",
        pl,
        re.I,
    ):
        w = m.group(1).lower()
        if w not in _SITE_STOPWORDS and w not in tokens:
            tokens.append(w)
    if not tokens:
        return None, None, "no_tokens"

    def _score(site: Site) -> int:
        code = (site.code or "").lower()
        name = (site.name or "").lower()
        sc = 0
        for t in tokens:
            if len(t) <= 2:
                continue
            if t == code or (len(t) >= 3 and t in code):
                sc += 3
            elif len(t) >= 3 and t in name:
                sc += 2
        return sc

    scored = [(s, _score(s)) for s in sites]
    scored.sort(key=lambda x: (-x[1], x[0].code or ""))
    best_site, best = scored[0]
    second = scored[1][1] if len(scored) > 1 else -1
    if best <= 0:
        return None, None, "no_match"
    if best == second:
        return None, None, "ambiguous"
    sid = best_site.id
    if scope is not None and sid not in scope:
        return None, None, "out_of_scope"
    return sid, best_site, "matched"


def _resolved_site_for_counts(
    user_prompt: str, scope: Optional[List[str]], focus
) -> Tuple[Optional[str], Optional[Site], str]:
    """Pick one site when the user names a site and asks for plan/activity counts."""
    if not (getattr(focus, "activity_totals", False) or getattr(focus, "plan_totals", False)):
        return None, None, ""
    return _resolve_single_site_for_prompt(user_prompt, scope)


def _combined_plan_activity_one_line_totals_prompt(user_prompt: str) -> bool:
    """e.g. 'How many plans and how many activities — one line each?' → totals only in bracket line."""
    pl = (user_prompt or "").lower()
    has_plan = bool(re.search(r"(?<![a-z])plans?(?![a-z])", pl)) or "csr plan" in pl
    has_act = "activit" in pl or "activités" in pl or "planifi" in pl
    if not (has_plan and has_act):
        return False
    return any(t in pl for t in ("one line", "une ligne", "one each", "each line"))


def _norm_scope_role(role: str) -> str:
    r = (role or "").strip().upper()
    if r in ("SITE_USER", "SITE"):
        return "SITE"
    if r in ("CORPORATE_USER", "CORPORATE"):
        return "CORPORATE"
    return r


def _format_sites(scope: Optional[Sequence[str]]) -> List[Site]:
    if scope is None:
        return Site.query.order_by(Site.code.asc()).limit(80).all()
    if not scope:
        return []
    return Site.query.filter(Site.id.in_(scope)).order_by(Site.code.asc()).all()


def _scope_one_line(scope: Optional[List[str]]) -> str:
    if scope is None:
        return "all sites (global)"
    if not scope:
        return "no sites assigned"
    sites = (
        Site.query.filter(Site.id.in_(scope))
        .order_by(Site.code.asc())
        .limit(MAX_SITE_CODES_INLINE)
        .all()
    )
    codes = [s.code for s in sites]
    more = len(scope) - len(codes)
    tail = f" (+{more} more)" if more > 0 else ""
    return f"{len(scope)} site(s): {', '.join(codes)}{tail}"


def _permission_compact(user_id: str, role: str) -> str:
    perm_line, keys = _permission_summary(user_id, role)
    if not keys:
        return perm_line
    if len(keys) > MAX_PERMISSION_KEYS_INLINE:
        sample = keys[:MAX_PERMISSION_KEYS_INLINE]
        return f"{perm_line} | keys_sample={','.join(sample)} (+{len(keys) - len(sample)})"
    return f"{perm_line} | keys={','.join(keys)}"


def _permission_summary(user_id: str, role: str) -> Tuple[str, List[str]]:
    """Human-readable permission line + list of granted keys (subset)."""
    scope = _norm_scope_role(role)
    keys: List[str] = []
    if scope == "CORPORATE":
        user = User.query.get(user_id)
        if not user:
            return "Unknown user", []
        from core.permissions import effective_corporate_permissions

        eff = effective_corporate_permissions(user)
        keys = list(eff.get("keys") or [])
        if len(keys) >= len(ALLOWED_PERMISSION_KEYS):
            return "Corporate user — full module permissions (customizable per user).", keys
        return "Corporate user — custom permissions (see key list below).", sorted(keys)

    user = User.query.get(user_id)
    if not user:
        return "Unknown user", []
    explicit = user.get_permissions()
    if explicit and explicit.get("keys"):
        keys = sorted(explicit["keys"])
        return "Site user — permissions restricted to the keys below.", keys
    return (
        "Site user — default policy: all actions allowed for data on assigned sites only.",
        [],
    )


def build_chatbot_prompt_enrichment(user_id: str, role: str, user_prompt: str) -> str:
    """
    Short bracketed line prepended to the user message with exact DB figures for this scope.

    Helps small local models (e.g. phi3:mini) answer count questions without drifting off USER_DATA.
    """
    uid = (user_id or "").strip()
    if not User.query.get(uid):
        return ""
    focus = infer_chatbot_focus(user_prompt or "")
    parts: List[str] = []
    scope = data_scope_site_ids(uid, role)
    no_access = scope is not None and not scope
    site_id, site_obj, _site_how = _resolved_site_for_counts(user_prompt or "", scope, focus)

    combined_totals_only = _combined_plan_activity_one_line_totals_prompt(user_prompt or "")

    if focus.plan_totals and has_permission(uid, role, "plan", "read"):
        if no_access:
            parts.append("plans_total=0")
            if not (combined_totals_only and focus.activity_totals):
                for st in PLAN_STATUS_ORDER:
                    parts.append(f"PLAN_{st}=0")
        else:
            if site_obj:
                parts.append(f"plans_count_site={site_obj.code}")
            t, _br, plan_items = _plan_aggregates_for_user(uid, role, site_id=site_id)
            parts.append(f"plans_total={t}")
            if not (combined_totals_only and focus.activity_totals):
                for code, n in plan_items:
                    parts.append(f"PLAN_{code}={n}")
    if focus.plan_by_year and has_permission(uid, role, "plan", "read") and not no_access:
        parts.append(f"plans_by_year={_plans_by_year_summary(uid, role)}")

    if focus.activity_totals and has_permission(uid, role, "activity", "read"):
        if no_access:
            parts.append("activities_total=0")
            if not (combined_totals_only and focus.plan_totals):
                for st in ACTIVITY_STATUS_ORDER:
                    parts.append(f"ACT_{st}=0")
        else:
            if site_obj:
                parts.append(f"activities_count_site={site_obj.code}")
            t, _br, act_items = _activity_aggregates_for_user(uid, role, site_id=site_id)
            parts.append(f"activities_total={t}")
            if not (combined_totals_only and focus.plan_totals):
                for code, n in act_items:
                    parts.append(f"ACT_{code}={n}")

    if focus.realized_totals and has_permission(uid, role, "realized_activity", "read"):
        parts.append(f"realized_rows={0 if no_access else _realized_row_count(uid, role)}")

    if focus.document_totals and has_permission(uid, role, "document", "read"):
        parts.append(f"documents_site_linked={0 if no_access else _document_site_linked_count(uid, role)}")

    if not parts:
        return ""
    return (
        "[Use exactly these figures for your visible scope (same digits in your answer): "
        + "; ".join(parts)
        + ".]\n"
    )


def build_chatbot_system_context(user_id: str, role: str, user_prompt: str) -> str:
    """Slim USER_DATA: only sections relevant to ``user_prompt``."""
    focus = infer_chatbot_focus(user_prompt or "")
    uid = (user_id or "").strip()
    lines: List[str] = [
        "### USER_DATA (filtered to this question)",
        "Use only facts below. Answer with the numbers given; do not refuse when totals are listed. "
        "If the user names a site, use the matching site line and any count filter line. Mention routes only if they ask where to click.",
    ]

    user = User.query.get(uid)
    if not user:
        return "\n".join(lines + ["User not found."])

    corp_flag = ""
    if (user.role or "").upper() == "CORPORATE_USER":
        corp_flag = f" | corporate_all_sites={'yes' if bool(getattr(user, 'is_corporate_global', False)) else 'no'}"
    lines.append(f"User: {user.first_name} {user.last_name} ({user.email}) | role={user.role}{corp_flag}")
    lines.append(f"Permissions: {_permission_compact(uid, role)}")
    scope = data_scope_site_ids(uid, role)
    lines.append(f"Scope: {_scope_one_line(scope)}")
    site_id, site_obj, site_how = _resolved_site_for_counts(user_prompt or "", scope, focus)

    if focus.site_codes_line:
        sites = _format_sites(scope)
        if sites:
            lines.append("Sites (compact):")
            for s in sites[:MAX_SITE_CODES_INLINE]:
                lines.append(f"  {s.code}: {s.name}")
            if len(sites) > MAX_SITE_CODES_INLINE:
                lines.append(f"  … +{len(sites) - MAX_SITE_CODES_INLINE} sites")

    no_access = scope is not None and not scope

    if site_how == "ambiguous" and (focus.activity_totals or focus.plan_totals):
        lines.append(
            "Site name in your message matches several sites; counts below are for your full scope. "
            "Repeat the question with one site code from the list above."
        )
    elif site_how == "no_match" and (focus.activity_totals or focus.plan_totals):
        lines.append(
            "No site in your scope clearly matched a place or name in your message "
            "(compare with the Sites list above). Plan/activity counts below are for your full visible scope, not one country unless a single site was resolved."
        )

    if focus.plan_totals:
        if not has_permission(uid, role, "plan", "read"):
            lines.append("Plans: not available (no plan.read).")
        elif no_access:
            lines.append("Plans: 0 (no site access).")
        else:
            total, _br, plan_items = _plan_aggregates_for_user(uid, role, site_id=site_id)
            hdr = (
                f"Plans: total={total} for site {site_obj.code} ({site_obj.name})."
                if site_obj
                else f"Plans: total={total} (matches /csr-plans unfiltered)."
            )
            lines.append(f"{hdr} Counts by status — one number per line:")
            for code, n in plan_items:
                gloss = _PLAN_STATUS_HELP.get(code, code)
                lines.append(f"  {code}: {n} ({gloss})")
            if focus.plan_by_year:
                lines.append(f"Plans by year: {_plans_by_year_summary(uid, role)}")
            if focus.plan_samples:
                recent = (
                    csr_plans_visible_query(uid, role)
                    .order_by(CsrPlan.year.desc(), CsrPlan.created_at.desc())
                    .limit(MAX_PLAN_SAMPLES)
                    .all()
                )
                if recent:
                    lines.append("Plan samples:")
                    for p in recent:
                        site = p.site
                        code = (getattr(site, "code", None) or "?").strip()
                        lines.append(f"  {code} {p.year} {p.status} id={str(p.id).strip()}")

    if focus.activity_totals:
        if not has_permission(uid, role, "activity", "read"):
            lines.append("Planned activities: not available (no activity.read).")
        elif no_access:
            lines.append("Planned activities: 0 (no site access).")
        else:
            t, _br, act_items = _activity_aggregates_for_user(uid, role, site_id=site_id)
            hdr = (
                f"Planned activities: total={t} for site {site_obj.code} ({site_obj.name})."
                if site_obj
                else f"Planned activities: total={t}."
            )
            lines.append(f"{hdr} Counts by **effective** activity status — one number per line:")
            for code, n in act_items:
                gloss = _ACTIVITY_STATUS_HELP.get(code, code)
                lines.append(f"  {code}: {n} ({gloss})")
            if focus.activity_samples:
                sample_q = (
                    db.session.query(CsrActivity)
                    .options(joinedload(CsrActivity.plan).joinedload(CsrPlan.site))
                    .join(CsrPlan, CsrPlan.id == CsrActivity.plan_id)
                )
                if scope is not None:
                    sample_q = sample_q.filter(CsrPlan.site_id.in_(scope))
                sample = sample_q.order_by(CsrActivity.updated_at.desc()).limit(MAX_ACTIVITY_SAMPLES).all()
                if sample:
                    lines.append("Activity samples (effective_status, stored status in parentheses):")
                    ctx_s = build_cr_effective_context(sample)
                    for a in sample:
                        pl = a.plan
                        code = (getattr(pl.site, "code", None) or "?").strip() if pl and pl.site else "?"
                        yr = pl.year if pl else "?"
                        eff = effective_planned_activity_status(a, pl, ctx_s)
                        raw = (a.status or "DRAFT").upper()
                        lines.append(f"  {code} {yr}: {a.title[:80]} ({eff}, stored={raw})")

    if focus.realized_totals:
        if not has_permission(uid, role, "realized_activity", "read"):
            lines.append("Realized rows: not available (no realized_activity.read).")
        elif no_access:
            lines.append("Realized rows: 0 (no site access).")
        else:
            lines.append(f"Realized activity rows: {_realized_row_count(uid, role)}")

    if focus.document_totals:
        if not has_permission(uid, role, "document", "read"):
            lines.append("Documents: not available (no document.read).")
        elif no_access:
            lines.append("Documents: 0 (no site access).")
        else:
            lines.append(f"Documents (site-linked): {_document_site_linked_count(uid, role)}")

    if focus.nav_routes:
        lines.append(
            "Routes: /dashboard /csr-plans /planned-activities /realized-csr /documents /changes /sites /admin/users /admin/audit"
        )

    text = "\n".join(lines)
    if len(text) > MAX_CONTEXT_CHARS:
        return text[: MAX_CONTEXT_CHARS - 80] + "\n... [truncated]"
    return text


CHATBOT_SYSTEM_INSTRUCTIONS = """You are CSR Insight's in-app assistant.

Style (strict)
- Answer in plain language: usually 1–4 short sentences, or a few bullets if listing facts. No long intros or outros.
- Do not open with greetings like "Bonjour", "Hello", or "How can I help you today?" unless the user greeted you first — and even then, one short line only.
- Do not offer generic help ("let me know if…", "feel free to ask…") or repeat the same idea twice.
- Do not suggest app routes or "navigate to /…" unless the user explicitly asks where to go in the UI.
- Never say you cannot access live data, cannot use the app, or are not connected to CSR Insight when USER_DATA or the bracketed facts line already contains plan or activity totals — that block is the live snapshot for this user.
- For questions like "how many plans in Serbia" (or another place): if USER_DATA shows totals for one site, answer with those; if it explains that no site matched and gives full-scope totals, answer with those totals and say clearly they are across your allowed sites, and suggest matching a site code or name from the Sites list — still without refusing.

Formatting (counts and statuses)
- Do not paste or quote the bracketed prefix line (the one starting with [Use exactly these figures…]) and do not echo raw key=value tokens such as PLAN_DRAFT=0 or plans_count_site=… — translate them into normal words.
- Do not wrap numbers in ASCII single quotes.
- Do not use markdown asterisks for bold; the UI will emphasize list lines for you. Use simple hyphen bullets at the start of each line.
- When several plan or activity statuses matter (draft, submitted, validated, etc.): put one short headline on the first line (total + site if relevant), then a bullet list with one status per line, format exactly:
  - DRAFT: 4
  - SUBMITTED: 0
  - VALIDATED: 2
  (same idea in French with French labels if the user wrote in French). Each bullet line must start with "- " (hyphen and space).

Facts
- USER_DATA is small and may omit modules not relevant to the question.
- If your prompt starts with a bracketed line like [Use exactly these figures…], repeat every integer from that line in your answer for the matching metrics (same digits; do not round or estimate), but only inside the headline or bullets — never copy that bracketed line itself.
- When USER_DATA shows plan or planned-activity counts by status, use the bullet list rule above so every status count is visible on its own line.
- When USER_DATA says totals are for one site (site code/name in the same block), answer with that site’s counts directly. Do not refuse, hedge, or send the user to URLs instead of giving those numbers.
- Quote only numbers present in USER_DATA or that bracketed line. Plan totals match /csr-plans with all filters cleared unless USER_DATA says otherwise.
- If on-screen row counts differ, mention filters (year, status, planned vs realized) in one brief phrase — not a lecture.
- Do not invent data.
- Never print fake sections such as "### USER_DATA" or invented emails or figures not present in the real USER_DATA / bracketed facts line.

Language: match the user's language (French or English)."""
