# CSR Insight — local chatbot, RAG, and security architecture

This document maps the **advanced RAG chatbot** pattern (Angular + Flask + local Ollama + ChromaDB + permission-aware SQL context) to **this repository**. It aligns with a CSR/RSE assistant that stays **private**, **fast**, and **small-context** (e.g. phi3:mini on Apple Silicon).

## Stack (this project)

| Spec idea | CSR Insight implementation |
|-----------|----------------------------|
| Angular frontend | `frontend/` — widget posts to `/api/chatbot/chat` |
| Flask backend | `backend/app.py`, blueprints |
| Database | **MySQL** via SQLAlchemy (`config.get_db_url()`), not SQL Server |
| Local LLM | **Ollama** only; `OLLAMA_BASE_URL` restricted to localhost / private LAN in `chatbot_routes.py` |
| Vector RAG | **ChromaDB** persistent store under `backend/data/chroma/` (default), ingest from `backend/rag_corpus/` |
| Non-streaming | `stream: false` in `_ollama_chat` for stable latency |

## End-to-end workflow

```text
User message (Angular)
      ↓
JWT + role (token_required)
      ↓
infer_chatbot_focus(prompt)     ← context compression: which DB slices matter
      ↓
build_chatbot_system_context()  ← permission-checked SQL aggregates / samples
      ↓
query_rag_block()             ← Chroma semantic retrieval (optional)
      ↓
build_chatbot_prompt_enrichment() ← short bracketed exact figures (counts)
      ↓
system = instructions + RAG + USER_DATA
      ↓
Ollama /api/generate (prompt + system, num_predict, optional num_ctx, temperature)
      ↓
JSON response → Angular
```

## Code layout (vs a generic `chatbot/` package)

| Role | Location |
|------|----------|
| HTTP API | `features/chatbot_assistant/chatbot_routes.py` |
| Focus / compression | `features/chatbot_assistant/chatbot_focus.py` |
| USER_DATA + enrichment + system copy | `features/chatbot_assistant/chatbot_context.py` |
| Chroma query | `features/chatbot_assistant/rag_store.py` |
| Corpus ingest CLI | `features/chatbot_assistant/rag_ingest.py` |
| QA script | `features/chatbot_assistant/verify_chatbot_prompts.py` |
| Markdown corpus | `backend/rag_corpus/*.md` |
| Schema hint (tooling / docs) | `backend/metadata/database_schema_chatbot.json` |

## Role-based access and SQL

- **Site scope** and **plan visibility** use `data_scope_site_ids`, `csr_plans_visible_query`, and `has_permission` from `core.permissions` and CSR plan modules — **before** building any aggregate the model sees.
- The **model does not generate or execute SQL**. Flask/SQLAlchemy runs fixed queries; results are **serialized into natural language context**.
- Optional **site name resolution** (e.g. “Serbia”) narrows aggregates to one `sites.id` when unambiguous — still server-side only.

## RAG (ChromaDB)

- **Embeddings**: Chroma’s default embedding path for `query_texts` (ingest uses the same stack).
- **Audience metadata**: `rag_ingest` stores `audience: all | corporate | site`; `rag_store.query_rag_block` filters by role.
- **Chunking**: `RAG_CHUNK_MAX_CHARS` (default 600) in ingest; keep `RAG_TOP_K=4` for RAM/latency.
- **Conflicts**: System text states **USER_DATA wins** over retrieved docs for numbers and scope.

## Recommended environment (local, low RAM)

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=phi3:mini
OLLAMA_NUM_PREDICT=280
OLLAMA_TEMPERATURE=0.2

RAG_ENABLED=true
RAG_TOP_K=4
```

After editing `rag_corpus/`, re-run:

`PYTHONPATH=. .venv/bin/python3 -m features.chatbot_assistant.rag_ingest`

## Security rules (must remain in Flask)

The chatbot must **not**:

- call cloud LLM APIs for this flow;
- expose passwords or secrets;
- return data outside the user’s **site + permission** envelope;
- invent **USER_DATA** blocks or emails.

## Future extensions (spec vs today)

- **Dedicated** `ollama_client.py` / `rag_prompt_builder.py`: optional refactor; logic is currently in `chatbot_routes.py` and `chatbot_context.py`.
- **SQL Server**: would require DSN and dialect changes; architecture (permission → SQL → RAG → prompt) stays the same.
