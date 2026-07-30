# Database — CSR Insight

## Overview

| Property | Value |
|----------|-------|
| Engine | MySQL 8+ |
| ORM | Flask-SQLAlchemy 3.1 |
| Database name | `csr_db` (default) |
| Schema management | `db.create_all()` + `core/schema_patches.py` |
| Migration tool | None (Alembic/Flyway not used) |

---

## Setup

### Prerequisites

- MySQL 8+ server running
- Database created: `CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`

### Initialize

```bash
cd backend
cp .env.example .env   # Configure DB_* variables
python3 init_db.py     # Creates tables + seed data
```

### Seed Data Includes

- CSR categories (Environment, Social, Education, Health, Governance)
- Test users (site + corporate)
- Sample sites

### Test Accounts

| Email | Password | Role |
|-------|----------|------|
| `user@test.com` | `password123` | Site User |
| `admin@test.com` | `admin123` | Corporate User |
| `john@example.com` | `john123` | Site User |

---

## Entity Relationship Diagram

```
users ──────────────┬── user_sessions
  │                 ├── user_permissions
  │                 ├── user_sites ──── sites
  │                 ├── notifications
  │                 └── chatbot_logs
                    │
sites ──────────────┼── csr_plans ──── planned_activity ──── realized_activity
  │                 │         │                │                      │
  │                 │         │                ├── csr_objectives     ├── csr_completed_objectives
  │                 │         │                ├── csr_attachments    └── activity_kpis
  │                 │         │                └── external_partners (M2M)
  │                 │         │
  │                 ├── change_requests        categories
  │                 ├── documents
  │                 ├── validations
  │                 ├── audit_logs
  │                 ├── entity_history
  │                 └── csr_snapshots
                    │
external_partners ──┘
```

---

## Tables (22)

### Users & Access Control

#### `users`
System accounts (site and corporate users).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| first_name, last_name | varchar | |
| email | varchar (unique) | Login identifier |
| password_hash | varchar | bcrypt hash |
| role | enum | `SITE_USER`, `CORPORATE_USER` |
| is_active | boolean | |
| is_corporate_global | boolean | Cross-site corporate access |
| avatar_url | varchar | Profile photo path |
| phone, language, theme | varchar | User preferences |
| notify_* | boolean | Notification preferences |
| created_at, updated_at | datetime | |

#### `user_sessions`
JWT session tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | → users |
| refresh_token | varchar | JWT jti |
| ip_address, user_agent | varchar | |
| expires_at, created_at | timestamp | |

#### `user_permissions`
Granular RBAC permissions per user.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | → users |
| permission_key | varchar | e.g. `plan.read`, `activity.approve` |

#### `user_sites`
User-to-site access mapping.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id, site_id | UUID (FK) | Unique pair |
| grade | varchar | `level_0`, `level_1`, `level_2`, `level_3` |
| is_active | boolean | |
| granted_by | UUID (FK) | → users |
| granted_at | datetime | |

---

### Sites & Reference Data

#### `sites`
COFICAB manufacturing plants/entities.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name, code | varchar | code is unique |
| region, country, location | varchar | |
| description | text | |
| is_active | boolean | |
| created_at, updated_at | timestamp | |

#### `categories`
CSR activity categories.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | varchar | e.g. Environment, Education |
| description | text | |

#### `external_partners`
External entities (NGOs, schools, associations).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| name | varchar | |
| type | enum | NGO, SCHOOL, ASSOCIATION, SUPPLIER, GOVERNMENT, OTHER |
| contact_person, email, phone | varchar | |
| address, website, description | text/varchar | |
| is_active | boolean | |

---

### CSR Core

#### `csr_plans`
Annual CSR plans per site/year.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| site_id | UUID (FK) | → sites |
| year | int | Plan year |
| validation_mode | varchar | `101` or `111` |
| status | enum | DRAFT, SUBMITTED, VALIDATED, REJECTED, LOCKED |
| total_budget, total_hc | decimal/int | |
| submitted_at, validated_at | timestamp | |
| rejection_comment | text | |
| created_at, updated_at | timestamp | |

#### `planned_activity`
Planned CSR activities within a plan.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| plan_id | UUID (FK) | → csr_plans |
| category_id | UUID (FK) | → categories |
| activity_number | varchar | Unique within plan |
| title, description | varchar/text | |
| status | enum | DRAFT, IN_PROGRESS, COMPLETED, etc. |
| planned_budget | decimal | |
| organization | enum | INTERNAL, PARTNERSHIP |
| contract_type | enum | ONE_SHOT, SUCCESSIVE_PERFORMANCE |
| collaboration_nature | enum | CHARITY_DONATION, PARTNERSHIP, etc. |
| planned_start_date, planned_end_date | date | |
| is_off_plan | boolean | Created outside original plan |
| created_at, updated_at | timestamp | |

#### `realized_activity`
Actual execution/reporting data.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| activity_id | UUID (FK) | → planned_activity |
| realized_budget | decimal | |
| employees_actual | int | |
| beneficiaries_count | int | |
| realization_date | date | |
| comments | text | |
| created_at, updated_at | timestamp | |

#### `csr_objectives`
Planned objectives per activity.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| activity_id | UUID (FK) | → planned_activity |
| description | text | |
| target_value | varchar | |
| unit | varchar | |

#### `csr_completed_objectives`
Achieved objectives per realization.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| realized_id | UUID (FK) | → realized_activity |
| description | text | |
| achieved_value | varchar | |

#### `csr_attachments`
File attachments linked to activities.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| activity_id | UUID (FK) | → planned_activity |
| file_name, file_path | varchar | |
| file_type | varchar | |
| uploaded_at | timestamp | |

