#!/usr/bin/env node
/**
 * Capture CSR Insight UI screenshots for documentation.
 * Requires: backend on :5001, frontend on :4200, Playwright WebKit.
 *
 * Setup (one-time):
 *   npm install --no-save playwright@latest
 *   npx playwright install webkit
 *
 * Usage: node scripts/capture-screenshots.mjs
 *
 * Optional env: SCREENSHOT_PLAN_ID, SCREENSHOT_ACTIVITY_ID, SCREENSHOT_REALIZED_ID
 */
import { webkit } from 'playwright';
import { mkdir } from 'fs/promises';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = join(ROOT, 'screenshot');
const BASE = 'http://localhost:4200';

const IDS = {
  plan: process.env.SCREENSHOT_PLAN_ID ?? '6f8b990b-f6f8-490e-8a5c-9b755e93417d',
  activity: process.env.SCREENSHOT_ACTIVITY_ID ?? '79853774-9a6c-4b15-9d62-6bab490f7ac5',
  realized: process.env.SCREENSHOT_REALIZED_ID ?? 'd912c16f-5466-409f-8c61-a187ca45ff48',
};

async function ensureDir(filePath) {
  await mkdir(dirname(filePath), { recursive: true });
}

async function save(page, relativePath, opts = {}) {
  const path = join(OUT, relativePath);
  await ensureDir(path);
  await page.screenshot({
    path,
    fullPage: opts.fullPage ?? false,
    ...opts,
  });
  console.log('✓', relativePath);
}

async function goto(page, route, waitMs = 2500) {
  await page.goto(`${BASE}${route}`, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(waitMs);
}

async function login(page, email, password) {
  await goto(page, '/login', 1000);
  await page.fill('#email', email);
  await page.fill('#password', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/(dashboard|csr-plans)/, { timeout: 45000 });
  await page.waitForTimeout(1500);
}

async function scrollShot(page, relativePath, y) {
  await page.evaluate((scrollY) => window.scrollTo(0, scrollY), y);
  await page.waitForTimeout(400);
  await save(page, relativePath);
}

async function launchBrowser() {
  return webkit.launch({ headless: true });
}

async function main() {
  const browser = await launchBrowser();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });

  // --- Login (public) ---
  await goto(page, '/login', 2000);
  await save(page, 'auth/interface-login.png');

  await login(page, 'admin@test.com', 'admin123');

  // --- Dashboard / Power BI ---
  await goto(page, '/dashboard', 5000);
  await save(page, 'dashboard/interface-dashboard.png');
  await save(page, 'PowerBI/dashboard-csr-performance-overview.png');
  await goto(page, '/dashboard/corporate', 5000);
  await save(page, 'PowerBI/dashboard-csr-budget-analytics.png');
  await goto(page, '/dashboard/site', 5000);
  await save(page, 'PowerBI/dashboard-csr-impact-analytics.png');

  // --- Plans ---
  await goto(page, '/csr-plans', 3000);
  await save(page, 'plan/interface annual plan.png');
  await goto(page, `/csr-plans/${IDS.plan}`, 3000);
  await save(page, 'plan/plan-details-1.png');
  await scrollShot(page, 'plan/plan-details-2.png', 700);

  // --- Planned activities ---
  await goto(page, '/planned-activities', 3000);
  await save(page, 'all-activities/interface activities.png');
  await goto(page, `/planned-activity/${IDS.activity}`, 3000);
  await save(page, 'activities-details/planned-activity-details-1.png');
  await scrollShot(page, 'activities-details/planned-activity-details-2.png', 700);

  // --- Reports ---
  await goto(page, '/realized-csr', 3000);
  await save(page, 'report/interface reports.png');
  await goto(page, `/realized-csr/${IDS.realized}`, 3000);
  await save(page, 'report/report-details-1.png');
  await scrollShot(page, 'report/report-details-2.png', 500);
  await scrollShot(page, 'report/report-details-3.png', 1000);
  await scrollShot(page, 'report/report-details-4.png', 1500);
  await save(page, 'activities-details/report-activity-details.png');

  // --- Documents ---
  await goto(page, '/documents', 3000);
  await save(page, 'document/interface documents.png');

  // --- Corporate admin ---
  await goto(page, '/sites', 2500);
  await save(page, 'sites/interface-sites.png');
  await goto(page, '/categories', 2500);
  await save(page, 'categories/interface-categories.png');
  await goto(page, '/admin/users', 2500);
  await save(page, 'admin/interface-users.png');
  await goto(page, '/admin/audit', 2500);
  await save(page, 'admin/interface-audit.png');

  // --- Change requests ---
  await goto(page, '/changes', 2500);
  await save(page, 'changes/interface-changes.png');
  await goto(page, '/changes/pending', 2500);
  await save(page, 'changes/interface-changes-pending.png');
  await goto(page, '/changes/history', 2500);
  await save(page, 'changes/interface-changes-history.png');

  // --- Profile ---
  await goto(page, '/account/profile', 2500);
  await save(page, 'profile/interface-profile.png');

  // --- Validation ---
  await goto(page, '/annual-plans/validation', 2500);
  await save(page, 'plan/interface-plan-validation.png');

  await browser.close();
  console.log('\nDone — screenshots saved under screenshot/');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
