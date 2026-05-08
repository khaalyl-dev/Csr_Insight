# Testing Deployment (Vercel + Render + Railway MySQL)

## 1) Railway MySQL

Deploy the Railway MySQL template, then copy these variables from Railway:
- `MYSQLHOST`
- `MYSQLPORT`
- `MYSQLUSER`
- `MYSQLPASSWORD`
- `MYSQLDATABASE`

Use these as backend env vars on Render:
- `DB_HOST` = `MYSQLHOST`
- `DB_PORT` = `MYSQLPORT`
- `DB_USER` = `MYSQLUSER`
- `DB_PASSWORD` = `MYSQLPASSWORD`
- `DB_NAME` = `MYSQLDATABASE`

If Render cannot connect with Railway private host, use values from `MYSQL_PUBLIC_URL`
(public endpoint details) instead.

## 2) Flask backend on Render

This repo includes `backend/render.yaml`.

Steps:
1. Push code to GitHub.
2. In Render, create service from `render.yaml` (Blueprint) or create a Web Service and reuse:
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command:
     `gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:$PORT app:app`
3. Set env vars:
   - `SECRET_KEY` (strong random)
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - `FRONTEND_ORIGINS` = your Vercel URL(s), comma-separated
     (example: `https://myapp.vercel.app,https://myapp-git-main.vercel.app`)
   - Optional for files on Render disk:
     - `MEDIA_FOLDER=/var/data/media`
4. Deploy and verify:
   - `https://<your-render-app>.onrender.com/api/health`

## 3) Angular frontend on Vercel

This repo includes `frontend/vercel.json`.

Before deploying, edit these 2 lines in `frontend/vercel.json`:
- `YOUR_RENDER_BACKEND_URL` -> your actual Render service subdomain.

Then:
1. Import the repo into Vercel.
2. Set project root to `frontend`.
3. Deploy.

The frontend calls `/api/*` and `/socket.io/*`; Vercel rewrites proxy requests to Render.

## Notes

- If you change Render URL, update `frontend/vercel.json` rewrites and redeploy frontend.
- Railway service must allow external connections for Render to connect.
- Media/documents are currently stored on the backend filesystem; for long-term persistence on Render, use external object storage (S3/Cloudinary/etc.).
