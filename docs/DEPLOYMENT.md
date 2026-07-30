# Deployment Guide — CSR Insight

This guide covers local development setup and generic production build steps.

---

## Architecture Summary

| Component | Technology |
|-----------|------------|
| Frontend (SPA) | Angular 21 |
| Backend (API) | Flask + Socket.IO |
| Database | MySQL 8+ |
| File storage | Local filesystem (`MEDIA_FOLDER`) |
| Real-time | Socket.IO (same backend process) |
| AI Chatbot | Ollama + ChromaDB (optional, local/private network) |

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | ≥ 20.19.0 | Frontend build |
| Python | ≥ 3.10 | Backend runtime |
| MySQL | ≥ 8.0 | Database |
| Git | Latest | Source control |
| Ollama | Latest (optional) | Chatbot |

---

## Local Development

### 1. Clone Repository

```bash
git clone <repository-url> Csr_Insight
cd Csr_Insight
```

### 2. Database Setup

```bash
mysql -u root -p
```

```sql
CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'csr_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON csr_db.* TO 'csr_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=csr_user
DB_PASSWORD=your_password
DB_NAME=csr_db
SECRET_KEY=dev-secret-key-change-in-prod
```

Initialize database:

```bash
python3 init_db.py
```

Start backend:

```bash
python3 app.py
# → http://localhost:5001
# Health check: http://localhost:5001/api/health
```

### 4. Frontend Setup

```bash
cd frontend
npm ci
npm start
# → http://localhost:4200
```

The dev server proxies `/api` and `/socket.io` to `localhost:5001` via `proxy.conf.json`.

### 5. Optional — Chatbot (Ollama)

```bash
# Install Ollama: https://ollama.ai
ollama serve
ollama pull phi3:mini
```

Ensure `.env` has:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=phi3:mini
RAG_ENABLED=true
```

---

## Production Build (Self-Hosted)

Build artifacts locally or on your server. Configure your own reverse proxy (nginx, Apache, etc.) to serve the frontend and route `/api` and `/socket.io` to the backend.

### Backend

```bash
cd backend
pip install -r requirements.txt

# Development server (not for production load)
python3 app.py

# Production WSGI server (recommended)
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5001 app:app
```

Set production environment variables (see below). Run `init_db.py` once against the production database before going live.

### Frontend

```bash
cd frontend
npm ci
npm run build
# Output: dist/csr-management/browser/
```

Serve the built static files with your web server. Ensure `/api/*` and `/socket.io/*` are proxied to the Flask backend on port 5001 (or your chosen port).

Example nginx pattern:

```nginx
location / {
    root /path/to/dist/csr-management/browser;
    try_files $uri $uri/ /index.html;
}

location /api/ {
    proxy_pass http://127.0.0.1:5001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /socket.io/ {
    proxy_pass http://127.0.0.1:5001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

Add your frontend origin to backend `FRONTEND_ORIGINS` for CORS.

---

## Environment Variables Reference

### Required (Backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | MySQL hostname |
| `DB_PORT` | 3306 | MySQL port |
| `DB_USER` | root | MySQL username |
| `DB_PASSWORD` | (empty) | MySQL password |
| `DB_NAME` | csr_db | Database name |
| `SECRET_KEY` | change-me | JWT signing key — **must change in production** |

### Optional (Backend)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5001 | Server port |
| `MEDIA_FOLDER` | frontend/src/media | File upload directory |
| `FRONTEND_ORIGINS` | — | Extra CORS origins (comma-separated) |
| `ACCESS_TOKEN_EXPIRATION_HOURS` | 24 | JWT lifetime |
| `REVOKED_TOKENS_FILE` | revoked_tokens.txt | Logout token blacklist |
| `OLLAMA_BASE_URL` | http://127.0.0.1:11434 | Ollama server URL |
| `OLLAMA_MODEL` | phi3:mini | LLM model name |
| `OLLAMA_NUM_PREDICT` | 280 | Max response tokens |
| `OLLAMA_TEMPERATURE` | 0.2 | Sampling temperature |
| `RAG_ENABLED` | true | Enable ChromaDB retrieval |
| `RAG_TOP_K` | 4 | RAG chunks retrieved |
| `RAG_CHROMA_PATH` | backend/data/chroma | ChromaDB directory |
| `RAG_CORPUS_PATH` | backend/rag_corpus | Knowledge base markdown |

---

## File Storage

Uploaded files are stored on the backend filesystem:

| Subfolder | Content |
|-----------|---------|
| `change_requests/` | Change request attachments |
| `activity_photos/` | Activity photos/documents |
| `profile_photos/` | User avatars |

**Default path:** `frontend/src/media/` (relative to project root)

**Production:** Set `MEDIA_FOLDER` to a persistent, writable directory on the server.

> **Important:** File storage is not in the database. Back up the media folder alongside the database.

---

## Health Checks & Monitoring

| Check | URL | Expected |
|-------|-----|----------|
| Backend health | `GET /api/health` | `{ "status": "ok" }` |
| Frontend | Load SPA root | Login page renders |
| Database | Backend logs on startup | No connection errors |
| WebSocket | Browser DevTools → Network → WS | Socket.IO connected after login |

---

## Build Commands Reference

```bash
# Backend — production WSGI
cd backend
pip install -r requirements.txt
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5001 app:app

# Frontend — production build
cd frontend
npm ci
npm run build

# Frontend — tests
npm test
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] MySQL database provisioned and accessible from the backend server
- [ ] `SECRET_KEY` set to a strong random value
- [ ] `FRONTEND_ORIGINS` includes production frontend URL(s)
- [ ] Reverse proxy configured for `/api` and `/socket.io`
- [ ] `init_db.py` run once on production DB
- [ ] Test account passwords changed or removed in production

### Post-Deployment

- [ ] `GET /api/health` returns 200
- [ ] Login works from production frontend
- [ ] CORS: no browser console errors on API calls
- [ ] Socket.IO connects (notification bell works)
- [ ] File upload/download works
- [ ] Power BI dashboards load (iframe config)
- [ ] Audit log records actions

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| 401 on all API calls | Expired/invalid JWT | Re-login; check SECRET_KEY consistency |
| CORS errors | Missing FRONTEND_ORIGINS | Add frontend URL to backend env |
| DB connection refused | Wrong DB_HOST or firewall | Verify MySQL allows backend server IP |
| WebSocket fails | Proxy not configured | Enable WebSocket upgrade on reverse proxy |
| File upload 500 | MEDIA_FOLDER not writable | Set writable path on server |
| Chatbot 503 | Ollama not running | Start Ollama or disable RAG |
| Blank dashboard | Power BI config | Update `power-bi.config.ts` embed URLs |

---

## Security Hardening (Production)

1. Change all default test passwords
2. Use strong `SECRET_KEY` (32+ random bytes)
3. Restrict MySQL access to the backend server
4. Enable HTTPS on your reverse proxy
5. Set `FRONTEND_ORIGINS` explicitly — do not rely on defaults
6. Review corporate user permissions regularly
7. Back up database and media folder on schedule
8. Keep `requirements.txt` and `package.json` dependencies updated

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) — System design
- [API.md](./API.md) — Endpoint reference
- [DATABASE.md](./DATABASE.md) — Schema details
- [index.html](./index.html) — Interactive UI ↔ API mapping
