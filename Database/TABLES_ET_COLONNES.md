# Tables et description des colonnes — CSR Insight

Référence alignée sur les modèles SQLAlchemy dans `backend/models/` (MySQL 8+, charset `utf8mb4`).

**22 tables** — dernière synchronisation avec le code source du backend.

---

## Enums (types énumérés)

| Enum | Valeurs | Description |
|------|---------|-------------|
| **user_role** | `SITE_USER`, `CORPORATE_USER` | Rôle utilisateur |
| **plan_status** | `DRAFT`, `SUBMITTED`, `VALIDATED`, `REJECTED`, `LOCKED` | Statut du plan annuel |
| **activity_status** | `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `VALIDATED`, `SUBMITTED`, `REJECTED` | Statut activité / réalisation |
| **validation_status** | `PENDING`, `APPROVED`, `REJECTED` | Statut validation / demande de modification |
| **entity_type** | `PLAN`, `ACTIVITY` | Type d'entité ciblée |
| **partner_type** | `NGO`, `SCHOOL`, `ASSOCIATION`, `SUPPLIER`, `GOVERNMENT`, `OTHER` | Type partenaire externe |
| **validation_mode** | `101`, `111` | `101` = corporate seul ; `111` = site L1 puis corporate |

---

## users

Comptes utilisateurs (Site User, Corporate User).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **first_name** | VARCHAR(255) | NON | Prénom |
| **last_name** | VARCHAR(255) | NON | Nom |
| **email** | VARCHAR(255) UNIQUE | NON | Identifiant de connexion |
| **password_hash** | VARCHAR(255) | NON | Mot de passe hashé (bcrypt) |
| **role** | VARCHAR(50) | NON | `SITE_USER` ou `CORPORATE_USER` |
| **is_active** | BOOLEAN | NON | Compte actif (défaut: true) |
| **is_corporate_global** | BOOLEAN | NON | Accès corporate tous sites (défaut: false) |
| **avatar_url** | VARCHAR(512) | OUI | Chemin photo de profil |
| **phone** | VARCHAR(64) | OUI | Téléphone |
| **language** | VARCHAR(10) | NON | Langue UI (`en`, `fr`) |
| **theme** | VARCHAR(20) | NON | Thème (`light`, `dark`) |
| **notify_csr_plan_validation** | BOOLEAN | NON | Notif validation plan |
| **notify_activity_validation** | BOOLEAN | NON | Notif validation activité |
| **notify_activity_reminders** | BOOLEAN | NON | Rappels activités |
| **notify_weekly_summary_email** | BOOLEAN | NON | Email résumé hebdomadaire |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

---

## user_sessions

Sessions JWT actives.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID session |
| **user_id** | CHAR(36) FK → users | NON | Utilisateur |
| **refresh_token** | VARCHAR(512) | NON | JTI du token |
| **ip_address** | VARCHAR(45) | OUI | IP connexion |
| **user_agent** | VARCHAR(512) | OUI | Navigateur / client |
| **expires_at** | DATETIME | NON | Expiration |
| **created_at** | DATETIME | OUI | Date création |

---

## user_permissions

Matrice RBAC granulaire par utilisateur.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **user_id** | CHAR(36) FK → users | NON | Utilisateur |
| **resource** | VARCHAR(64) | NON | Ressource (`plan`, `activity`, `document`, …) |
| **action** | VARCHAR(64) | NON | Action (`read`, `create`, `update`, `delete`, `validate`, …) |
| **is_allowed** | BOOLEAN | NON | Permission accordée (défaut: true) |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

**Contrainte :** UNIQUE (`user_id`, `resource`, `action`)

---

## user_sites

Association utilisateur ↔ site avec niveau de validation.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **user_id** | CHAR(36) FK → users | NON | Utilisateur |
| **site_id** | CHAR(36) FK → sites | NON | Site |
| **grade** | VARCHAR(20) | OUI | `level_0`, `level_1`, `level_2`, `level_3` |
| **is_active** | BOOLEAN | NON | Accès actif |
| **granted_by** | CHAR(36) FK → users | OUI | Accordeur |
| **granted_at** | DATETIME | OUI | Date attribution |
| **access_types_json** | TEXT | OUI | Types d'accès (JSON array) |

**Contrainte :** UNIQUE (`user_id`, `site_id`)

---

## sites

Sites / usines COFICAB.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **name** | VARCHAR(255) | NON | Nom du site |
| **code** | VARCHAR(50) UNIQUE | NON | Code usine (ex. COFSRB) |
| **region** | VARCHAR(255) | OUI | Région |
| **country** | VARCHAR(255) | OUI | Pays |
| **location** | VARCHAR(255) | OUI | Adresse / localisation |
| **description** | TEXT | OUI | Description |
| **is_active** | BOOLEAN | NON | Site actif |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

---

## categories

Catégories d'activités CSR.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **name** | VARCHAR(255) | NON | Nom (Environment, Social, …) |
| **description** | TEXT | OUI | Description |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

---

## external_partners

Partenaires externes (ONG, écoles, associations).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **name** | VARCHAR(255) | NON | Nom |
| **type** | VARCHAR(50) | NON | Type partenaire |
| **contact_person** | VARCHAR(255) | OUI | Contact |
| **email** | VARCHAR(255) | OUI | Email |
| **phone** | VARCHAR(50) | OUI | Téléphone |
| **address** | TEXT | OUI | Adresse |
| **website** | VARCHAR(255) | OUI | Site web |
| **description** | TEXT | OUI | Description |
| **is_active** | BOOLEAN | NON | Actif |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

---

## csr_plans

Plans annuels CSR par site et par année.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | NON | Site |
| **year** | INT | NON | Année du plan |
| **validation_mode** | VARCHAR(10) | NON | `101` ou `111` (défaut: `101`) |
| **status** | VARCHAR(20) | NON | `DRAFT`, `SUBMITTED`, `VALIDATED`, `REJECTED`, `LOCKED` |
| **allocated_budget** | DECIMAL(15,2) | OUI | Budget alloué (€) |
| **total_hc** | INT | OUI | Effectif total (headcount) |
| **submitted_at** | DATETIME | OUI | Date soumission |
| **rejected_comment** | TEXT | OUI | Motif de rejet |
| **rejected_activity_ids** | TEXT | OUI | IDs activités à corriger (JSON array) |
| **validation_step** | INT | OUI | Étape workflow (`1` = L1, `2` = corporate) |
| **validated_at** | DATETIME | OUI | Date validation finale |
| **realization_report_submitted_at** | DATETIME | OUI | Soumission rapport CSR consolidé |
| **unlock_until** | DATETIME | OUI | Fin déverrouillage temporaire |
| **unlock_since** | DATETIME | OUI | Début déverrouillage |
| **created_by** | CHAR(36) FK → users | OUI | Créateur |
| **submitted_by** | CHAR(36) FK → users | OUI | Soumissionnaire |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

**Contrainte :** UNIQUE (`site_id`, `year`)

---

## planned_activity

Activités CSR planifiées (modèle `CsrActivity`).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **plan_id** | CHAR(36) FK → csr_plans | NON | Plan parent |
| **category_id** | CHAR(36) FK → categories | NON | Catégorie |
| **external_partner_id** | CHAR(36) FK → external_partners | OUI | Partenaire externe |
| **nb_of_external_partner** | INT | NON | Nombre partenaires (défaut: 0) |
| **activity_number** | VARCHAR(50) | NON | Numéro activité (ex. CSR 1) |
| **title** | VARCHAR(255) | NON | Titre |
| **organization** | VARCHAR(255) | OUI | `INTERNAL` ou `PARTNERSHIP` |
| **contract_type** | VARCHAR(100) | OUI | `ONE_SHOT` ou `SUCCESSIVE_PERFORMANCE` |
| **description** | TEXT | OUI | Description détaillée |
| **collaboration_nature** | VARCHAR(30) | OUI | Charity, Partnership, Sponsorship, Others |
| **periodicity** | VARCHAR(100) | OUI | Périodicité |
| **planned_budget** | DECIMAL(15,2) | OUI | Budget prévu (€) |
| **action_impact_target** | DECIMAL(15,2) | OUI | Objectif d'impact (nombre) |
| **action_impact_unit** | VARCHAR(100) | OUI | Unité d'impact |
| **action_impact_duration** | VARCHAR(100) | OUI | Durée de l'impact |
| **employees_planned** | INT | OUI | Volontaires internes prévus |
| **start_year** | INT | OUI | Année démarrage (récurrent) |
| **edition** | INT | OUI | Numéro édition |
| **organizer** | VARCHAR(255) | OUI | Organisateur |
| **status** | VARCHAR(20) | NON | Statut activité |
| **created_by** | CHAR(36) FK → users | OUI | Créateur |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |
| **unlock_until** | DATETIME | OUI | Fin déverrouillage |
| **unlock_since** | DATETIME | OUI | Début déverrouillage |
| **off_plan_validation_mode** | VARCHAR(10) | OUI | Mode validation modification in-plan |
| **off_plan_validation_step** | INT | OUI | Étape validation modification |

**Contrainte :** UNIQUE (`plan_id`, `activity_number`)

---

## realized_activity

Réalisations / rapports d'exécution (modèle `RealizedCsr`).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **activity_id** | CHAR(36) FK → planned_activity | NON | Activité planifiée |
| **participants** | INT | OUI | Participants internes |
| **corporate_image_improved** | BOOLEAN | OUI | Image corporate améliorée |
| **incidents_number** | INT | OUI | Nombre d'incidents |
| **contact_department** | VARCHAR(255) | OUI | Département contact |
| **realized_budget** | DECIMAL(15,2) | OUI | Budget réalisé (€) |
| **action_impact_actual** | DECIMAL(15,2) | OUI | Impact réalisé |
| **action_impact_unit** | VARCHAR(100) | OUI | Unité d'impact |
| **is_off_plan** | BOOLEAN | NON | Activité hors plan (défaut: false) |
| **off_plan_validation_mode** | VARCHAR(10) | OUI | Mode validation hors plan |
| **off_plan_validation_step** | INT | OUI | Étape validation hors plan |
| **realization_date** | DATE | OUI | Date de réalisation |
| **comment** | TEXT | OUI | Commentaire |
| **contact_name** | VARCHAR(255) | OUI | Nom contact |
| **contact_email** | VARCHAR(255) | OUI | Email contact |
| **created_by** | CHAR(36) FK → users | OUI | Saisisseur |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |
| **unlock_until** | DATETIME | OUI | Fin déverrouillage |
| **unlock_since** | DATETIME | OUI | Début déverrouillage |
| **status** | VARCHAR(20) | NON | Statut |

---

## csr_objectives

Objectifs planifiés par activité.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **activity_id** | CHAR(36) FK → planned_activity | NON | Activité |
| **objective** | TEXT | NON | Texte de l'objectif |
| **created_at** | DATETIME | OUI | Date création |

---

## csr_completed_objectives

Objectifs atteints (liés à l'activité planifiée).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **activity_id** | CHAR(36) FK → planned_activity | NON | Activité |
| **objective** | TEXT | NON | Texte objectif atteint |
| **achieved** | BOOLEAN | NON | Atteint (défaut: true) |
| **created_at** | DATETIME | OUI | Date création |

---

## csr_attachments

Pièces jointes activité (chemins fichiers).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **activity_id** | CHAR(36) FK → planned_activity | NON | Activité |
| **file_path** | TEXT | NON | Chemin fichier |
| **uploaded_at** | DATETIME | OUI | Date upload |

---

## activity_kpis

KPI calculés par activité (service `kpi_management`).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **plan_id** | CHAR(36) FK → csr_plans | NON | Plan |
| **activity_id** | CHAR(36) FK → planned_activity UNIQUE | NON | Activité |
| **incidents_count** | INT | OUI | Nombre incidents |
| **participants_actual_sum** | INT | OUI | Participants réels |
| **employees_planned** | INT | OUI | Employés prévus |
| **involvement_rate** | DECIMAL(8,2) | OUI | Taux d'implication |
| **announced_objectives_count** | INT | OUI | Objectifs annoncés |
| **completed_objectives_count** | INT | OUI | Objectifs complétés |
| **action_delivery_rate** | DECIMAL(8,2) | OUI | Taux de livraison |
| **realized_budget_sum** | DECIMAL(15,2) | OUI | Budget réalisé cumulé |
| **planned_budget_amount** | DECIMAL(15,2) | OUI | Budget planifié |
| **budget_control_rate** | DECIMAL(8,2) | OUI | Contrôle budget |
| **plan_total_hc** | INT | OUI | HC total du plan |
| **participants_vs_total_hc_rate** | DECIMAL(8,2) | OUI | % participants / HC |
| **lifecycle_status** | VARCHAR(20) | OUI | `DRAFT`, `PLANNED`, `PENDING`, `COMPLETED` |
| **created_at** | DATETIME | OUI | Date création |
| **updated_at** | DATETIME | OUI | Dernière mise à jour |

---

## validations

Enregistrements de validation multi-niveaux (plan ou activité).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **entity_type** | VARCHAR(20) | NON | `PLAN` ou `ACTIVITY` |
| **entity_id** | CHAR(36) | NON | ID entité |
| **site_id** | CHAR(36) FK → sites | NON | Site |
| **grade** | VARCHAR(20) | OUI | `level_1`, `level_2` |
| **status** | VARCHAR(20) | NON | `PENDING`, `APPROVED`, `REJECTED` |
| **validated_by** | CHAR(36) FK → users | OUI | Validateur |
| **comment** | TEXT | OUI | Commentaire / motif rejet |
| **rejected_activity_ids** | TEXT | OUI | IDs activités rejetées (JSON) |
| **validated_at** | DATETIME | OUI | Date décision |
| **created_at** | DATETIME | OUI | Date création demande |

**Contrainte :** UNIQUE (`entity_type`, `entity_id`, `grade`)

---

## change_requests

Demandes de déverrouillage (plan ou activité validé/verrouillé).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | NON | Site |
| **entity_type** | VARCHAR(20) | NON | `PLAN` ou `ACTIVITY` |
| **entity_id** | CHAR(36) | NON | Entité ciblée |
| **year** | INT | NON | Année concernée |
| **reason** | TEXT | OUI | Justification |
| **status** | VARCHAR(20) | NON | `PENDING`, `APPROVED`, `REJECTED` |
| **requested_by** | CHAR(36) FK → users | NON | Demandeur |
| **requested_duration** | VARCHAR(100) | OUI | Durée demandée (ex. `7 days`) |
| **validation_mode** | VARCHAR(10) | OUI | `101` ou `111` |
| **validation_step** | INT | OUI | Étape validation déverrouillage |
| **reviewed_by** | CHAR(36) FK → users | OUI | Relecteur |
| **reviewed_at** | DATETIME | OUI | Date décision |
| **created_at** | DATETIME | OUI | Date soumission |

---

## documents

Métadonnées fichiers (stockage disque via `MEDIA_FOLDER`).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | OUI | Site (NULL = photo profil) |
| **file_name** | VARCHAR(255) | NON | Nom fichier |
| **file_path** | VARCHAR(512) | NON | Chemin stockage |
| **file_type** | VARCHAR(20) | OUI | PDF, PNG, DOCX, … |
| **is_pinned** | BOOLEAN | OUI | Épinglé |
| **change_request_id** | CHAR(36) FK → change_requests | OUI | Demande de modification |
| **entity_type** | VARCHAR(20) | OUI | Type entité liée |
| **entity_id** | CHAR(36) | OUI | ID entité liée |
| **uploaded_by** | CHAR(36) FK → users | OUI | Déposant |
| **uploaded_at** | DATETIME | OUI | Date upload |
| **updated_at** | DATETIME | OUI | Dernière modification |

---

## audit_logs

Journal d'audit applicatif.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | OUI | Site |
| **user_id** | CHAR(36) FK → users | OUI | Utilisateur |
| **action** | VARCHAR(64) | NON | Type action |
| **entity_type** | VARCHAR(20) | NON | Type entité |
| **entity_id** | CHAR(36) | OUI | ID entité |
| **description** | TEXT | OUI | Description |
| **entity_history_id** | CHAR(36) FK → entity_history | OUI | Lien historique |
| **created_at** | DATETIME | NON | Horodatage |

---

## entity_history

Snapshots JSON avant/après modification.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | OUI | Site |
| **entity_type** | VARCHAR(20) | NON | Type entité |
| **entity_id** | CHAR(36) | OUI | ID entité |
| **old_data** | JSON | OUI | État avant (NULL si CREATE) |
| **new_data** | JSON | OUI | État après (NULL si DELETE) |
| **modified_by** | CHAR(36) FK → users | OUI | Modificateur |
| **modified_at** | DATETIME | NON | Horodatage |

---

## notifications

Notifications in-app par utilisateur.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **user_id** | CHAR(36) FK → users | NON | Destinataire |
| **site_id** | CHAR(36) FK → sites | OUI | Site contexte |
| **title** | VARCHAR(255) | NON | Titre |
| **message** | TEXT | OUI | Message |
| **type** | ENUM | OUI | `info`, `success`, `warning`, `error` |
| **entity_type** | VARCHAR(50) | OUI | Type entité liée |
| **entity_id** | CHAR(36) | OUI | ID entité liée |
| **is_read** | BOOLEAN | NON | Lu (défaut: false) |
| **created_at** | DATETIME | OUI | Date création |

---

## csr_snapshots

Agrégats mensuels pour Power BI (usage futur).

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **site_id** | CHAR(36) FK → sites | NON | Site |
| **year** | INT | NON | Année |
| **month** | INT | NON | Mois |
| **total_budget** | DECIMAL(15,2) | OUI | Budget total |
| **total_realized** | DECIMAL(15,2) | OUI | Montant réalisé |
| **total_activities** | INT | OUI | Nombre activités |
| **completion_rate** | DECIMAL(5,2) | OUI | Taux complétion |
| **created_at** | DATETIME | OUI | Date snapshot |

**Contrainte :** UNIQUE (`site_id`, `year`, `month`)

---

## chatbot_logs

Historique échanges chatbot IA.

| Colonne | Type | Null | Description |
|---------|------|------|-------------|
| **id** | CHAR(36) PK | NON | UUID |
| **user_id** | CHAR(36) FK → users | NON | Utilisateur |
| **site_id** | CHAR(36) FK → sites | OUI | Contexte site |
| **question** | TEXT | OUI | Question |
| **answer** | TEXT | OUI | Réponse |
| **created_at** | DATETIME | OUI | Horodatage |

---

## Diagramme des relations (résumé)

```
users ─────┬── user_sessions, user_permissions, user_sites, notifications, chatbot_logs
           └── (created_by / submitted_by / validated_by / …) sur toutes les entités métier

sites ─────┬── csr_plans ── planned_activity ──┬── realized_activity
           │                                    ├── csr_objectives
           │                                    ├── csr_completed_objectives
           │                                    ├── csr_attachments
           │                                    └── activity_kpis
           ├── change_requests, documents, validations
           ├── audit_logs, entity_history, csr_snapshots
           └── notifications

categories ── planned_activity
external_partners ── planned_activity
```

---

## Tables obsolètes (non présentes dans le code actuel)

| Table | Statut |
|-------|--------|
| `csr_activities` | Remplacée par `planned_activity` |
| `realized_csr` | Remplacée par `realized_activity` |
| `validation_steps` | Non implémentée |
| `user_notifications` | Fusionnée dans `notifications.is_read` |
| `notification_settings` | Préférences sur colonnes `users.notify_*` |

Voir [MIGRATIONS.md](./MIGRATIONS.md) pour l'historique des changements.
