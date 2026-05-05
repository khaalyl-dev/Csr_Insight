"""Local RAG retrieval: ChromaDB persistent index over markdown corpus (see rag_ingest)."""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

COLLECTION_NAME = "csr_insight_docs"


def _audience_where_for_role(role: str) -> Dict[str, Any]:
    r = (role or "").strip().upper()
    if r in ("CORPORATE_USER", "CORPORATE"):
        return {"$or": [{"audience": "all"}, {"audience": "corporate"}]}
    return {"$or": [{"audience": "all"}, {"audience": "site"}]}


def query_rag_block(
    user_prompt: str,
    role: str,
    *,
    chroma_path: str,
    top_k: int,
    enabled: bool,
) -> str:
    """
    Return a short markdown block for the system prompt, or empty string if RAG is off,
    chromadb is missing, the index is empty, or retrieval fails.
    """
    if not enabled or not (user_prompt or "").strip():
        return ""
    try:
        import chromadb  # noqa: F401
    except Exception as e:
        # ImportError if missing; on some Python versions (e.g. 3.14) protobuf/chroma can raise TypeError.
        logger.debug("chromadb not usable; RAG skipped: %s", e)
        return ""
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        coll = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        logger.debug("RAG collection unavailable (run rag_ingest): %s", e)
        return ""
    k = min(max(int(top_k or 4), 1), 12)
    try:
        res = coll.query(
            query_texts=[user_prompt.strip()],
            n_results=k,
            where=_audience_where_for_role(role),
        )
        docs = (res.get("documents") or [[]])[0]
        if not docs:
            return ""
        lines = [
            "### KNOWLEDGE_BASE (retrieved documentation — if facts conflict with USER_DATA, trust USER_DATA)"
        ]
        for i, d in enumerate(docs, 1):
            t = (d or "").strip()
            if t:
                lines.append(f"[{i}] {t}")
        return "\n".join(lines) + "\n"
    except Exception:
        logger.warning("RAG query failed", exc_info=True)
        return ""
