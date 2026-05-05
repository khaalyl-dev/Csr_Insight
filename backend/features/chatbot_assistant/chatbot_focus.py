"""
Infer which data slices to inject into the chatbot system prompt (keep context small).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChatbotDataFocus:
    """What to load from the DB for this turn."""

    plan_totals: bool = False
    plan_by_year: bool = False
    plan_samples: bool = False
    activity_totals: bool = False
    activity_samples: bool = False
    realized_totals: bool = False
    document_totals: bool = False
    site_codes_line: bool = False
    nav_routes: bool = False


def infer_chatbot_focus(prompt: str) -> ChatbotDataFocus:
    p = (prompt or "").lower()

    def _has(*needles: str) -> bool:
        return any(n in p for n in needles)

    asks_how_many = _has(
        "how many",
        "combien",
        "nombre de",
        "number of",
        "how much",
        "total de",
    ) or bool(re.search(r"\bcounts?\b", p))
    # "Why might my plan count differ from the list view?" — UI explanation, not a quantity request.
    explains_count_gap = (
        (bool(re.search(r"\bwhy\b", p)) or "pourquoi" in p)
        and (
            bool(
                re.search(
                    r"\bdiffers?\b|\bdifferent\b|\bdiscrepancy\b|\bmismatch\b|\bfewer\b|\bless than\b|\blist view\b|\bfilt(er|re)s?\b",
                    p,
                )
            )
            or _has("différent", "différence", "moins de", "vue liste")
        )
        and not _has("how many", "combien", "nombre de", "number of", "total de")
    )
    if explains_count_gap:
        asks_how_many = False
    # "plan" substring must not match inside "planned" / "planning" (those are activities).
    asks_plan_word = bool(re.search(r"(?<![a-z])plans?(?![a-z])", p))
    asks_plan = asks_plan_word or _has(
        "annual",
        "csr plan",
        "plan annuel",
        "validation",
        "draft",
        "submitted",
        "validated",
        "rejected",
        "rejet",
        "verrou",
        "locked",
    )
    asks_activity = _has(
        "activit",
        "activity",
        "activités",
        "planned",
        "planifi",
        "prévu",
    )
    asks_realized = _has("realized", "réalis", "realis", "saisie", "réalisation")
    asks_docs = _has("document", "file", "pdf", "upload", "fichier", "joint")
    asks_sites = _has("site", "plant", "usine", "entité", "sites")
    asks_nav = _has(
        "how to",
        "how do",
        "how can",
        "where ",
        "comment ",
        "navigate",
        "page",
        "écran",
        "menu",
        "trouve",
        "accès",
        "route",
        "open ",
        "aller ",
    )
    wants_samples = _has(
        "list",
        "liste",
        "show",
        "recent",
        "sample",
        "exemple",
        "dernier",
        "last ",
        "détail",
        "detail",
    )
    any_domain = asks_plan or asks_activity or asks_realized or asks_docs or asks_sites

    # Yearly breakdown (not bare "année" in "site et année", and not "year" in "site and year").
    year_kw = (
        _has("par année", "par an", "by year", "per year", "break down", "breakdown", "répartition", "repartition")
        or bool(re.search(r"\byears?\b", p))
    )
    if re.search(r"\bsite[s]?\s+(and|et)\s+(year|years|ann[eée]e|années)\b", p):
        year_kw = False

    # Numeric aggregates only for quantity-style questions (saves tokens vs. "how to … plan").
    plan_totals = asks_how_many and (asks_plan or not any_domain)
    activity_totals = asks_how_many and (asks_activity or not any_domain)
    if asks_how_many and not any_domain:
        plan_totals = True
        activity_totals = True

    plan_by_year = year_kw and (asks_plan or asks_how_many)
    if plan_by_year:
        plan_totals = True
    plan_samples = asks_plan and wants_samples and not asks_how_many
    activity_samples = asks_activity and wants_samples and not asks_how_many

    realized_totals = asks_realized or (asks_how_many and _has("realized", "réalis", "realis"))
    # "Which routes for documents…" is navigation, not a document count question.
    document_totals = asks_docs and not asks_nav

    # Include site names when counting plans/activities so the model can match a named site (e.g. Serbia).
    site_codes_line = (
        asks_sites or plan_samples or activity_samples or (asks_how_many and (asks_activity or asks_plan_word))
    )

    nav_routes = asks_nav or not any_domain

    # "Réalisées (lignes)" = realized rows, not planned-activity table totals.
    if asks_realized and ("ligne" in p or "row" in p or "lines" in p):
        activity_totals = False

    # Definitional English / "vs" questions should not pull numeric aggregates (avoids wrong totals in prose).
    conceptual = not asks_how_many and (
        _has("what is", "what's", "what are")
        or "difference between" in p
        or " différence entre " in p
        or " versus " in p
        or re.search(r"\bvs\.?\b", p)
    )
    if conceptual:
        plan_totals = False
        plan_by_year = False
        activity_totals = False
        realized_totals = False
        document_totals = False

    return ChatbotDataFocus(
        plan_totals=plan_totals,
        plan_by_year=plan_by_year,
        plan_samples=plan_samples,
        activity_totals=activity_totals,
        activity_samples=activity_samples,
        realized_totals=realized_totals,
        document_totals=document_totals,
        site_codes_line=site_codes_line,
        nav_routes=nav_routes,
    )
