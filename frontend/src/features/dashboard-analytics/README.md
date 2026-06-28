# DashboardAndAnalytics

Tableau de bord consolidé par site et global.

## Scope

- Filtres avancés (site, catégorie, type, période, statut)
- Visualisation des KPI : taux de réalisation, écarts budgétaires, top activités
- Graphiques interactifs : courbes, camemberts, barres
- Export Excel/PDF et drill-down par site

## Structure

- `dashboard/` – Dashboard site avec métriques et graphique activités (Chart.js)
- `models/` – (snapshots dans powerbi-integration)

## Power BI (iframe)

Les liens de partage `https://app.powerbi.com/links/...` **ne fonctionnent pas** en iframe (erreur « refused to connect »).

1. Ouvrir le rapport dans Power BI Service → **Fichier** → **Intégrer le rapport** → **Site web ou portail**
2. Copier le `src` de l’iframe (`reportEmbed?reportId=...&autoAuth=true`)
3. Mettre à jour `dashboard/power-bi.config.ts` (`POWER_BI_REPORT_ID`, etc.)

### Zoom

- `POWER_BI_ZOOM_LEVEL` : zoom CSS sur l’iframe (`0.5` = 50 %) — **fonctionne** avec autoAuth.
- `settings.zoomLevel` dans l’URL **est ignoré** sans jeton d’accès / SDK.
- `setZoom()` via powerbi-client nécessite un **access token** backend (Azure AD).

Doc : [Embed a report in a secure portal](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure)

## À développer

- [ ] **Filtres avancés** – Filtres par site, catégorie, période, statut
- [ ] **Vue corporate** – Dashboard consolidé tous sites
- [ ] **Graphiques supplémentaires** – Camemberts (par catégorie), courbes (tendance), barres comparatives
- [ ] **KPI cards** – Taux de réalisation, écarts budgétaires, top activités
- [ ] **Export Excel/PDF** – Export du tableau de bord
- [ ] **Drill-down** – Clic sur une métrique → liste détaillée
