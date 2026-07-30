# Dashboard Analytics

Executive CSR dashboards via embedded Power BI reports.

---

## Routes

| Route | Component | Access |
|-------|-----------|--------|
| `/dashboard` | `Dashboard` | Authenticated |
| `/dashboard/corporate` | `Dashboard` | Corporate |
| `/dashboard/site` | `Dashboard` | Site user |

---

## Structure

```
dashboard-analytics/
├── dashboard/
│   ├── dashboard.ts           # Power BI iframe embed
│   ├── dashboard.html
│   ├── power-bi.config.ts     # Report IDs, zoom, embed URLs
│   └── dashboard-api.ts       # Legacy /api/dashboard client (unused)
└── README.md
```

---

## Power BI setup

Share links (`https://app.powerbi.com/links/...`) **do not work** in iframes.

1. Open report in Power BI Service → **Embed** → **Website or portal**
2. Copy iframe `src` (`reportEmbed?reportId=...&autoAuth=true`)
3. Update `power-bi.config.ts`

See [Microsoft embed docs](https://learn.microsoft.com/en-us/power-bi/collaborate-share/service-embed-secure).

Screenshots: [`../../../screenshot/PowerBI/`](../../../screenshot/PowerBI/)

---

## Implemented

- [x] Power BI iframe embed (performance, budget, impact dashboards)
- [x] Corporate vs site dashboard routes

---

## Roadmap

- [ ] Re-enable native KPI dashboard via `/api/dashboard/*` (backend already implemented)
- [ ] Advanced filters (site, category, period)
- [ ] Export Excel/PDF from dashboard views
