# CSRPlanManagement

Création et édition des plans annuels CSR par site.

## Scope

- Import/export Excel et PDF
- Catégorisation des activités (Environnement, Social, Gouvernance)
- Assignation des budgets, KPI et responsables
- Workflow de validation multi-niveaux (site → corporate)

## Structure

- `annual-plans/` – Liste et pilotage des plans annuels
- `plan-detail/`, `plan-edit/`, `plan-validation/` – Fiche plan, édition, validation
- `plan-create-sidebar/`, `plan-edit-sidebar/` – Création / édition plan en panneau
- `models/` – CsrPlan
- `api/` – csr-plans-api

Les activités planifiées (CRUD, hors plan, sidebars) sont dans **`planned-activity-management`**.

## À développer

- [ ] **CSR Plans API** – CRUD csr_plans (create, list, get, update, submit)
- [ ] **CSR Activities API** – CRUD csr_activities, activity_kpis
- [ ] **Plan create/edit** – Formulaire plan annuel (year, allocated_budget, status)
- [ ] **Activity create/edit** – Formulaire activité (title, category, budget, KPI, dates, organization_type, contract_type)
- [ ] **Import Excel** – Import plan/activités depuis Excel
- [ ] **Export Excel/PDF** – Export plan annuel
- [ ] **Validation workflow** – Boutons soumettre/valider/rejeter (via csr-plans-api)
