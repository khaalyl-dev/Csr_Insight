# Notification Management

In-app notifications with real-time delivery via Socket.IO.

---

## Components (not routed — embedded in MainLayout)

| Component | File | API |
|-----------|------|-----|
| Notification bell | `notification-bell/notification-bell.ts` | `GET /api/notifications`, Socket.IO `notification` |

User notification preferences are edited on `/account/profile`.

---

## Structure

```
notification-management/
├── notification-bell/
├── api/notifications-api.ts
└── models/
```

---

## Implemented

- [x] Notifications API — list, unread count, mark read, mark all read
- [x] Notification bell with unread badge
- [x] Real-time push via Socket.IO (`notification-socket.service.ts`)
- [x] Profile notification preferences (`users.notify_*` columns)

---

## Roadmap

- [ ] Email delivery for critical notifications
- [ ] Per-site notification settings UI
