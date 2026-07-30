# Site Management

Corporate administration of COFICAB sites, site users, and CSR categories.

---

## Routes

| Route | Component | Access |
|-------|-----------|--------|
| `/sites` | `SitesListComponent` | Corporate, `site.read` |
| `/sites/create` | `SiteFormComponent` | Corporate |
| `/sites/edit/:id` | `EditSiteComponent` | Corporate |
| `/sites/:id/users` | `SiteUsersComponent` | Corporate |
| `/categories` | `CategoriesListComponent` | Corporate, `category.read` |

---

## Structure

```
site-management/
├── sites-list/
├── site-form/
├── edit-site/
├── site-users/
├── categories-list/
├── api/sites-api.ts
├── api/categories-api.ts
└── models/
```

---

## Implemented

- [x] Sites list with active/inactive toggle
- [x] Site create and edit forms
- [x] Site users assignment (grade, access)
- [x] Categories list, create, delete with reassignment

---

## Roadmap

- [ ] Dedicated site detail page (plans + activities summary)
