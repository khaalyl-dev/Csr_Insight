# Realized Activity Management

CSR realization reports — track actual budget, participants, impact, and objectives.

---

## Routes

| Route | Component | Permission |
|-------|-----------|------------|
| `/realized-csr` | `RealizedListComponent` | `realized_activity.read` |
| `/realized-csr/:id` | `RealizedDetailComponent` | — |
| `/realized-csr/:id/edit` | `RealizedEditComponent` | — |

---

## Structure

```
realized-activity-management/
├── realized-list/             # Plans with realization KPIs
├── realized-detail/           # Single realization view
├── realized-edit/             # Edit realization
├── realized-create-sidebar/   # Create realization (sidebar)
├── api/realized-csr-api.ts
├── api/categories-api.ts      # Re-export for forms
└── models/realized-csr.model.ts
```

Table: `realized_activity` · API prefix: `/api/realized-csr`

---

## Implemented

- [x] Realized CSR API — CRUD (`GET`, `POST`, `PUT`, `DELETE`)
- [x] Realized list (by plan with KPIs)
- [x] Realized detail and edit forms
- [x] Document attachments (via `file-management`)
- [x] Status management (DRAFT, IN_PROGRESS, COMPLETED, etc.)
- [x] Link to planned activity

---

## Roadmap

- [ ] Volunteer hours field (if required by business)
