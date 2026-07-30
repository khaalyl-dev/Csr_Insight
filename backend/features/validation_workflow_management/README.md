# validation_workflow_management

Validation workflow for plans and activities.

> **Status: stub.** The blueprint is registered in `app.py` but `validations_routes.py` has no routes. Validation logic is implemented in:
> - `csr_plan_management/csr_plans_routes.py` — submit, approve, reject plans
> - `planned_activity_management/planned_csr_routes.py` — off-plan / modification approve/reject
> - `change_request_management/change_requests_routes.py` — unlock approval

Records are stored in the `validations` table via helpers in those modules.

---

## Files

| File | Purpose |
|------|---------|
| **validations_routes.py** | Blueprint `/api/validations` (stub). |
| **__init__.py** | Exports `validations_bp`. |
