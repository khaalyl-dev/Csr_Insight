# Planned Activity Management

Planned CSR activities — list, detail, create, edit, off-plan workflow, and realization capture.

Aligns with backend `planned_activity_management` and `/api/csr-activities`.  
MySQL table: `planned_activity` (model `CsrActivity`).

---

## Routes

| Route | Component | Permission |
|-------|-----------|------------|
| `/planned-activities` | `PlannedActivitiesListComponent` | `activity.read` |
| `/planned-activity/:id` | `PlannedActivityDetailComponent` | `activity.read` |
| `/planned-activity/:id/edit` | `PlannedActivityEditComponent` | — |

Sidebars are embedded from `csr-plan-management/plan-detail`.

---

## Structure

| Path | Purpose |
|------|---------|
| `api/csr-activities-api.ts` | HTTP client — CRUD, off-plan, modification review |
| `models/csr-activity.model.ts` | `CsrActivity` TypeScript type |
| `planned-activities-list/` | Global activities list |
| `planned-activity-detail/` | Single activity view |
| `planned-activity-edit/` | Edit form |
| `planned-activity-create-sidebar/` | Add activity to a plan |
| `realized-activity-sidebar/` | Capture realization (past-year draft flow) |

---

## Implemented

- [x] Full CRUD via `/api/csr-activities`
- [x] Off-plan realization (`POST /off-plan-realization`)
- [x] Modification review workflow (approve/reject/resubmit)
- [x] Objectives and document attachments
- [x] Integration with plan detail page

---

## Roadmap

- [ ] Activity KPI summary widget on detail page