#### `activity_kpis`
Computed KPIs per activity.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| activity_id | UUID (FK) | → planned_activity |
| budget_variance | decimal | |
| completion_rate | decimal | |
| participant_count | int | |

---

### Workflow & Governance

#### `validations`
Multi-step validation records.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| site_id | UUID (FK) | → sites |
| entity_type | enum | PLAN, ACTIVITY |
| entity_id | UUID | |
| status | enum | PENDING, APPROVED, REJECTED |
| validator_id | UUID (FK) | → users |
| comment | text | |
| validated_at | timestamp | |

#### `change_requests`
Unlock/modification requests on validated entities.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| site_id | UUID (FK) | → sites |
| plan_id / activity_id | UUID (FK) | One required |
| reason | text | |
| status | enum | PENDING, APPROVED, REJECTED |
| requested_duration | int | Days |
| requested_by | UUID (FK) | → users |
| approved_by | UUID (FK) | → users |
| created_at, resolved_at | timestamp | |

---

### Documents & Audit

#### `documents`
File metadata (files stored on disk).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| site_id | UUID (FK) | → sites |
| file_name, file_path, file_type | varchar | |
| entity_type, entity_id | varchar/UUID | Polymorphic link |
| is_pinned | boolean | |
| uploaded_by | UUID (FK) | → users |
| created_at | timestamp | |

#### `audit_logs`
System audit trail.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | → users |
| site_id | UUID (FK) | → sites |
| action | varchar | CREATE, UPDATE, DELETE, APPROVE, etc. |
| entity_type, entity_id | varchar/UUID | |
| details | JSON | Change details |
| ip_address | varchar | |
| created_at | timestamp | |

#### `entity_history`
JSON snapshots of entity state changes.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| entity_type, entity_id | varchar/UUID | |
| snapshot | JSON | Full entity state |
| changed_by | UUID (FK) | → users |
| created_at | timestamp | |

---

### Notifications & Analytics

#### `notifications`
User notifications.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | → users |
| site_id | UUID (FK) | → sites |
| type | varchar | PLAN_VALIDATED, ACTIVITY_REJECTED, etc. |
| title, message | varchar/text | |
| is_read | boolean | |
| entity_type, entity_id | varchar/UUID | Link to related entity |
| created_at | timestamp | |

#### `csr_snapshots`
Monthly Power BI data snapshots (future use).

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| site_id | UUID (FK) | → sites |
| year, month | int | |
| snapshot_data | JSON | Aggregated metrics |
| created_at | timestamp | |

#### `chatbot_logs`
Chatbot query history.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | |
| user_id | UUID (FK) | → users |
| prompt, response | text | |
| model | varchar | |
| created_at | timestamp | |

---

## Enums Reference

| Enum | Values |
|------|--------|
| user_role | SITE_USER, CORPORATE_USER |
| plan_status | DRAFT, SUBMITTED, VALIDATED, REJECTED, LOCKED |
| activity_status | DRAFT, IN_PROGRESS, COMPLETED, CANCELLED, VALIDATED, SUBMITTED, REJECTED |
| validation_status | PENDING, APPROVED, REJECTED |
| entity_type | PLAN, ACTIVITY |
| partner_type | NGO, SCHOOL, ASSOCIATION, SUPPLIER, GOVERNMENT, OTHER |
| organization_type | INTERNAL, PARTNERSHIP |
| contract_type | ONE_SHOT, SUCCESSIVE_PERFORMANCE |
| collaboration_nature | CHARITY_DONATION, PARTNERSHIP, SPONSORSHIP, OTHERS |

---

## Schema Evolution

There is no formal migration framework. Schema changes are applied via:

1. **Model updates** — SQLAlchemy models in `backend/models/`
2. **Startup patches** — `core/schema_patches.py` runs additive ALTER statements on existing databases
3. **Fresh install** — `python3 init_db.py` creates all tables from scratch

For manual reference, see:
- `Database/schema.dbml` — DBML entity diagram
- `Database/TABLES_ET_COLONNES.md` — Full column reference (French)
- `Database/MIGRATIONS.md` — Migration notes

---

## Backup & Maintenance

```bash
# Backup
mysqldump -u root -p csr_db > csr_db_backup_$(date +%Y%m%d).sql

# Restore
mysql -u root -p csr_db < csr_db_backup_20260730.sql
```

### Recommended Indexes

Primary keys and foreign keys are indexed by default. Consider additional indexes for:
- `csr_plans(site_id, year, status)`
- `planned_activity(plan_id, status)`
- `audit_logs(created_at, site_id)`
- `notifications(user_id, is_read)`

---

## SQLAlchemy Models Location

All models: `backend/models/`

| Model file | Table |
|------------|-------|
| `user.py` | users |
| `user_session.py` | user_sessions |
| `user_permission.py` | user_permissions |
| `user_site.py` | user_sites |
| `site.py` | sites |
| `category.py` | categories |
| `external_partner.py` | external_partners |
| `csr_plan.py` | csr_plans |
| `planned_activity.py` | planned_activity |
| `realized_activity.py` | realized_activity |
| `csr_objective.py` | csr_objectives |
| `csr_completed_objective.py` | csr_completed_objectives |
| `csr_attachment.py` | csr_attachments |
| `activity_kpi.py` | activity_kpis |
| `validation.py` | validations |
| `change_request.py` | change_requests |
| `document.py` | documents |
| `audit_log.py` | audit_logs |
| `entity_history.py` | entity_history |
| `notification.py` | notifications |
| `csr_snapshot.py` | csr_snapshots |
| `chatbot_log.py` | chatbot_logs |
