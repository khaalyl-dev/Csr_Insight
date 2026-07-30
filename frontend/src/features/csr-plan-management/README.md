# CSR Plan Management

Annual CSR plans per site/year — create, submit, validate, Excel import.

---

## Routes

| Route | Component | Permission |
|-------|-----------|------------|
| `/csr-plans` | `AnnualPlansComponent` | `plan.read` |
| `/csr-plans/:id` | `PlanDetailComponent` | `plan.read` |
| `/csr-plans/:id/edit` | `PlanEditComponent` | — |
| `/annual-plans/validation` | `PlanValidationComponent` | `plan.validate`, `activity.validate` |

---

## Structure

```
csr-plan-management/
├── annual-plans/              # List, bulk submit/delete, Excel import
├── plan-detail/               # Plan + activities + KPIs + actions
├── plan-edit/                 # Edit plan metadata
├── plan-validation/           # Corporate validation queue
├── plan-create-sidebar/       # Create plan (sidebar)
├── plan-edit-sidebar/         # Edit plan (sidebar)
├── api/csr-plans-api.ts       # HTTP client
└── models/
```

Planned activities live in **`planned-activity-management`**.

---

## API (`/api/csr-plans`)

`GET`, `POST`, `PATCH`, `DELETE`, `submit`, `approve`, `reject`, `bulk-submit`, `bulk-delete`, Excel import endpoints.

Full reference: [`../../../docs/API.md`](../../../docs/API.md)

---

## Implemented

- [x] CSR Plans API — full CRUD + workflow
- [x] Plan create/edit (sidebar + full page)
- [x] Plan detail with activities and validation actions
- [x] Excel import (preview, conflicts, validate, commit)
- [x] Bulk submit and delete
- [x] Plan validation page (corporate)

---

## Roadmap

- [ ] Export plan to Excel/PDF
