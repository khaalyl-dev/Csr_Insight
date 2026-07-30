# audit_history_management

Audit log and entity history.

---

## Files

| File | Purpose |
|------|---------|
| **audit_routes.py** | Blueprint `/api/audit`. List audit logs, entity history. Filter by user, action, entity type, date. |
| **audit_helper.py** | `write_audit()`, `write_entity_history()`. Used by csr_plans, planned_activity, change_requests to record actions. |
| **__init__.py** | Exports `audit_bp`. |
