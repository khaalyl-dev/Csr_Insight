# File Management

Document library — upload, download, pin, filter by site and entity.

---

## Routes

| Route | Component | Permission |
|-------|-----------|------------|
| `/documents` | `DocumentsListComponent` | `document.read` |

Documents are also attached from plan/activity/change-request screens.

---

## Structure

```
file-management/
├── documents-list/
├── api/documents-api.ts
└── models/
```

Storage: backend `MEDIA_FOLDER` (default `frontend/src/media/`)

---

## API (`/api/documents`)

`GET`, `POST /upload`, `PUT`, `DELETE`, `PATCH /pin`, `GET /download/:path`, `GET /serve/:path`

---

## Implemented

- [x] Documents API — upload, list, delete, update, pin
- [x] Documents list page with site filter
- [x] Download and inline serve URLs
- [x] Upload from activity/plan/change-request forms

---

## Roadmap

- [ ] Drag-and-drop upload component
- [ ] PDF/image preview modal
- [ ] Configurable max file size validation (frontend)
