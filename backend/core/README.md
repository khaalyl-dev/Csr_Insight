# core/

Shared infrastructure: database, JWT, permissions, schema evolution.

---

## Files

| File | Purpose |
|------|---------|
| **db.py** | SQLAlchemy instance (`db = SQLAlchemy()`). Initialized in `app.py` with `db.init_app(app)`. |
| **jwt_utils.py** | JWT create/verify. Decorators `@token_required` and `@role_required(['corporate'])`. |
| **permissions.py** | RBAC helpers — permission keys (`plan.read`, `activity.approve`, etc.). |
| **schema_patches.py** | Additive MySQL `ALTER TABLE` patches applied on startup for existing databases. |
| **__init__.py** | Exposes `db` and JWT utilities. |

---

## How it works

- **db**: Models inherit from `db.Model`. `db.session` handles transactions. `db.create_all()` runs on startup.
- **JWT**: Login returns a token. Protected routes verify `Authorization: Bearer <token>` via `@token_required`.
- **Permissions**: Granular keys stored in `user_permissions`; checked in route handlers and mirrored in Angular guards.
- **Schema patches**: Safe migrations without Alembic — see [`../../Database/MIGRATIONS.md`](../../Database/MIGRATIONS.md).
