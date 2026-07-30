# Frontend — CSR Insight

Angular 21 standalone SPA for CSR plan management, activities, reports, and analytics.

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Framework | Angular 21 (standalone components, signals) |
| Styling | Tailwind CSS 3.4, PrimeNG 21 |
| i18n | ngx-translate (EN/FR) — `public/i18n/` |
| Real-time | socket.io-client |
| Charts | Chart.js (legacy KPI widgets) |
| Build | `@angular/build:application` → `dist/csr-management/browser` |

Node.js **≥ 20.19.0** required.

---

## Setup

```bash
cd frontend
npm ci
ng serve
```

→ http://localhost:4200

With proxy (recommended): `ng serve --proxy-config proxy.conf.json` — proxies `/api` and `/socket.io` to `http://localhost:5001`.

Production build:

```bash
npm run build
```

Serve `dist/csr-management/browser/` behind a reverse proxy that routes `/api` and `/socket.io` to the Flask backend.

---

## Structure

```
frontend/src/
├── app.routes.ts          # All routes
├── app.config.ts          # Providers, interceptors, i18n
├── core/                  # Guards, interceptors, global services
├── features/              # Domain screens + *-api.ts clients
├── shared/                # Layout, sidebar, widgets
└── media/                 # Uploaded files (default MEDIA_FOLDER)
```

Path aliases: `@core/*`, `@shared/*`, `@features/*`

---

## Feature modules

| Feature | Route prefix | README |
|---------|--------------|--------|
| Dashboard | `/dashboard` | [dashboard-analytics](src/features/dashboard-analytics/README.md) |
| CSR Plans | `/csr-plans` | [csr-plan-management](src/features/csr-plan-management/README.md) |
| Planned Activities | `/planned-activities` | [planned-activity-management](src/features/planned-activity-management/README.md) |
| CSR Reports | `/realized-csr` | [realized-activity-management](src/features/realized-activity-management/README.md) |
| Documents | `/documents` | [file-management](src/features/file-management/README.md) |
| Change Requests | `/changes` | [change-request-management](src/features/change-request-management/README.md) |
| Sites & Categories | `/sites`, `/categories` | [site-management](src/features/site-management/README.md) |
| Users & Profile | `/admin/users`, `/account/profile` | [user-management](src/features/user-management/README.md) |
| Audit | `/admin/audit` | [audit-history-management](src/features/audit-history-management/README.md) |

---

## Documentation

- Full API ↔ UI mapping: [`../docs/index.html`](../docs/index.html)
- Architecture: [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)
