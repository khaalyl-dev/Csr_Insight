# CSR Insight — Documentation

Professional documentation for the CSR Insight platform (COFICAB CSR Management System).

> Project overview: [`../README.md`](../README.md) · Database schema (FR): [`../Database/README.md`](../Database/README.md)

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture, tech stack, module structure |
| [API.md](./API.md) | REST API reference with endpoints, auth, and examples |
| [DATABASE.md](./DATABASE.md) | MySQL schema overview (English) |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Local development and self-hosted production |
| [index.html](./index.html) | Interactive reference (API ↔ UI ↔ files ↔ screenshots) |
| [openapi.yaml](./openapi.yaml) | OpenAPI 3.0 spec (Swagger-compatible) |
| [swagger.html](./swagger.html) | Swagger UI viewer |

## Quick Start

```bash
# Backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
python3 init_db.py && python3 app.py

# Frontend
cd frontend && npm ci && npm start
```

Open [http://localhost:4200](http://localhost:4200) — API at [http://localhost:5001/api/health](http://localhost:5001/api/health).

## View Swagger UI

```bash
cd docs && python3 -m http.server 8080
# → http://localhost:8080/swagger.html
# → http://localhost:8080/index.html
```

## Module READMEs

| Area | Path |
|------|------|
| Backend features | `backend/features/*/README.md` |
| Backend models | `backend/models/README.md` |
| Frontend features | `frontend/src/features/*/README.md` |
| Frontend core/shared | `frontend/src/core/README.md`, `frontend/src/shared/README.md` |
