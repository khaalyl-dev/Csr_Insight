# Architecture — CSR Insight

## Overview

CSR Insight is a full-stack web application for managing Corporate Social Responsibility (CSR) plans, activities, realization reports, validations, and analytics across multiple COFICAB manufacturing sites.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Browser (Angular SPA)                           │
│  Port 4200 (dev) │ Vercel (prod)                                        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP /api/*  +  WebSocket /socket.io
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Flask REST API + Socket.IO                           │
│  Port 5001 (dev) │ Render.com + Gunicorn (prod)                         │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ SQLAlchemy ORM
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         MySQL 8+ Database                               │
└─────────────────────────────────────────────────────────────────────────┘

External integrations:
  • Power BI (embedded dashboards via iframe)
  • Ollama + ChromaDB (local AI chatbot with RAG)
  • File storage (local filesystem — MEDIA_FOLDER)
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Frontend | Angular (standalone components) | 21.x |
| UI | Tailwind CSS, PrimeNG, Font Awesome, Chart.js | — |
| i18n | ngx-translate (EN/FR) | — |
| Real-time | socket.io-client | 4.8 |
| Backend | Flask | 3.0 |
| ORM | Flask-SQLAlchemy | 3.1 |
| Database | MySQL | 8+ |
| Auth | JWT (PyJWT) + bcrypt | — |
| Real-time (server) | Flask-SocketIO | 5.4 |
| AI Chatbot | Ollama + ChromaDB RAG | Optional |
| Production server | Gunicorn + GeventWebSocketWorker | — |
| Frontend hosting | Vercel | — |
| Backend hosting | Render.com | — |

---

## Repository Structure

```
Csr_Insight/
├── backend/                    # Flask REST API
│   ├── app.py                  # Application factory, blueprint registration
│   ├── config.py               # Environment-based configuration
│   ├── init_db.py              # Database initialization + seed data
│   ├── requirements.txt
│   ├── render.yaml             # Render.com deployment manifest
│   ├── core/                   # Shared: db, JWT, permissions, schema patches
│   ├── models/                 # 22 SQLAlchemy models
│   ├── features/               # 17 Flask blueprints (domain modules)
│   ├── rag_corpus/             # Chatbot knowledge base (markdown)
│   ├── data/chroma/            # ChromaDB vector index
│   └── tests/
│
├── frontend/                   # Angular SPA
│   ├── src/
│   │   ├── app.routes.ts       # All route definitions
│   │   ├── app.config.ts       # DI providers, interceptors
│   │   ├── core/               # Guards, interceptors, global services
│   │   ├── features/           # Domain screens + *-api.ts HTTP clients
│   │   ├── shared/             # Layout, sidebar, reusable widgets
│   │   └── media/              # Uploaded files (default MEDIA_FOLDER)
│   ├── public/i18n/            # Translation files (en.json, fr.json)
│   ├── proxy.conf.json         # Dev proxy → localhost:5001
│   └── vercel.json             # Production API rewrites
│
├── Database/                   # Schema documentation (DBML, column reference)
├── screenshot/                 # UI screenshots for documentation
└── docs/                       # This documentation set
```

---

## Backend Architecture

### Blueprint Modules

Each feature is a Flask **Blueprint** under `backend/features/`:

| Blueprint | URL Prefix | Purpose |
|-----------|------------|---------|
| `health_bp` | `/api` | Health check |
| `auth_bp` | `/api/auth` | Authentication, profile |
| `users_bp` | `/api/users` | User CRUD (corporate) |
| `sites_bp` | `/api/sites` | Site management |
| `categories_bp` | `/api/categories` | CSR activity categories |
| `csr_plans_bp` | `/api/csr-plans` | Annual CSR plans |
| `csr_import_bp` | `/api/csr-plans` | Excel import |
| `planned_csr_bp` | `/api/csr-activities` | Planned activities |
| `realized_csr_bp` | `/api/realized-csr` | Realization reports |
| `change_requests_bp` | `/api/change-requests` | Unlock/modification requests |
| `documents_bp` | `/api/documents` | File upload & metadata |
| `audit_bp` | `/api/audit` | Audit trail (corporate) |
| `notifications_bp` | `/api/notifications` | User notifications |
| `tasks_bp` | `/api/tasks` | Aggregated task inbox |
| `dashboard_bp` | `/api/dashboard` | KPIs & analytics |
| `chatbot_bp` | `/api/chatbot` | AI assistant |
| `validations_bp` | `/api/validations` | Stub (logic in plan/activity routes) |
| `powerbi_bp` | `/api/powerbi` | Stub (Power BI embedded in frontend) |
| `external_partners_bp` | `/api/external-partners` | Stub |

### Cross-Cutting Concerns

| Concern | Location | Description |
|---------|----------|-------------|
| Authentication | `core/jwt_utils.py` | `@token_required`, `@role_required` decorators |
| Permissions | `core/permissions.py` | RBAC matrix (`plan.read`, `activity.approve`, etc.) |
| Schema evolution | `core/schema_patches.py` | Additive MySQL patches on startup |
| Real-time | `notification_management/` | Socket.IO events for notifications & tasks |
| KPI computation | `kpi_management/kpi_service.py` | Activity/plan KPI aggregation |

### Request Flow

```
HTTP Request
    → CORS middleware
    → JWT verification (@token_required)
    → Role/permission check (@role_required / permission helpers)
    → Route handler (feature blueprint)
    → SQLAlchemy models / services
    → JSON response (+ optional Socket.IO emit)
```

---

## Frontend Architecture

### Layering

```
Routes (app.routes.ts)
    → Guards (auth, role, permission, validator level)
    → Page Components (features/*/)
    → API Services (*-api.ts)
    → HttpClient (+ JWT & error interceptors)
    → Backend /api/*
```

### Key Patterns

- **Standalone components only** — no NgModules except `TranslateModule.forRoot`
- **No environment files** — API base is always relative `/api`; dev proxy and Vercel rewrites handle routing
- **Feature-based folders** — each domain has components, models, and an API client
- **MainLayout shell** — sidebar, notification bell, tasks bell, chatbot widget

### Route Map (Summary)

| Route | Feature | Permission |
|-------|---------|------------|
| `/login` | Auth | Public |
| `/dashboard` | Power BI dashboards | Authenticated |
| `/csr-plans` | Annual plans | `plan.read` |
| `/planned-activities` | Planned activities | `activity.read` |
| `/realized-csr` | CSR reports | `activity.read` |
| `/documents` | Document library | `document.read` |
| `/changes/*` | Change requests | Various |
| `/sites`, `/categories` | Site admin | Corporate |
| `/admin/users` | User management | Corporate |
| `/admin/audit` | Audit log | Corporate |
| `/account/profile` | Profile settings | Authenticated |

See [index.html](./index.html) for the complete route → API → file mapping with screenshots.

---

## Security Model

### Roles

| Role | Scope |
|------|-------|
| `SITE_USER` | Access limited to assigned sites |
| `CORPORATE_USER` | Cross-site access; admin features |

### Authentication

- JWT bearer token in `Authorization` header
- Token stored in localStorage/sessionStorage (frontend)
- Session tracked in `user_sessions` table
- Logout revokes token via `revoked_tokens.txt`

### Authorization

- **Role guard** — corporate-only routes (sites, users, audit)
- **Permission guard** — granular RBAC keys per feature action
- **Validator level guard** — multi-step validation workflows (level_0–level_3)
- **Site scoping** — site users only see data for their assigned sites

---

## Data Flow — CSR Lifecycle

```
1. CREATE PLAN (DRAFT)
   Site user creates annual CSR plan for a site/year

2. ADD ACTIVITIES
   Planned activities with budget, objectives, partners

3. SUBMIT PLAN (SUBMITTED)
   Plan enters validation workflow (mode 101 or 111)

4. VALIDATE (VALIDATED)
   Corporate (and optionally site L1) approves plan

5. EXECUTE & REPORT
   Realized activities recorded; off-plan activities possible

6. SUBMIT REALIZATION REPORT (LOCKED)
   Plan closed as consolidated CSR report

7. CHANGE REQUESTS
   Unlock validated/locked entities for modification
```

---

## Real-Time Events (Socket.IO)

| Event | Direction | Purpose |
|-------|-----------|---------|
| `connect` | Client → Server | Authenticate with JWT, join `user_{id}` room |
| `notification` | Server → Client | New notification push |
| `tasks_updated` | Server → Client | Task inbox refresh |

---

## External Integrations

### Power BI

Dashboard routes (`/dashboard`, `/dashboard/corporate`, `/dashboard/site`) embed Power BI reports via iframe configuration in `frontend/src/features/dashboard-analytics/dashboard/power-bi.config.ts`. The backend `/api/dashboard/*` endpoints exist but are currently unused by the frontend.

### Chatbot (Ollama + RAG)

- Endpoint: `POST /api/chatbot/chat`
- Retrieves relevant docs from ChromaDB (`backend/rag_corpus/`)
- Attaches a role-filtered DB snapshot to the prompt
- Requires local Ollama server (`OLLAMA_BASE_URL`)

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| No Docker | Deployed via Render (backend) + Vercel (frontend) |
| No Alembic/Flyway | Schema via `db.create_all()` + manual patches |
| Relative API paths | Simplifies dev/prod switching via proxy/rewrites |
| File storage on disk | Simple deployment; `MEDIA_FOLDER` configurable |
| Feature blueprints | Clear domain boundaries, easy to extend |
