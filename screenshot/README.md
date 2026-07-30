# UI Screenshots

PNG captures of the CSR Insight Angular app, used in [docs/index.html](../docs/index.html) and project documentation.

## Prerequisites

1. **Backend** running on `http://localhost:5001`
2. **Frontend** running on `http://localhost:4200` (with API proxy to the backend)
3. **Seed data** — default plan/activity/realized IDs in the script must exist in your database (or override via env vars below)

## Regenerate all screenshots

From the repository root:

```bash
npm install --no-save playwright@latest
npx playwright install webkit
node scripts/capture-screenshots.mjs
```

The script uses **Playwright WebKit** (headless). Chromium was avoided due to incomplete browser downloads in some environments.

## Test account

The script logs in as `admin@test.com` / `admin123` (corporate admin) after capturing the public login page.

## Optional environment variables

| Variable | Purpose |
|----------|---------|
| `SCREENSHOT_PLAN_ID` | UUID for plan detail screenshots |
| `SCREENSHOT_ACTIVITY_ID` | UUID for planned activity detail |
| `SCREENSHOT_REALIZED_ID` | UUID for realized CSR report detail |

## Output layout

| Folder | Screens |
|--------|---------|
| `auth/` | Login page |
| `dashboard/` | App shell after login |
| `PowerBI/` | Embedded Power BI dashboards (3 views) |
| `plan/` | Annual plans list, detail, validation |
| `all-activities/` | Planned activities list |
| `activities-details/` | Activity detail + report activity |
| `report/` | Realized CSR list and detail |
| `document/` | Documents library |
| `sites/`, `categories/` | Corporate admin |
| `admin/` | Users and audit log |
| `changes/` | Change requests (my, pending, history) |
| `profile/` | Account settings |

Total: **27** PNG files.
