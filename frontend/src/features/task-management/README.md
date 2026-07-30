# Task Management

Aggregated actionable task inbox — embedded in MainLayout as the tasks bell.

---

## Component

| Widget | File | API |
|--------|------|-----|
| Tasks bell | `user-tasks-bell/user-tasks-bell.ts` | `GET /api/tasks`, Socket.IO `tasks_updated` |

---

## Task types (backend)

`APPROVE_PLAN`, `FIX_REJECTED_PLAN`, `EDIT_PLAN_DRAFT`, `EDIT_UNLOCKED_PLAN`, `RESUBMIT_ACTIVITY`, `EDIT_UNLOCKED_ACTIVITY`, `REVIEW_PENDING_CHANGES`

---

## Structure

```
task-management/
├── user-tasks-bell/
└── api/tasks-api.ts
```

Backend: `backend/features/task_management/tasks_routes.py`
