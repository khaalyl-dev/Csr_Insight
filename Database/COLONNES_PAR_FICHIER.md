# Colonnes de chaque fichier Excel

Mapping des formulaires Excel COFICAB vers les champs applicatifs (`planned_activity`, `realized_activity`, `csr_plans`, `sites`).

Voir aussi : [TABLES_ET_COLONNES.md](./TABLES_ET_COLONNES.md) pour le schéma MySQL complet.

## Correspondance Excel → base de données (résumé)

| Colonne Excel | Table / colonne MySQL |
|---------------|----------------------|
| COFICAB Entity / Plant | `sites.code` ou `sites.name` |
| Category | `categories.name` → `planned_activity.category_id` |
| Activity description / Title | `planned_activity.title`, `description` |
| Organization | `planned_activity.organization` |
| Name of external entity | `external_partners.name` → `planned_activity.external_partner_id` |
| Cost (EUR) / Budget in € | `planned_activity.planned_budget` / `realized_activity.realized_budget` |
| Contract type | `planned_activity.contract_type` |
| Periodicity | `planned_activity.periodicity` |
| Number of internal volunteers | `planned_activity.employees_planned` / `realized_activity.participants` |
| Action impact (In numbers) | `planned_activity.action_impact_target` / `realized_activity.action_impact_actual` |
| Action impact – Unit | `planned_activity.action_impact_unit` |
| Nature of collaboration | `planned_activity.collaboration_nature` |
| Total HC | `csr_plans.total_hc` |
| Activity N | `planned_activity.activity_number` |
| Region / country | `sites.region`, `sites.country` |
| Year | `csr_plans.year` |

---

## 1. 10.30.13.09-01 Annual CSR Plan updated (1).xlsx

### Feuille « Annual CSR Plan_Report » (plan annuel CSR)

| # | Colonne |
|---|---------|
| 1 | COFICAB Entity |
| 2 | Category |
| 3 | Activity type |
| 4 | Activity description |
| 5 | Organization |
| 6 | Name of external entity (if any) |
| 7 | Cost (EUR) |
| 8 | Contract type |
| 9 | Periodicity |
| 10 | Number of internal volunteers |
| 11 | Action impact (In numbers) |
| 12 | Action impact – Unit |
| 13 | Action impact duration |
| 14 | Sustainability of action |
| 15 | Status |

---

## 2. 10.30.13.10-01 CSR Reporting form updated (1).xlsx

### Feuille « Annual CSR Plan_Report »
Même structure que le plan annuel ci‑dessus, avec **Cost** (sans « EUR ») au lieu de Cost(EUR).

### Feuille « CSR Reporting form » (saisie des activités réalisées)

Champs du formulaire (libellés / zones de saisie) :

| Champ / zone | Description |
|--------------|-------------|
| Name of company/factory | Nom ou code du site (usine/entité) |
| Contact – Department | Département du contact |
| Contact – Name | Nom du contact |
| Contact – E-mail | E-mail du contact |
| Content of the activity | Titre de l’activité (court) |
| Outline of the activity | Description (quoi, qui, quand, pourquoi, comment) |
| Photos | Photo 1, Photo 2 (pièces jointes) |
| Activity status, comments, etc. | Statut, commentaires |
| Number of participants per event | Nombre de participants par événement |
| Percentage out of all the employees (%) | % des employés participants |
| Budget in € | Budget réalisé (€) |
| Number of external participants | Nombre de participants externes |

---

## 3. 2024 CSR Consolidated Report Form (1).xlsx

### Feuille « Group figures » (chiffres consolidés groupe)

| # | Colonne |
|---|---------|
| 1 | Activity N |
| 2 | Region |
| 3 | country |
| 4 | Plant |
| 5 | Activity Title/ description |
| 6 | Category |
| 7 | Nature of collaboration |
| 8 | Year |
| 9 | Start year |
| 10 | Edition |
| 11 | Nbr of internal Participants |
| 12 | Total HC |
| 13 | Percentage out of all the employees % |
| 14 | Estimated Budget in € |
| 15 | Actual Budget in € |
| 16 | Action Impact In Numbers |
| 17 | Action Impact Unit |
| 18 | Organizer |
| 19 | External Partner |
| 20 | Number of External Partners |

### Feuille « Activities & Slide Numbers »

| # | Colonne |
|---|---------|
| 1 | Activity N |
| 2 | Region |
| 3 | country |
| 4 | Plant |
| 5 | Activity Title/ description |
| 6 | Slide Number in PPT |

### Feuille « EE0 » (vue régionale simplifiée)

| # | Colonne |
|---|---------|
| 1 | Activity N |
| 2 | Region |
| 3 | country |
| 4 | Plant |
| 5 | Activity Title/ description |
| 6 | Category |
| 7 | Year |
| 8 | Start year |
| 9 | edition |
| 10 | Nbr of internal Participants |
| 11 | Percentage out of all the employees % |
| 13 | Budget in € |
| 14 | Organizer |
| 15 | External Partner |

### Feuille « categories »

| # | Colonne |
|---|---------|
| 2 | Region |
| 3 | Country |
| 4 | Plant |
| 5 | Category |
| 6 | Nature |
