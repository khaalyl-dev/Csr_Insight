# CSR Insight

Corporate Social Responsibility (CSR) management platform for COFICAB manufacturing sites — annual plans, planned activities, realization reports, validations, documents, and Power BI analytics.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Angular 21, Tailwind CSS, PrimeNG, ngx-translate (EN/FR) |
| Backend | Flask 3, Flask-SQLAlchemy, JWT, Socket.IO |
| Database | MySQL 8+ |
| AI Chatbot | Ollama + ChromaDB RAG (optional) |

## Project Structure

```
Csr_Insight/
├── backend/          # Flask REST API (port 5001)
├── frontend/         # Angular SPA (port 4200)
├── Database/         # MySQL schema docs (DBML, column reference)
├── docs/             # API, architecture, deployment, Swagger
└── screenshot/       # UI screenshots for documentation
```

## Quick Start

### Prerequisites

- Python 3.10+, Node.js ≥ 20.19, MySQL 8+

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure DB_* and SECRET_KEY
python3 init_db.py
python3 app.py
```

→ API: http://localhost:5001/api/health

### Frontend

```bash
cd frontend
npm ci
ng serve
```

→ App: http://localhost:4200 (proxies `/api` to backend)

### Test Accounts

| Email | Password | Role |
|-------|----------|------|
| `user@test.com` | `password123` | Site User |
| `admin@test.com` | `admin123` | Corporate User |
| `john@example.com` | `john123` | Site User |

## Documentation

| Location | Content |
|----------|---------|
| [`docs/`](docs/README.md) | API reference, architecture, deployment, Swagger, interactive HTML |
| [`Database/`](Database/README.md) | MySQL schema, tables, migrations, Excel mapping |
| [`backend/README.md`](backend/README.md) | Backend setup and structure |
| [`backend/models/README.md`](backend/models/README.md) | SQLAlchemy models (22 tables) |

## Main Features

- **Annual CSR Plans** — create, submit, validate, Excel import
- **Planned Activities** — budget, objectives, off-plan workflow
- **CSR Reports** — realization tracking and consolidated reporting
- **Change Requests** — unlock validated/locked entities
- **Documents** — upload, download, pin by site/entity
- **User & Site Admin** — RBAC, site assignment, audit log
- **Dashboard** — Power BI embedded analytics
- **Chatbot** — AI assistant with role-filtered DB context (Ollama)
- **Real-time** — notifications and task inbox via Socket.IO

## License

Proprietary — COFICAB / internal use.
