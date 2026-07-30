# features/

Business modules (Flask blueprints). Each feature is a subpackage with:

- `__init__.py` — exports the blueprint
- `*_routes.py` — route definitions
- `*_helper.py` — shared business logic (optional)

Full API map: [`../../docs/API.md`](../../docs/API.md)

---

## Modules

| Feature | Blueprint | Prefix | Status |
|---------|-----------|--------|--------|
| **user_management** | auth_bp, users_bp | `/api/auth`, `/api/users` | Active |
| **site_management** | sites_bp, categories_bp, external_partners_bp | `/api/sites`, `/api/categories`, `/api/external-partners` | Active (partners stub) |
| **csr_plan_management** | csr_plans_bp, csr_import_bp | `/api/csr-plans` | Active |
| **planned_activity_management** | planned_csr_bp | `/api/csr-activities` | Active |
| **realized_activity_management** | realized_csr_bp | `/api/realized-csr` | Active |
| **change_request_management** | change_requests_bp | `/api/change-requests` | Active |
| **file_management** | documents_bp | `/api/documents` | Active |
| **audit_history_management** | audit_bp | `/api/audit` | Active |
| **notification_management** | notifications_bp | `/api/notifications` | Active + Socket.IO |
| **task_management** | tasks_bp | `/api/tasks` | Active |
| **dashboard_analytics** | dashboard_bp | `/api/dashboard` | Active (frontend uses Power BI) |
| **chatbot_assistant** | chatbot_bp | `/api/chatbot` | Active (requires Ollama) |
| **validation_workflow_management** | validations_bp | `/api/validations` | Stub — logic in plan/activity routes |
| **powerbi_integration** | powerbi_bp | `/api/powerbi` | Stub — Power BI embedded in frontend |
| **health** | health_bp | `/api/health` | Active |

---

## Cross-cutting

| Module | Role |
|--------|------|
| **kpi_management/** | KPI computation service (not a blueprint) |
| **notification_management/socketio_*** | Real-time push for notifications and tasks |
