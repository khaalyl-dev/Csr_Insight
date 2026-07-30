# CSR Insight — Documentation

Professional documentation for the CSR Insight platform (COFICAB CSR Management System).

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture, tech stack, module structure |
| [API.md](./API.md) | REST API reference with endpoints, auth, and examples |
| [DATABASE.md](./DATABASE.md) | MySQL schema, tables, relationships, setup |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Local, staging, and production deployment guide |
| [index.html](./index.html) | Interactive HTML reference (API ↔ UI ↔ files ↔ screenshots) |
| [openapi.yaml](./openapi.yaml) | OpenAPI 3.0 spec (Swagger-compatible) |
| [swagger.html](./swagger.html) | Swagger UI viewer for the OpenAPI spec |

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

Open `docs/swagger.html` in a browser, or serve the docs folder:

```bash
cd docs && python3 -m http.server 8080
# → http://localhost:8080/swagger.html
```
