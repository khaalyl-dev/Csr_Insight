# Change Request Management

Request temporary unlock of validated or locked plans/activities for modification.

---

## Routes

| Route | Component | Permission |
|-------|-----------|------------|
| `/changes` | `ChangeRequestsListComponent` | `change_request.read` |
| `/changes/create` | `ChangeRequestCreateComponent` | `change_request.create` |
| `/changes/pending` | `ChangeRequestsPendingComponent` | `change_request.review` |
| `/changes/history` | `ChangeRequestsHistoryComponent` | Corporate, `change_request.history` |
| `/changes/:id` | `ChangeRequestDetailComponent` | — |

---

## Structure

```
change-request-management/
├── change-requests-list/
├── change-request-create/
├── change-requests-pending/
├── change-requests-history/
├── change-request-detail/
├── api/change-requests-api.ts
└── models/
```

---

## Implemented

- [x] Change Requests API — create, list, get, approve, reject
- [x] My requests list
- [x] Create form with reason + document attachments
- [x] Pending review page (approve/reject)
- [x] History page (corporate)
- [x] Detail view with document preview

---

## Roadmap

- [ ] Email notification on approve/reject
