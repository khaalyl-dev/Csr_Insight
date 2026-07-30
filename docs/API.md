# API Reference — CSR Insight

Base URL: `http://localhost:5001`

All endpoints under `/api/*` require authentication unless noted otherwise.

```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```

---

## Table of Contents

1. [Authentication](#authentication)
2. [Health](#health)
3. [Users](#users)
4. [Sites & Categories](#sites--categories)
5. [CSR Plans](#csr-plans)
6. [Excel Import](#excel-import)
7. [Planned Activities](#planned-activities)
8. [Realized Activities](#realized-activities)
9. [Change Requests](#change-requests)
10. [Documents](#documents)
11. [Audit](#audit)
12. [Notifications](#notifications)
13. [Tasks](#tasks)
14. [Dashboard Analytics](#dashboard-analytics)
15. [Chatbot](#chatbot)
16. [Socket.IO (Real-Time)](#socketio-real-time)
17. [Error Responses](#error-responses)
18. [Status Codes & Enums](#status-codes--enums)

---

## Authentication

### POST `/api/auth/login`

Authenticate and receive a JWT token.

**Auth:** None

**Request:**
```json
{
  "email": "user@test.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "token": "eyJ...",
  "user": { "id": "...", "email": "...", "role": "SITE_USER", "first_name": "...", "last_name": "..." },
  "permissions": ["plan.read", "activity.read"],
  "expires_at": "2026-07-31T09:00:00Z"
}
```

**Purpose:** Entry point for all authenticated sessions.

---

### POST `/api/auth/logout`

Revoke the current JWT token.

**Auth:** Required

**Response (200):** `{ "message": "Logged out successfully" }`

---

### GET `/api/auth/me`

Validate current session; returns minimal user info.

**Auth:** Required

---

### GET `/api/auth/profile`

Full user profile including sites and notification preferences.

**Auth:** Required

---

### PUT `/api/auth/profile`

Update profile settings.

**Auth:** Required

**Request (partial):**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+33612345678",
  "language": "fr",
  "theme": "dark",
  "notifications": {
    "notify_csr_plan_validation": true,
    "notify_activity_validation": true
  }
}
```

---

### PUT `/api/auth/change-password`

**Auth:** Required

**Request:**
```json
{
  "current_password": "oldpass",
  "new_password": "newpass123"
}
```

---

### POST `/api/auth/profile-photo`

Upload profile avatar.

**Auth:** Required

**Content-Type:** `multipart/form-data`

**Form field:** `file` (image)

**Response:** `{ "avatar_url": "/api/documents/serve/profile_photos/..." }`

---

## Health

### GET `/api/health`

**Auth:** None

**Response:** `{ "status": "ok" }`

**Purpose:** Service health check for monitoring and load balancers.

---

## Users

> **Corporate only** — requires `CORPORATE_USER` role.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/users` | List all users |
| GET | `/api/users/{id}` | User detail with site assignments |
| POST | `/api/users` | Create user |
| PATCH | `/api/users/{id}` | Update user fields |
| POST | `/api/users/{id}/sites` | Assign/replace site access |
| POST | `/api/users/{id}/reset-password` | Generate one-time password |
| DELETE | `/api/users/{id}/sites/{site_id}` | Revoke site access |
| DELETE | `/api/users/{id}` | Disabled (returns 403) |

**Create user request:**
```json
{
  "email": "newuser@example.com",
  "password": "securepass",
  "first_name": "Jane",
  "last_name": "Smith",
  "role": "SITE_USER",
  "permissions": ["plan.read", "plan.create"],
  "is_corporate_global": false
}
```

**Assign sites request:**
```json
{
  "site_accesses": [
    { "site_id": "uuid", "grade": "level_1", "access_types": ["read", "write"] }
  ]
}
```

---

## Sites & Categories

### Sites

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/sites` | List sites (`?active=true`) |
| POST | `/api/sites` | Create site |
| GET | `/api/sites/{id}` | Site detail |
| PUT | `/api/sites/{id}` | Update site |
| PATCH | `/api/sites/{id}/status` | Toggle active status (corporate) |
| GET | `/api/sites/{id}/users` | List users assigned to site |
| POST | `/api/sites/{id}/users` | Assign user to site |
| PUT | `/api/sites/{id}/users/{user_id}` | Update user grade |
| DELETE | `/api/sites/{id}/users/{user_id}` | Revoke user from site |

**Create site:**
```json
{
  "name": "COFICAB Serbia",
  "code": "COFSRB",
  "region": "EE",
  "country": "Serbia",
  "location": "Novi Sad",
  "description": "Manufacturing plant"
}
```

### Categories

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/categories` | List CSR categories |
| POST | `/api/categories` | Create category (idempotent) |
| GET | `/api/categories/{id}/related-activities` | Activities using category |
| DELETE | `/api/categories/{id}` | Delete with optional activity reassignment |

---

## CSR Plans

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/csr-plans` | List plans (filtered by site, year, status) |
| POST | `/api/csr-plans` | Create DRAFT plan |
| GET | `/api/csr-plans/{id}` | Plan detail with activities and KPIs |
| PATCH | `/api/csr-plans/{id}` | Update editable plan |
| PATCH | `/api/csr-plans/{id}/submit` | Submit for validation |
| PATCH | `/api/csr-plans/{id}/submit-realization-report` | Close plan (→ LOCKED) |
| PATCH | `/api/csr-plans/{id}/approve` | Approve plan |
| PATCH | `/api/csr-plans/{id}/reject` | Reject with comment |
| DELETE | `/api/csr-plans/{id}` | Delete editable plan |
| POST | `/api/csr-plans/bulk-submit` | Bulk submit |
| POST | `/api/csr-plans/bulk-delete` | Bulk delete |

**Query parameters (GET list):**
- `site_id` — filter by site
- `year` — filter by year
- `status` — DRAFT, SUBMITTED, VALIDATED, REJECTED, LOCKED
- `plan_type` — `planned` or `realized`
- `include_plan_kpis` — `1` to include KPI summary

**Create plan:**
```json
{
  "site_id": "uuid",
  "year": 2026,
  "validation_mode": "111",
  "total_hc": 500
}
```

**Reject plan:**
```json
{
  "comment": "Budget exceeds allocation",
  "activity_ids": ["uuid1", "uuid2"]
}
```

**Permissions:** `plan.read`, `plan.create`, `plan.update`, `plan.delete`, `plan.submit`, `plan.approve`, `plan.reject`

---

## Excel Import

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/csr-plans/import-excel-preview` | Parse Excel, preview rows (no DB write) |
| POST | `/api/csr-plans/import-excel-check-conflicts` | Check activity number conflicts |
| POST | `/api/csr-plans/import-validate-rows` | Re-validate edited rows |
| POST | `/api/csr-plans/import-excel` | Commit import to database |

**Preview/Import:** `multipart/form-data` with `file`, `site_id` (optional), `year` (required)

**Check conflicts / validate rows:**
```json
{
  "rows": [ { "activity_number": "A001", "title": "..." } ],
  "site_id": "uuid",
  "year": 2026
}
```

---

## Planned Activities

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/csr-activities` | List activities |
| POST | `/api/csr-activities` | Create activity |
| GET | `/api/csr-activities/{id}` | Activity detail |
| PUT | `/api/csr-activities/{id}` | Update activity |
| DELETE | `/api/csr-activities/{id}` | Delete activity |
| POST | `/api/csr-activities/plan-realized-draft` | Draft activity + realization (past-year) |
| POST | `/api/csr-activities/off-plan-realization` | Create off-plan activity |
| PATCH | `/api/csr-activities/{id}/submit-modification-review` | Submit modification for review |
| PATCH | `/api/csr-activities/{id}/approve` | Approve off-plan/modification |
| PATCH | `/api/csr-activities/{id}/reject` | Reject off-plan/modification |
| PATCH | `/api/csr-activities/{id}/resubmit-off-plan` | Resubmit rejected off-plan |

**Query (GET list):**
- `plan_id`, `year`, `exclude_realized=1`

**Create activity (key fields):**
```json
{
  "plan_id": "uuid",
  "title": "Tree Planting Initiative",
  "category_id": "uuid",
  "activity_number": "ENV-001",
  "planned_budget": 15000,
  "collaboration_nature": "PARTNERSHIP",
  "organization": "PARTNERSHIP",
  "contract_type": "ONE_SHOT",
  "planned_objectives": ["Plant 500 trees", "Engage 50 employees"],
  "external_partners": ["NGO Name"],
  "draft": false
}
```

---

## Realized Activities

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/realized-csr` | List realized records |
| GET | `/api/realized-csr/{id}` | Realization detail |
| POST | `/api/realized-csr` | Create realization |
| PUT | `/api/realized-csr/{id}` | Update realization |
| DELETE | `/api/realized-csr/{id}` | Delete realization |

**Query:** `?activity_id=uuid`

**Create realization:**
```json
{
  "activity_id": "uuid",
  "realized_budget": 14500,
  "employees_actual": 48,
  "realization_date": "2026-05-15",
  "completed_objectives": ["Planted 520 trees", "Engaged 48 employees"],
  "beneficiaries_count": 200,
  "comments": "Exceeded target"
}
```

---

## Change Requests

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/change-requests` | Request unlock on plan/activity |
| GET | `/api/change-requests` | List change requests |
| GET | `/api/change-requests/{id}` | Detail with documents |
| POST | `/api/change-requests/{id}/approve` | Approve unlock |
| POST | `/api/change-requests/{id}/reject` | Reject unlock |

**Create:**
```json
{
  "plan_id": "uuid",
  "reason": "Budget adjustment needed",
  "requested_duration": 7,
  "validation_mode": "111"
}
```

Use `activity_id` instead of `plan_id` for activity-level unlocks.

---

## Documents

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/documents` | List documents (`?entity_type&entity_id`) |
| POST | `/api/documents` | Create document record |
| POST | `/api/documents/upload` | Upload file + create record |
| GET | `/api/documents/pinned` | Pinned documents |
| GET | `/api/documents/download/{path}` | Download file |
| GET | `/api/documents/serve/{path}` | Serve inline (images) |
| GET | `/api/documents/site/{site_id}` | Site documents |
| PUT | `/api/documents/{id}` | Update metadata |
| PATCH | `/api/documents/{id}/pin` | Toggle pin |
| DELETE | `/api/documents/{id}` | Delete file + record |

**Upload:** `multipart/form-data` — `file`, `site_id`, optional `change_request_id`, `entity_type`, `entity_id`

**Storage:** Files stored under `MEDIA_FOLDER` (default: `frontend/src/media/`).

---

## Audit

> **Corporate only**

### GET `/api/audit/logs`

**Query parameters:** `action`, `entity_type`, `site_id`, `user_id`, `date_from`, `date_to`, `limit`

**Purpose:** Filtered audit trail for compliance and troubleshooting.

---

## Notifications

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/notifications` | List user notifications |
| GET | `/api/notifications/unread-count` | Unread count |
| PATCH | `/api/notifications/{id}/read` | Mark one as read |
| PATCH | `/api/notifications/read-all` | Mark all as read |
| DELETE | `/api/notifications/{id}` | Delete notification |

---

## Tasks

### GET `/api/tasks`

Returns aggregated actionable tasks for the current user.

**Response:**
```json
{
  "tasks": [
    { "type": "APPROVE_PLAN", "plan_id": "...", "title": "...", "site_name": "..." }
  ],
  "count": 3
}
```

**Task types:** `APPROVE_PLAN`, `FIX_REJECTED_PLAN`, `EDIT_PLAN_DRAFT`, `EDIT_UNLOCKED_PLAN`, `RESUBMIT_ACTIVITY`, `EDIT_UNLOCKED_ACTIVITY`, `REVIEW_PENDING_CHANGES`

---

## Dashboard Analytics

Base: `/api/dashboard`

> **Note:** These endpoints are implemented but currently unused by the frontend (Power BI dashboards are embedded instead).

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/filter-options` | Years, sites, categories for filters |
| GET | `/site/summary` | Site summary KPIs |
| GET | `/site/activities-chart` | 6-month activity chart |
| GET | `/kpis` | Full KPI dashboard |
| GET | `/categories` | Activities by category |
| GET | `/monthly-timeline` | 12-month timeline |
| GET | `/site-performance` | Cross-site comparison |
| GET | `/top-activities` | Top 10 by participants |
| GET | `/notifications` | Dashboard alerts |

**Common query:** `?site_id=&year=&category_id=`

---

## Chatbot

### POST `/api/chatbot/chat`

AI assistant with RAG and role-filtered DB snapshot.

**Request:**
```json
{
  "prompt": "How many activities are pending validation?",
  "model": "phi3:mini"
}
```

**Response:**
```json
{
  "model": "phi3:mini",
  "response": "Based on your site data, there are 3 activities pending..."
}
```

**Requires:** Local Ollama server (`OLLAMA_BASE_URL`).

---

## Socket.IO (Real-Time)

Connect to `/socket.io` with JWT in `auth.token` or query `?token=`.

| Event | Direction | Purpose |
|-------|-----------|---------|
| `connect` | Client → Server | Join room `user_{user_id}` |
| `disconnect` | Client → Server | Cleanup |
| `notification` | Server → Client | Push new notification |
| `tasks_updated` | Server → Client | Refresh task inbox |

---

## Error Responses

Standard error format:

```json
{
  "error": "Human-readable message",
  "code": "OPTIONAL_ERROR_CODE"
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Bad request / validation error |
| 401 | Missing or invalid token |
| 403 | Insufficient permissions |
| 404 | Resource not found |
| 409 | Conflict (duplicate, invalid state transition) |
| 500 | Internal server error |

---

## Status Codes & Enums

### Plan Status
`DRAFT` → `SUBMITTED` → `VALIDATED` → `LOCKED` (or `REJECTED`)

### Activity Status
`DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `VALIDATED`, `SUBMITTED`, `REJECTED`

### Validation Mode
- `101` — Corporate validation only
- `111` — Site Level 1 → Corporate Level 2

### Roles
`SITE_USER`, `CORPORATE_USER`

---

## OpenAPI / Swagger

Machine-readable spec: [openapi.yaml](./openapi.yaml)

Interactive viewer: [swagger.html](./swagger.html)

Interactive UI ↔ API mapping: [index.html](./index.html)
