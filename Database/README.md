# Base de données — CSR Insight

Documentation du schéma **MySQL 8+** utilisé par le backend Flask (`backend/models/`).

---

## Contenu du dossier

| Fichier | Description |
|---------|-------------|
| **[TABLES_ET_COLONNES.md](./TABLES_ET_COLONNES.md)** | Référence complète : 22 tables, colonnes, contraintes, relations |
| **[schema.dbml](./schema.dbml)** | Schéma conceptuel DBML (diagramme ER) — importable dans [dbdiagram.io](https://dbdiagram.io) |
| **[MIGRATIONS.md](./MIGRATIONS.md)** | Création de base, évolution du schéma, patches automatiques |
| **[COLONNES_PAR_FICHIER.md](./COLONNES_PAR_FICHIER.md)** | Mapping colonnes Excel COFICAB → champs applicatifs |

Documentation complémentaire (déploiement, API) : [`../docs/DATABASE.md`](../docs/DATABASE.md)

---

## Stack

| Composant | Valeur |
|-----------|--------|
| SGBD | MySQL 8+ |
| Charset | `utf8mb4` |
| Collation | `utf8mb4_unicode_ci` |
| ORM | Flask-SQLAlchemy 3.1 |
| Nom par défaut | `csr_db` |

---

## Schéma — 22 tables

```
Utilisateurs & accès          CSR métier                    Workflow & gouvernance
─────────────────────         ─────────────                 ──────────────────────
users                         csr_plans                     validations
user_sessions                 planned_activity              change_requests
user_permissions              realized_activity             documents
user_sites                    csr_objectives                audit_logs
sites                         csr_completed_objectives      entity_history
categories                    csr_attachments               notifications
external_partners             activity_kpis                 chatbot_logs
                              csr_snapshots
```

---

## Correspondance modèles Python

| Table MySQL | Classe SQLAlchemy | Fichier |
|-------------|-------------------|---------|
| `users` | `User` | `backend/models/user.py` |
| `user_sessions` | `UserSession` | `backend/models/user_session.py` |
| `user_permissions` | `UserPermission` | `backend/models/user_permission.py` |
| `user_sites` | `UserSite` | `backend/models/user_site.py` |
| `sites` | `Site` | `backend/models/site.py` |
| `categories` | `Category` | `backend/models/category.py` |
| `external_partners` | `ExternalPartner` | `backend/models/external_partner.py` |
| `csr_plans` | `CsrPlan` | `backend/models/csr_plan.py` |
| `planned_activity` | `CsrActivity` | `backend/models/planned_activity.py` |
| `realized_activity` | `RealizedCsr` | `backend/models/realized_activity.py` |
| `csr_objectives` | `CsrObjective` | `backend/models/csr_objective.py` |
| `csr_completed_objectives` | `CsrCompletedObjective` | `backend/models/csr_completed_objective.py` |
| `csr_attachments` | `CsrAttachment` | `backend/models/csr_attachment.py` |
| `activity_kpis` | `ActivityKpi` | `backend/models/activity_kpi.py` |
| `validations` | `Validation` | `backend/models/validation.py` |
| `change_requests` | `ChangeRequest` | `backend/models/change_request.py` |
| `documents` | `Document` | `backend/models/document.py` |
| `audit_logs` | `AuditLog` | `backend/models/audit_log.py` |
| `entity_history` | `EntityHistory` | `backend/models/entity_history.py` |
| `notifications` | `Notification` | `backend/models/notification.py` |
| `csr_snapshots` | `CsrSnapshot` | `backend/models/csr_snapshot.py` |
| `chatbot_logs` | `ChatbotLog` | `backend/models/chatbot_log.py` |

---

## Commandes

### Création initiale (base fraîche)

```bash
# Créer la base MySQL
mysql -u root -p -e "CREATE DATABASE csr_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Depuis backend/
cd backend
cp .env.example .env   # Configurer DB_*
python3 init_db.py     # Tables + données de test
```

### Démarrage applicatif (crée aussi les tables manquantes)

```bash
cd backend
python3 app.py
# db.create_all() + apply_schema_patches() s'exécutent au démarrage
```

### Comptes de test (après init_db.py)

| Email | Mot de passe | Rôle |
|-------|--------------|------|
| `user@test.com` | `password123` | Site User |
| `admin@test.com` | `admin123` | Corporate User |
| `john@example.com` | `john123` | Site User |

---

## Enums principaux

| Enum | Valeurs |
|------|---------|
| **user_role** | `SITE_USER`, `CORPORATE_USER` |
| **plan_status** | `DRAFT`, `SUBMITTED`, `VALIDATED`, `REJECTED`, `LOCKED` |
| **activity_status** | `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `VALIDATED`, `SUBMITTED`, `REJECTED` |
| **validation_status** | `PENDING`, `APPROVED`, `REJECTED` |
| **entity_type** | `PLAN`, `ACTIVITY` |
| **validation_mode** | `101` (corporate seul), `111` (site L1 → corporate L2) |

---

## Sauvegarde

```bash
mysqldump -u root -p csr_db > csr_db_backup_$(date +%Y%m%d).sql
mysql -u root -p csr_db < csr_db_backup_20260730.sql
```
