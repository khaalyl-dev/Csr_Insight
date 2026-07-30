# Shared

Reusable layouts and UI components used across features.

---

## Structure

```
shared/
├── layouts/main-layout/       # Shell: sidebar, notification bell, tasks bell, chatbot
├── components/
│   ├── sidebar/               # Navigation (nav-config.ts)
│   ├── chatbot-widget/        # AI assistant widget
│   ├── button/
│   ├── spinner/
│   └── user-avatar-name/
```

Path alias: `@shared/*` → `src/shared/*`

---

## Implemented

- [x] **MainLayout** — authenticated app shell with router outlet
- [x] **Sidebar** — role/permission-based navigation
- [x] **Notification bell** — real-time via Socket.IO
- [x] **Tasks bell** — aggregated actionable tasks
- [x] **Chatbot widget** — `POST /api/chatbot/chat`
- [x] **Error toasts** — via `error-toast.interceptor.ts` (core)

---

## Roadmap

- [ ] **Reusable data table** — sort, pagination, filters
- [ ] **Confirmation dialog** — shared confirm-before-action component
