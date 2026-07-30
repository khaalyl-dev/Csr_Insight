# Core

Cross-cutting Angular services, guards, interceptors, and utilities.

---

## Structure

```
core/
├── guards/auth.guard.ts       # authGuard, roleGuard, permissionGuard, validatorLevelGuard
├── interceptors/
│   ├── jwt.interceptor.ts     # Adds Bearer token; 401 → logout
│   └── error-toast.interceptor.ts
├── services/
│   ├── auth-store.ts          # JWT + user state (localStorage/sessionStorage)
│   ├── auth.service.ts        # Login/logout orchestration
│   ├── notification-socket.service.ts  # Socket.IO real-time
│   ├── i18n.service.ts        # Language switching (EN/FR)
│   ├── theme.service.ts       # Light/dark theme
│   └── breadcrumb.service.ts
└── utils/
```

Path alias: `@core/*` → `src/core/*`

---

## Implemented

- [x] **JWT interceptor** — `Authorization: Bearer` on all `/api/*` requests
- [x] **authGuard** — protects authenticated routes
- [x] **roleGuard** — corporate vs site access
- [x] **permissionGuard** — granular RBAC (`plan.read`, etc.)
- [x] **validatorLevelGuard** — multi-step validation workflows
- [x] **Session init** — `APP_INITIALIZER` calls `GET /api/auth/me`
- [x] **Socket.IO** — real-time notifications and task updates

---

## Roadmap

- [ ] **Session expiry warning** — notify user before JWT expires
- [ ] **Refresh token flow** — if backend adds token refresh
