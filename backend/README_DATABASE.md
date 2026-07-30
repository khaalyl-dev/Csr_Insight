# Database — Backend

MySQL 8+ database initialized via `init_db.py`. Schema evolves via SQLAlchemy models + automatic patches.

---

## Initial setup (fresh DB)

```bash
mysql -u root -p -e "CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cd backend
python3 init_db.py
```

**Effects:**
- `db.create_all()` creates all 22 tables from `models/`
- Inserts CSR categories (Environment, Social, Governance, Education, Health)
- Inserts test users and sites
- Assigns sites to users (`user_sites`)

**Reset:** Drop and recreate the database, then run `init_db.py` again.

---

## Runtime schema evolution

On every startup (`python3 app.py`), the app runs:

1. `db.create_all()` — creates missing tables
2. `apply_schema_patches()` — additive `ALTER TABLE` for existing databases

See `core/schema_patches.py` and [`../Database/MIGRATIONS.md`](../Database/MIGRATIONS.md).

---

## Schema documentation

| File | Content |
|------|---------|
| [`../Database/TABLES_ET_COLONNES.md`](../Database/TABLES_ET_COLONNES.md) | Full column reference (French) |
| [`../Database/schema.dbml`](../Database/schema.dbml) | DBML entity diagram |
| [`../Database/MIGRATIONS.md`](../Database/MIGRATIONS.md) | Setup and patch history |
| [`../docs/DATABASE.md`](../docs/DATABASE.md) | English overview |

---

## Key tables

| Table | Model | Purpose |
|-------|-------|---------|
| `planned_activity` | `CsrActivity` | Planned CSR activities |
| `realized_activity` | `RealizedCsr` | Realization reports |
| `csr_plans` | `CsrPlan` | Annual plans |
| `activity_kpis` | `ActivityKpi` | Computed KPIs per activity |
| `user_permissions` | `UserPermission` | RBAC matrix |

Legacy names (`csr_activities`, `realized_csr`) are no longer used.
