"""
Build / refresh the ChromaDB index from markdown files under rag_corpus/.

Run from the backend directory:
  python -m features.chatbot_assistant.rag_ingest

Optional: RAG_CORPUS_PATH, RAG_CHROMA_PATH, RAG_CHUNK_MAX_CHARS (default 600).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv

from .rag_store import COLLECTION_NAME

_BACKEND = Path(__file__).resolve().parents[2]


def _parse_frontmatter(raw: str) -> Tuple[str, str]:
    text = raw.lstrip("\ufeff")
    audience = "all"
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end].strip()
            for line in block.splitlines():
                if ":" in line:
                    key, val = line.split(":", 1)
                    if key.strip().lower() == "audience":
                        audience = val.strip().lower()[:32]
            text = text[end + 4 :].lstrip()
    if audience not in ("all", "corporate", "site"):
        audience = "all"
    return audience, text


def _chunk_text(text: str, max_chars: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in paras:
        join_len = len(buf) + len(p) + (2 if buf else 0)
        if join_len <= max_chars:
            buf = f"{buf}\n\n{p}".strip() if buf else p
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= max_chars:
                buf = p
            else:
                for i in range(0, len(p), max_chars):
                    chunks.append(p[i : i + max_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def _safe_id(prefix: str, idx: int) -> str:
    base = re.sub(r"[^a-zA-Z0-9_-]+", "_", prefix)[:80]
    return f"{base}_{idx}"


def ingest_corpus(chroma_path: str, corpus_path: str, chunk_max: int) -> int:
    import chromadb

    os.makedirs(chroma_path, exist_ok=True)
    root = Path(corpus_path)
    if not root.is_dir():
        raise SystemExit(f"Corpus directory not found: {corpus_path}")

    md_files = sorted(root.rglob("*.md"))
    if not md_files:
        raise SystemExit(f"No .md files under {corpus_path}")

    client = chromadb.PersistentClient(path=chroma_path)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    coll = client.get_or_create_collection(name=COLLECTION_NAME)

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[dict] = []
    n = 0
    for path in md_files:
        rel = path.relative_to(root).as_posix()
        raw = path.read_text(encoding="utf-8")
        audience, body = _parse_frontmatter(raw)
        for i, chunk in enumerate(_chunk_text(body, chunk_max)):
            ids.append(_safe_id(rel, i))
            documents.append(chunk)
            metadatas.append({"audience": audience, "source": rel})
            n += 1

    if not documents:
        raise SystemExit("No chunks produced from corpus")

    batch = 128
    for start in range(0, len(documents), batch):
        end = start + batch
        coll.add(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
    return n


def main() -> None:
    load_dotenv(_BACKEND / ".env")
    from config import get_rag_chroma_path, get_rag_corpus_path

    chroma_path = get_rag_chroma_path()
    corpus_path = get_rag_corpus_path()
    chunk_max = int(os.environ.get("RAG_CHUNK_MAX_CHARS", "600"))
    n = ingest_corpus(chroma_path, corpus_path, chunk_max)
    print(f"Ingested {n} chunks into {chroma_path} (collection {COLLECTION_NAME})")


if __name__ == "__main__":
    main()
