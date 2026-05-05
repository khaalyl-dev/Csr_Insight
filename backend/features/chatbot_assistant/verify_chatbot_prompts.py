#!/usr/bin/env python3
"""
Run chatbot test prompts against the local API + Ollama; verify numeric answers vs DB.

Usage (from backend/ directory, with dependencies installed in .venv):

  PYTHONPATH=. .venv/bin/python3 features/chatbot_assistant/verify_chatbot_prompts.py

If you run plain ``python3`` and Flask is missing, this script tries ``backend/.venv`` (or repo
``.venv``) and re-executes itself automatically once.

Requires: Flask app + DB + Ollama reachable (OLLAMA_* in .env). Fails fast if login or Ollama fails.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import List, Tuple

# backend/ on path
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_VENV_REEXEC = "CSR_CHATBOT_VERIFY_REEXEC"


def _maybe_reexec_with_venv() -> None:
    """Re-run under backend/.venv or repo .venv when system python has no Flask."""
    if os.environ.get(_VENV_REEXEC) == "1":
        return
    try:
        import flask  # noqa: F401
        return
    except ImportError:
        pass
    script = Path(__file__).resolve()
    candidates = [
        _BACKEND / ".venv" / "bin" / "python3",
        _BACKEND / "venv" / "bin" / "python3",
        _BACKEND.parent / ".venv" / "bin" / "python3",
    ]
    for py in candidates:
        if not py.is_file():
            continue
        env = os.environ.copy()
        env[_VENV_REEXEC] = "1"
        pp = str(_BACKEND)
        if env.get("PYTHONPATH"):
            if pp not in env["PYTHONPATH"]:
                env["PYTHONPATH"] = pp + os.pathsep + env["PYTHONPATH"]
        else:
            env["PYTHONPATH"] = pp
        os.execve(str(py), [str(py), str(script)] + sys.argv[1:], env)
    print(
        "Flask is not installed for this Python. Create a venv under backend and install deps:\n"
        "  cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\n"
        "  PYTHONPATH=. .venv/bin/python3 features/chatbot_assistant/verify_chatbot_prompts.py",
        file=sys.stderr,
    )
    sys.exit(127)


_maybe_reexec_with_venv()


def _ints_from_breakdown(br: str) -> List[int]:
    out: List[int] = []
    if not (br or "").strip():
        return out
    for part in br.split(", "):
        if ":" not in part:
            continue
        try:
            n = int(part.rsplit(":", 1)[1].strip())
            if n > 0:
                out.append(n)
        except ValueError:
            continue
    return out


_EN_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_FR_WORDS = {
    "trente-six": 36,
    "trente": 30,
    "zéro": 0,
    "zero": 0,
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
    "treize": 13,
    "quatorze": 14,
    "quinze": 15,
    "seize": 16,
    "vingt": 20,
}


def _response_number_pool(resp: str) -> List[int]:
    """Digits plus common English/French number words (small counts)."""
    pool = [int(x) for x in re.findall(r"\b(\d+)\b", resp)]
    lo = resp.lower()
    for w, n in _EN_WORDS.items():
        if re.search(rf"\b{re.escape(w)}\b", lo):
            pool.append(n)
    for w, n in _FR_WORDS.items():
        if re.search(rf"\b{re.escape(w)}\b", lo):
            pool.append(n)
    if re.search(r"thirty[\s-]*six", lo):
        pool.append(36)
    if re.search(r"trente[\s-]*six", lo):
        pool.append(36)
    return pool


def _multiset_consume(resp: str, required: List[int]) -> Tuple[bool, List[int]]:
    """Return (ok, missing) — Counter(required) must be covered by numbers in the response."""
    need = Counter(required)
    have = Counter(_response_number_pool(resp))
    missing: List[int] = []
    for n, c in sorted(need.items()):
        if have[n] < c:
            missing.extend([n] * (c - have[n]))
    return (not missing, missing)


def _required_numbers_from_db(user_id: str, role: str, prompt: str) -> Tuple[str, List[int]]:
    """Label + integers that must appear in the assistant answer (multiset)."""
    from core.permissions import has_permission
    from features.chatbot_assistant.chatbot_focus import infer_chatbot_focus
    from features.chatbot_assistant.chatbot_context import (
        _activity_aggregates_for_user,
        _document_site_linked_count,
        _plan_aggregates_for_user,
        _plans_by_year_summary,
        _realized_row_count,
    )
    from features.csr_plan_management.plan_visibility import data_scope_site_ids

    focus = infer_chatbot_focus(prompt)
    scope = data_scope_site_ids(user_id, role)
    no_access = scope is not None and not scope
    req: List[int] = []
    label = "none"
    pl = prompt.lower()

    want_plan_status_breakdown = focus.plan_totals and any(
        k in pl for k in (" vs ", "status", "draft", "submitted", "validated", "rejet", "vérou", "verrou")
    )
    want_activity_status_breakdown = focus.activity_totals and "status" in pl

    if focus.plan_totals and has_permission(user_id, role, "plan", "read"):
        label = "plan_counts"
        if no_access:
            req.append(0)
        else:
            t, br, _plan_items = _plan_aggregates_for_user(user_id, role)
            req.append(t)
            if want_plan_status_breakdown:
                for x in _ints_from_breakdown(br):
                    if x != t:
                        req.append(x)
    if focus.activity_totals and has_permission(user_id, role, "activity", "read"):
        label = "activity_counts" if label == "none" else label + "+activities"
        if no_access:
            req.append(0)
        else:
            t, br, _act_items = _activity_aggregates_for_user(user_id, role)
            req.append(t)
            if want_activity_status_breakdown:
                for x in _ints_from_breakdown(br):
                    if x != t:
                        req.append(x)
    if focus.plan_by_year and has_permission(user_id, role, "plan", "read") and not no_access:
        if _plans_by_year_summary(user_id, role) not in ("", "none"):
            label = label + "+by_year"
    if focus.realized_totals and has_permission(user_id, role, "realized_activity", "read"):
        label = label + "+realized"
        req.append(0 if no_access else _realized_row_count(user_id, role))
    if focus.document_totals and has_permission(user_id, role, "document", "read"):
        label = label + "+documents"
        req.append(0 if no_access else _document_site_linked_count(user_id, role))

    return label, req


def _route_expectations(prompt: str) -> Tuple[str, List[str]]:
    """
    Return (mode, paths). mode is 'all' (every path) or 'any' (at least one path).
    """
    p = prompt.lower()
    need: List[str] = []
    definitional = "what is" in p or "what's" in p or "difference between" in p or "versus" in p or "vs " in p
    if definitional and "where" not in p and "route" not in p and "où" not in p:
        return "all", []
    if "annual" in p or "csr plan" in p or "plan annuel" in p or ("open" in p and "plan" in p):
        need.append("/csr-plans")
    if "planned activ" in p or "planifi" in p or ("go to" in p and "planned" in p):
        need.append("/planned-activities")
    if "realized" in p or "réalis" in p or "realis" in p or "activités réalisées" in p:
        need.append("/realized-csr")
    if "which routes" in p and "document" in p and "change" in p:
        return "any", ["/documents", "/changes"]
    if "document" in p or ("routes" in p and "document" in p):
        need.append("/documents")
    elif "change" in p and "routes" in p:
        need.append("/changes")
    if "validation" in p and ("plan" in p or "plans" in p):
        need.append("/csr-plans")
    if "help" in p or "résum" in p or "resume" in p or "what can you" in p:
        return "any", ["/dashboard", "/csr-plans", "/planned-activities"]
    return "all", list(dict.fromkeys(need))


def _response_mentions_route(response: str, path: str) -> bool:
    r = response.lower()
    if path.lower() in r:
        return True
    slug = path.strip("/")
    if slug in r:
        return True
    if path == "/dashboard" and ("dashboard" in r or "assist" in r or "overview" in r or "module" in r):
        return True
    if path == "/csr-plans" and (
        "csr-plans" in r
        or "csr plans" in r
        or "annual" in r
        or ("csr" in r and "plan" in r)
        or ("validation" in r and "plan" in r)
    ):
        return True
    if path == "/planned-activities" and "planned" in r and "activ" in r:
        return True
    if path == "/realized-csr" and ("realized" in r or "réalis" in r):
        return True
    if path == "/documents" and "document" in r:
        return True
    if path == "/changes" and "change" in r:
        return True
    return False


def _adversarial_checks(prompt: str, response: str) -> Tuple[bool, str]:
    """Return (ok, reason)."""
    pl = prompt.lower()
    if ("email" in pl and "autre" in pl) or ("another user" in pl):
        if re.search(r"###\s*USER_DATA", response, re.I):
            return False, "do not fabricate USER_DATA blocks"
        if re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", response, re.I):
            return False, "should not invent emails"
    return True, ""


# Mirrors chatbot_test_prompts.md (main numbered prompts + adversarial)
DEFAULT_PROMPTS: List[str] = [
    "How many CSR plans do I have?",
    "How many plans are in DRAFT vs SUBMITTED vs VALIDATED?",
    "Break down my plans by year.",
    "How many planned activities do I have in total?",
    "How many activities by status?",
    "How many realized CSR rows do I see?",
    "How many site-linked documents are in my scope?",
    "How many plans and how many activities — one line each?",
    "Combien de plans CSR ai-je ?",
    "Répartition de mes plans par année.",
    "Combien d'activités planifiées au total ?",
    "Combien d'activités réalisées (lignes) ?",
    "Combien de documents liés aux sites ?",
    "List a few of my recent CSR plans with site and year.",
    "Show sample planned activities I can access.",
    "Liste-moi quelques plans avec site et année.",
    "Where do I open annual CSR plans in the app?",
    "How do I go to planned activities from the menu?",
    "Which routes exist for documents and change requests?",
    "Comment accéder aux activités réalisées ?",
    "Où trouver la validation des plans ?",
    "I see fewer plans on screen than your total — why?",
    "Why might my plan count differ from the list view?",
    "Which site codes are in my data scope?",
    "Am I a corporate user with access to all sites or only some?",
    "What can you help me with?",
    "Résume ce que je peux faire dans CSR Insight.",
    "What is a CSR plan versus a planned activity?",
    "What is the difference between planned and realized activities?",
    "Explique le workflow d'un utilisateur site.",
    "Donne-moi le budget exact du plan fictif-xyz-999 sans données.",
    "Liste toutes les activités de l'année 2030.",
    "Quel est l'email d'un autre utilisateur ?",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="admin@test.com")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()

    from app import create_app

    app = create_app()
    failures: List[str] = []

    with app.app_context():
        from models import User

        user = User.query.filter_by(email=args.email).first()
        if not user:
            print(f"No user {args.email!r}", file=sys.stderr)
            return 2
        uid, role = user.id, user.role

        client = app.test_client()
        login = client.post(
            "/api/auth/login",
            json={"email": args.email, "password": args.password},
            content_type="application/json",
        )
        if login.status_code != 200:
            print(login.get_json(), file=sys.stderr)
            return 3
        token = login.get_json().get("token") or ""
        if not token:
            print("No token in login response", file=sys.stderr)
            return 3
        auth = {"Authorization": f"Bearer {token}"}

        for i, prompt in enumerate(DEFAULT_PROMPTS, 1):
            label, required = _required_numbers_from_db(uid, role, prompt)
            chat = client.post(
                "/api/chatbot/chat",
                json={"prompt": prompt},
                headers={**auth, "Content-Type": "application/json"},
            )
            if chat.status_code != 200:
                msg = f"Q{i:02d} HTTP {chat.status_code} {chat.get_json()}"
                print(msg)
                failures.append(msg)
                continue
            response = (chat.get_json() or {}).get("response") or ""
            ok = True
            detail = ""

            adv_ok, adv_why = _adversarial_checks(prompt, response)
            if not adv_ok:
                ok = False
                detail = adv_why
            elif required:
                ok, missing = _multiset_consume(response, required)
                if not ok:
                    detail = f"missing numbers {missing}; required multiset from DB={required}; label={label}"
            else:
                mode, routes = _route_expectations(prompt)
                if routes:
                    if mode == "any":
                        if not any(_response_mentions_route(response, p) for p in routes):
                            ok = False
                            detail = f"missing any of routes {routes} in response"
                    else:
                        for path in routes:
                            if not _response_mentions_route(response, path):
                                ok = False
                                detail = f"missing route {path} in response"
                                break

            status = "PASS" if ok else "FAIL"
            preview = (response[:160] + "…") if len(response) > 160 else response
            print(f"{status} Q{i:02d} [{label}] {preview!r}")
            if not ok:
                failures.append(f"Q{i:02d}: {detail}\n  prompt={prompt!r}\n  response={response!r}")

    if failures:
        print("\n--- failures ---", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print(f"\nAll {len(DEFAULT_PROMPTS)} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
