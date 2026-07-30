# models/

SQLAlchemy models matching MySQL tables. Each file defines one table via `db.Model`.

**22 tables** — see [`../../Database/TABLES_ET_COLONNES.md`](../../Database/TABLES_ET_COLONNES.md) for full column reference.

---

## Files and tables

| File | Table | Model class | Purpose |
|------|-------|-------------|---------|
| **user.py** | users | `User` | Users (auth, profile, notification prefs) |
| **user_session.py** | user_sessions | `UserSession` | JWT sessions |
| **user_permission.py** | user_permissions | `UserPermission` | RBAC permissions |
| **user_site.py** | user_sites | `UserSite` | User–site access (grade, access types) |
| **site.py** | sites | `Site` | COFICAB sites/plants |
| **category.py** | categories | `Category` | CSR categories |
| **external_partner.py** | external_partners | `ExternalPartner` | External partners |
| **csr_plan.py** | csr_plans | `CsrPlan` | Annual CSR plans |
| **planned_activity.py** | planned_activity | `CsrActivity` | Planned activities |
| **realized_activity.py** | realized_activity | `RealizedCsr` | Realization reports |
| **csr_objective.py** | csr_objectives | `CsrObjective` | Planned objectives |
| **csr_completed_objective.py** | csr_completed_objectives | `CsrCompletedObjective` | Completed objectives |
| **csr_attachment.py** | csr_attachments | `CsrAttachment` | Activity attachments |
| **activity_kpi.py** | activity_kpis | `ActivityKpi` | Computed KPIs |
| **validation.py** | validations | `Validation` | Validation workflow records |
| **change_request.py** | change_requests | `ChangeRequest` | Unlock/modification requests |
| **document.py** | documents | `Document` | File metadata |
| **notification.py** | notifications | `Notification` | User notifications |
| **audit_log.py** | audit_logs | `AuditLog` | Action audit trail |
| **entity_history.py** | entity_history | `EntityHistory` | JSON change snapshots |
| **csr_snapshot.py** | csr_snapshots | `CsrSnapshot` | Power BI monthly snapshots |
| **chatbot_log.py** | chatbot_logs | `ChatbotLog` | Chatbot query history |

---

## Usage

```python
from models import User, Site, CsrPlan, CsrActivity
user = User.query.filter_by(email="admin@test.com").first()
```

`__init__.py` exports all models for `db.create_all()` and feature imports.
