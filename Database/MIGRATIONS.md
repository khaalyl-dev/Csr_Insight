# Migrations & évolution du schéma — CSR Insight

Le projet **n'utilise pas Alembic, Flyway ou Liquibase**. L'évolution du schéma repose sur trois mécanismes.

---

## 1. Création initiale — `init_db.py`

Pour une **base MySQL vide** :

```bash
cd backend
python3 init_db.py
```

Actions effectuées :
- `db.create_all()` — crée les 22 tables depuis `backend/models/`
- Insertion des catégories CSR (Environment, Social, Education, etc.)
- Création des utilisateurs et sites de test

> **Attention :** ne pas relancer sur une base de production déjà peuplée.

Pour réinitialiser complètement :

```sql
DROP DATABASE csr_db;
CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Puis relancer `python3 init_db.py`.

---

## 2. Démarrage applicatif — `db.create_all()`

À chaque démarrage (`python3 app.py` ou Gunicorn), `app.py` exécute :

```python
db.create_all()
apply_schema_patches(db)
```

`db.create_all()` crée les tables **manquantes** sans modifier les colonnes existantes.

---

## 3. Patches automatiques — `core/schema_patches.py`

Pour les bases **déjà existantes** qui ont un schéma plus ancien, `apply_schema_patches()` applique des modifications additives de façon idempotente :

- Vérifie `information_schema.COLUMNS` avant chaque `ALTER TABLE`
- Crée les tables manquantes (`user_permissions`, `csr_objectives`, `activity_kpis`, etc.)
- Supprime les colonnes/tables obsolètes si présentes

### Patches appliqués (liste non exhaustive)

| Cible | Action |
|-------|--------|
| `change_requests.validation_step` | ADD COLUMN |
| `planned_activity.off_plan_validation_mode/step` | ADD COLUMN |
| `planned_activity.organization`, `contract_type` | ADD COLUMN |
| `planned_activity.nb_of_external_partner` | ADD COLUMN + backfill |
| `planned_activity.employees_planned` | ADD COLUMN |
| `realized_activity.off_plan_validation_mode/step` | ADD COLUMN |
| `realized_activity.corporate_image_improved` | ADD COLUMN |
| `realized_activity.incidents_number` | ADD COLUMN |
| `realized_activity.contact_department` | ADD COLUMN |
| `user_sites.access_types_json` | ADD COLUMN |
| `csr_plans.total_hc`, `allocated_budget` | ADD COLUMN |
| `csr_plans.realization_report_submitted_at` | ADD COLUMN |
| `csr_plans.total_budget` | DROP COLUMN (remplacé par `allocated_budget`) |
| `activity_kpis.lifecycle_status` | ADD COLUMN |
| `user_permissions` | CREATE TABLE IF NOT EXISTS |
| `csr_objectives`, `csr_completed_objectives`, `csr_attachments` | CREATE TABLE IF NOT EXISTS |
| `activity_kpis` | CREATE TABLE IF NOT EXISTS |
| `csr_activity_planned` | DROP TABLE (legacy) |

Source à jour : `backend/core/schema_patches.py`

---

## 4. Modifier le schéma (bonnes pratiques)

1. **Mettre à jour le modèle SQLAlchemy** dans `backend/models/<table>.py`
2. **Ajouter un patch** dans `backend/core/schema_patches.py` si la modification doit s'appliquer aux bases existantes
3. **Mettre à jour la documentation** :
   - `Database/TABLES_ET_COLONNES.md`
   - `Database/schema.dbml`
   - `docs/DATABASE.md` (optionnel)
4. **Tester** sur une copie de la base de production avant déploiement

---

## Tables supprimées / renommées (historique)

| Ancien nom | Statut actuel |
|------------|---------------|
| `csr_activities` | Renommé → `planned_activity` |
| `realized_csr` | Renommé → `realized_activity` |
| `csr_activity_planned` | Supprimé (legacy) |
| `validation_steps` | Non implémenté (logique dans `validations`) |
| `user_notifications` | Non implémenté (`is_read` sur `notifications`) |
| `notification_settings` | Non implémenté (préférences sur `users`) |

---

## Script SQL manuel (seed activités test)

Fichier optionnel : `backend/migrations/seed_test_activities.sql`

Utilisable pour enrichir une base de dev avec des activités de test supplémentaires (hors `init_db.py`).
