# Backend (Flask) — CSR Insight

Flask REST API for the CSR Insight platform. Manages CSR plans, activities, validations, documents, notifications, and real-time events.

---

## Structure

```
backend/
├── app.py              # Entry point — factory, CORS, blueprints, Socket.IO
├── config.py           # Configuration (DB, SECRET_KEY, MEDIA_FOLDER, Ollama/RAG)
├── init_db.py          # Fresh DB setup — tables, categories, users, sites
├── requirements.txt    # Python dependencies
├── core/               # Shared layer (db, JWT, permissions, schema patches)
├── models/             # 22 SQLAlchemy models
├── features/           # Flask blueprints (domain modules)
├── rag_corpus/         # Chatbot knowledge base (markdown)
├── data/chroma/        # ChromaDB vector index (default)
├── tests/
└── docs/               # Chatbot architecture notes
```

Full API reference: [`../docs/API.md`](../docs/API.md) · Database: [`../Database/README.md`](../Database/README.md)

---

## Main files

| File | Purpose |
|------|---------|
| **app.py** | Creates Flask app, loads config, `db.create_all()` + schema patches, registers blueprints, runs Socket.IO on port 5001. |
| **config.py** | Reads `.env`: `DB_*`, `SECRET_KEY`, `MEDIA_FOLDER`, `FRONTEND_ORIGINS`, optional `OLLAMA_*` / `RAG_*`. |
| **init_db.py** | Creates tables and seed data. Run once for a fresh database. |
| **core/schema_patches.py** | Additive MySQL patches for existing databases on startup. |

---

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Python 3.10+** required. `requirements.txt` uses **mysql-connector-python 9.x** for ChromaDB (RAG) compatibility.

Create `.env` at `backend/` root (see `.env.example`):

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=csr_db
SECRET_KEY=change-me-in-production
```

Initialize database:

```bash
python3 init_db.py
```

Start server:

```bash
python3 app.py
```

→ `http://localhost:5001` · Health: `GET /api/health`

### Optional — Chatbot (Ollama)

1. Install and run Ollama: `ollama serve`
2. Pull a model: `ollama pull phi3:mini`
3. Set `OLLAMA_MODEL=phi3:mini` in `.env`

---

## Test accounts

| Email | Password | Role |
|-------|----------|------|
| user@test.com | password123 | Site |
| admin@test.com | admin123 | Corporate |
| john@example.com | john123 | Site |

---

## Blueprint modules

| Prefix | Module | Purpose |
|--------|--------|---------|
| `/api/auth`, `/api/users` | user_management | Auth, profile, user CRUD |
| `/api/sites`, `/api/categories` | site_management | Sites, categories |
| `/api/csr-plans` | csr_plan_management | Plans + Excel import |
| `/api/csr-activities` | planned_activity_management | Planned activities |
| `/api/realized-csr` | realized_activity_management | Realization reports |
| `/api/change-requests` | change_request_management | Unlock requests |
| `/api/documents` | file_management | File upload/download |
| `/api/audit` | audit_history_management | Audit trail |
| `/api/notifications` | notification_management | Notifications + Socket.IO |
| `/api/tasks` | task_management | Aggregated task inbox |
| `/api/dashboard` | dashboard_analytics | KPIs (legacy — Power BI used in frontend) |
| `/api/chatbot` | chatbot_assistant | AI assistant (Ollama + RAG) |
| `/api/health` | health | Health check |

**Stubs (registered, no routes yet):** `/api/validations`, `/api/powerbi`, `/api/external-partners`

---

## Authentication

All `/api/*` routes except `POST /api/auth/login` and `GET /api/health` require:

```
Authorization: Bearer <jwt_token>
```

---

## Production

```bash
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5001 app:app
```

See [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for full deployment guide.
