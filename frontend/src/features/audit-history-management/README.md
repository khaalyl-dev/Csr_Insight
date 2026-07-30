# Audit History Management

Corporate audit trail — filterable log of user actions on plans, activities, and documents.

---

## Routes

| Route | Component | Access |
|-------|-----------|--------|
| `/admin/audit` | `AuditListComponent` | Corporate, `audit_log.read` |

---

## Structure

```
audit-history-management/
├── audit-list/
├── api/audit-api.ts
└── models/
```

---

## API

`GET /api/audit/logs` — filters: `action`, `entity_type`, `site_id`, `user_id`, `date_from`, `date_to`, `limit`

Entity history (`entity_history` table) is written by backend helpers; diff UI not yet exposed in frontend.

---

## Implemented

- [x] Audit API integration
- [x] Audit list page with filters (site, action, date range)
- [x] Site filter dropdown

---

## Roadmap

- [ ] Entity history diff view (old_data vs new_data)
- [ ] Export audit logs to CSV/Excel
- [ ] Year-over-year trend analysis
