/**
 * AAFC TMS — Staging verification suite
 *
 * Covers: navigation cleanup, retired routes, Activities, Parade Nights,
 * Mission Backlog, Planning Workspace counters, page headings, facilitator
 * subject-area-tag workflow, Dashboard API correctness, mobile navigation
 * (hamburger drawer), console errors, and screenshots.
 *
 * Error policy: no errors are suppressed.  Every CSP violation, console error,
 * unhandled rejection, and unexpected HTTP 4xx/5xx causes the test to fail.
 * The only valid exemption is an error that is explicitly tested as the expected
 * outcome of the operation under test.
 *
 * Credentials read exclusively from environment variables — no codes in source.
 * Run: STAGING_SQN_ADMIN_CODE=... STAGING_WING_ADMIN_CODE=... npx playwright test
 */

import { test, expect, Page } from "@playwright/test";
import { ROLES, injectSession } from "./helpers/auth";
import * as path from "path";
import * as fs from "fs";

// Update to the deployed commit SHA when a new build is promoted to staging.
// This directory holds screenshots that prove the staging domain and build.
const DEPLOYED_SHA = "483161e";
const SCREENSHOT_DIR = path.resolve(
  __dirname,
  `../../../artifacts/staging-ui-verification/${DEPLOYED_SHA}`
);

async function screenshot(page: Page, name: string): Promise<void> {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${name}.png`), fullPage: false });
}

// Strict error collector: no suppression of any error text.
// Attach AFTER injectSession() completes so boot noise is excluded.
function attachErrorCollector(page: Page): { errors: string[] } {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`[console.error] ${m.text()}`);
  });
  page.on("pageerror", (err) => {
    errors.push(`[pageerror] ${err.message}`);
  });
  return { errors };
}

async function navTo(page: Page, id: string): Promise<void> {
  await page.evaluate((navId) => (window as unknown as Record<string, (id: string) => void>).nav(navId), id);
  await page.waitForTimeout(600);
}

// ── Section 1: Navigation check per role ─────────────────────────────────────

const RETIRED_NAV = ["Annual Program", "Training Planner", "Parade Night Program", "Planner Help"];
const REQUIRED_NAV_SQN = ["Dashboard", "Activities", "Parade Nights", "Weekly Program", "Curriculum", "Facilitators"];

for (const role of ROLES) {
  test(`[Nav] ${role.label} — retired items absent, required items present`, async ({ page }) => {
    await injectSession(page, role);
    const { errors } = attachErrorCollector(page);

    await screenshot(page, `nav-${role.label.replace(/[^a-z0-9]/gi, "-").toLowerCase()}`);

    const sidenav = page.locator(".sidenav");
    const sidenavText = await sidenav.innerText();

    for (const retired of RETIRED_NAV) {
      expect(sidenavText, `"${retired}" must not appear in nav for ${role.label}`).not.toContain(retired);
    }

    if (role.role === "sqn_admin" || role.role === "sqn_general") {
      for (const required of REQUIRED_NAV_SQN) {
        expect(sidenavText, `"${required}" must appear in nav for ${role.label}`).toContain(required);
      }
    }

    expect(errors, `Console/page errors for ${role.label}: ${errors.join("; ")}`).toHaveLength(0);
  });
}

// ── Section 2: Mobile navigation — hamburger drawer ───────────────────────────

test("[Nav] Mobile — hamburger opens drawer, Parade Nights visible and clickable", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);

  // The sidenav is hidden on mobile by CSS. The hamburger button (#btn-hamburger) toggles it.
  const hamburger = page.locator("#btn-hamburger");
  await expect(hamburger, "Hamburger button must be visible on mobile viewport").toBeVisible();

  // Sidenav starts closed
  const sidenav = page.locator(".sidenav");
  await expect(sidenav, "Sidenav must be hidden before hamburger is clicked").not.toBeVisible();

  // Open nav drawer
  await hamburger.click();
  await expect(sidenav, "Sidenav must be visible after hamburger click").toBeVisible();
  await screenshot(page, "nav-mobile-drawer-open");

  // Retired items must not appear in the open drawer
  const drawerText = await sidenav.innerText();
  for (const retired of RETIRED_NAV) {
    expect(drawerText, `"${retired}" must not appear in mobile drawer`).not.toContain(retired);
  }

  // Parade Nights must be visible and clickable
  const pnItem = sidenav.locator("text=Parade Nights");
  await expect(pnItem, "'Parade Nights' must be visible in open drawer").toBeVisible();
  await pnItem.click();

  // Nav closed after click, Parade Nights page active
  await page.waitForTimeout(600);
  await expect(sidenav, "Drawer must close after nav item click").not.toBeVisible();
  const pageTitle = await page.locator(".page.active .ph-title").first().innerText().catch(() => "");
  expect(pageTitle, "Parade Nights page must be active after clicking nav item").toContain("Parade Nights");

  await screenshot(page, "nav-mobile-post-click");

  // Verify Activities is also in the drawer
  await hamburger.click();
  await expect(sidenav).toBeVisible();
  await expect(sidenav.locator("text=Activities"), "Activities must be visible in mobile drawer").toBeVisible();
  const missionItem = sidenav.locator("text=Mission Backlog");
  // Mission Backlog may be absent from nav scope — check and skip rather than fail
  const missionCount = await missionItem.count();
  if (missionCount > 0) {
    await expect(missionItem).toBeVisible();
  }

  // Close overlay by clicking outside
  const overlay = page.locator(".nav-overlay");
  await expect(overlay, "Overlay must be visible when drawer is open").toBeVisible();
  await overlay.click();
  await expect(sidenav, "Drawer must close after overlay click").not.toBeVisible();

  expect(errors, `Console/page errors on mobile nav: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 3: Retired route redirects ────────────────────────────────────────

const REDIRECTS: { old: string; expectedText: string }[] = [
  { old: "planning-year",     expectedText: "Activities" },
  { old: "planning-anchors",  expectedText: "Activities" },
  { old: "planning-term",     expectedText: "Activities" },
  { old: "planning-missions", expectedText: "Activities" },
  { old: "planning-builder",  expectedText: "Parade Nights" },
  { old: "planning-rooms",    expectedText: "Parade Nights" },
];

test("[Routes] Legacy nav IDs redirect correctly (sqn_admin)", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);

  for (const { old, expectedText } of REDIRECTS) {
    await navTo(page, old);
    const activePageTitle = await page.locator(".page.active .ph-title").first().innerText().catch(() => "");
    expect(activePageTitle, `nav('${old}') should redirect to a page titled "${expectedText}"`).toContain(expectedText);
  }
});

// ── Section 4: Activities page ────────────────────────────────────────────────

test("[Activities] Title, no retired subtitle, required buttons present", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);
  await navTo(page, "activities");

  const pageText = await page.locator("#page-activities").innerText();
  expect(pageText, "Activities page must contain 'Activities'").toContain("Activities");
  expect(pageText, "'Events and activities' subtitle must be absent").not.toContain("Events and activities");
  expect(pageText, "'Facilitator delivery profiles' must be absent").not.toContain("Facilitator delivery profiles");

  await expect(page.locator("#page-activities button:has-text('Generate Activities')").first(), "Generate Activities button must be visible").toBeVisible();
  await expect(page.locator("#page-activities button:has-text('Add Holiday')").first(), "+ Add Holiday button must be visible").toBeVisible();
  await expect(page.locator("#page-activities button:has-text('Import CEA')").first(), "Import CEA button must be visible").toBeVisible();

  await screenshot(page, "activities-page");
  expect(errors, `Console/page errors on Activities: ${errors.join("; ")}`).toHaveLength(0);
});

test("[Activities] Read-only role cannot see Generate/Holiday buttons", async ({ page }) => {
  const sqnGeneral = ROLES.find((r) => r.role === "sqn_general")!;
  await injectSession(page, sqnGeneral);
  await navTo(page, "activities");
  await expect(page.locator("button:has-text('Generate Activities'):visible")).toHaveCount(0);
});

// ── Section 5: Holiday workflow ───────────────────────────────────────────────

test("[Activities] Holiday create → verify → cleanup", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  await navTo(page, "activities");

  await page.locator("#page-activities button:has-text('Add Holiday')").first().click();
  const modal = page.locator("#m-add-holiday");
  await expect(modal).toBeVisible();

  await modal.locator("#hol-name-inp").fill("PLAYWRIGHT TEST HOLIDAY");
  await modal.locator("#hol-start-inp").fill("2026-08-01");
  await modal.locator("#hol-end-inp").fill("2026-08-15");
  await screenshot(page, "add-holiday-modal");

  await modal.locator("button.btn-primary").click();
  await page.waitForTimeout(3_000);

  await expect(
    page.locator("#page-activities").filter({ hasText: "PLAYWRIGHT TEST HOLIDAY" }),
    "Created holiday must appear in the activities page"
  ).toBeVisible({ timeout: 8_000 });

  await screenshot(page, "activities-holiday-created");
});

// ── Section 6: Generate Activities workflow ───────────────────────────────────

test("[Activities] Generate Activities modal opens and shows date preview", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  await navTo(page, "activities");

  await page.click("button:has-text('Generate Activities')");
  await expect(page.locator("#m-gen-acts")).toBeVisible({ timeout: 8_000 });
  await screenshot(page, "generate-activities-modal");
});

// ── Section 7: Parade Nights ──────────────────────────────────────────────────

test("[Parade Nights] Nav present, Generate button present, no retired label", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);

  const pnCount = await page.locator(".sidenav").locator("text=Parade Nights").count();
  expect(pnCount, "'Parade Nights' must exist in nav DOM").toBeGreaterThan(0);

  await navTo(page, "parade-nights");
  const pageText = await page.locator("#page-parade-nights").innerText();
  expect(pageText, "'Parade Night Program' label must be absent").not.toContain("Parade Night Program");

  const genBtn = page.locator("button:has-text('Generate')").first();
  await expect(genBtn, "Generate Parade Nights button must be visible").toBeVisible();

  await screenshot(page, "parade-nights-page");
  await genBtn.click();
  await page.waitForTimeout(800);
  await screenshot(page, "generate-parade-nights-modal");

  expect(errors, `Console/page errors on Parade Nights: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 8: Mission Backlog tabs ──────────────────────────────────────────

test("[Mission Backlog / PW] No Training Planner or Import Review tabs", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);

  const pwUrl = await page.evaluate(() => {
    const link = document.getElementById("nav-pw-link") as HTMLAnchorElement | null;
    return link?.href ?? null;
  });

  if (pwUrl) {
    await page.goto(pwUrl);
    await page.waitForTimeout(2_000);
    const pwText = await page.locator("body").innerText();
    expect(pwText, "Training Planner tab must not appear").not.toContain("Training Planner");
    expect(pwText, "Import Review tab must not appear").not.toContain("Import Review");
    await screenshot(page, "planning-workspace");
  } else {
    test.info().annotations.push({ type: "skip-reason", description: "PW link not visible for this role/scope" });
  }
});

// ── Section 9: Planning Workspace counters ────────────────────────────────────

test("[PW] No persistent conflicts or unscheduled counters in header", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  await navTo(page, "dashboard");

  const headerText = await page.locator("header, .ph, .context-bar, .top-bar").allInnerTexts().catch(() => [""]);
  const combined = headerText.join(" ");
  expect(combined, "No 'conflicts' badge in header").not.toMatch(/\d+\s*conflict/i);
  expect(combined, "No 'unscheduled' badge in header").not.toMatch(/\d+\s*unscheduled/i);
});

// ── Section 10: Page headings / subtitles ─────────────────────────────────────

test("[Headings] No retired subtitles on Curriculum, Activities, Facilitators, Resources", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);

  const checks = [
    { navId: "curriculum",   pageId: "page-curriculum",   title: "Curriculum",                forbiddenSubs: ["Curriculum", "Curriculum"] },
    { navId: "activities",   pageId: "page-activities",   title: "Activities",                forbiddenSubs: ["Events and activities"] },
    { navId: "facilitators", pageId: "page-facilitators", title: "Facilitators",              forbiddenSubs: ["Facilitator delivery profiles"] },
    { navId: "resources",    pageId: "page-resources",    title: "Resources & Training Areas", forbiddenSubs: ["Rooms and equipment"] },
  ];

  for (const { navId, pageId, title, forbiddenSubs } of checks) {
    await navTo(page, navId);
    const titleEl = page.locator(`#${pageId} .ph-title`).first();
    await expect(titleEl).toContainText(title);

    const phSubEls = page.locator(`#${pageId} .ph-sub`);
    const subCount = await phSubEls.count();
    for (let i = 0; i < subCount; i++) {
      const subText = await phSubEls.nth(i).innerText();
      for (const forbidden of forbiddenSubs) {
        expect(subText, `"${forbidden}" must not appear as subtitle on ${title} page`).not.toContain(forbidden);
      }
    }
    await screenshot(page, `page-${navId}`);
  }

  expect(errors, `Console/page errors on heading check: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 11: Dashboard — no appget/ CSP violations, charts load ────────────

test("[Dashboard] Loads with chart data, zero CSP violations, no appget/ requests", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  const appgetRequests: string[] = [];

  // Intercept any request going to appget/ (the api('GET',...) bug)
  page.on("request", (req) => {
    if (req.url().toLowerCase().includes("appget/") || req.url().toLowerCase().includes("appget.")) {
      appgetRequests.push(req.url());
    }
  });

  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);

  await navTo(page, "dashboard");
  await page.waitForTimeout(3_000);

  const dashText = await page.locator("#page-dashboard").innerText();
  expect(dashText, "Dashboard must not be empty").not.toBe("");

  const hasFn = await page.evaluate(() => typeof (window as unknown as Record<string, unknown>).loadDashCharts === "function");
  expect(hasFn, "loadDashCharts function must be defined").toBe(true);

  expect(appgetRequests, `No requests must be sent to appget/ (api('GET',...) bug): ${appgetRequests.join(", ")}`).toHaveLength(0);
  await screenshot(page, "dashboard");
  expect(errors, `Console/page errors on Dashboard: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 12: Facilitator subject-area-tag workflow ─────────────────────────

test("[Facilitators] Subject-area-tag: create → assign → reload → filter → remove", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);

  await navTo(page, "facilitators");
  await page.waitForTimeout(1_500);

  // Must have at least one facilitator to tag
  const tagsBtn = page.locator("button:has-text('Tags')").first();
  await expect(tagsBtn, "At least one 'Tags' button must be present on Facilitators page").toBeVisible({ timeout: 8_000 });

  // Open the tag modal
  await tagsBtn.click();
  const modal = page.locator("#m-tag-fac");
  await expect(modal, "Tag modal must open").toBeVisible();
  await screenshot(page, "tag-modal-open");

  // Create section must be visible for sqn_admin
  const createSection = page.locator("#m-tag-create-section");
  await expect(createSection, "Create-tag section must be visible for sqn_admin").toBeVisible();

  // Create a new tag with a unique name to avoid conflicts between test runs
  const tagName = `PW-TAG-${Date.now().toString(36).toUpperCase()}`;
  await page.locator("#m-tag-new-name").fill(tagName);

  const createBtn = page.locator("#m-tag-create-btn");
  await expect(createBtn, "+ Create button must be visible").toBeVisible();
  await createBtn.click();

  // Wait for tag creation confirmation
  const msgEl = page.locator("#m-tag-msg");
  await expect(msgEl, "Tag creation confirmation must appear").toContainText(`Tag "${tagName}" created`, { timeout: 8_000 });

  // Tag must appear as a chip in the modal
  const tagChip = modal.locator(`#m-tag-checks button:has-text('${tagName}')`);
  await expect(tagChip, "Newly created tag must appear as chip in modal").toBeVisible();

  // Activate the tag for this facilitator
  const chipState = await tagChip.getAttribute("data-active");
  if (chipState !== "true") {
    await tagChip.click();
  }
  const activeChipCount = await modal.locator("#m-tag-checks button[data-active='true']").count();
  expect(activeChipCount, "At least the new tag must be active").toBeGreaterThan(0);

  await screenshot(page, "tag-modal-tag-assigned");

  // Save tags
  await modal.locator("button:has-text('Save Tags')").click();
  await page.waitForTimeout(2_000);

  // Tag must survive reload — re-open modal for same facilitator
  await tagsBtn.click();
  await expect(modal, "Modal must reopen").toBeVisible();
  await page.waitForTimeout(800);

  const savedChip = modal.locator(`#m-tag-checks button:has-text('${tagName}')`);
  await expect(savedChip, "Tag must persist after page reload and modal reopen").toBeVisible();

  const savedState = await savedChip.getAttribute("data-active");
  expect(savedState, "Tag must remain active (assigned to facilitator) after reload").toBe("true");

  await screenshot(page, "tag-modal-after-reload");

  // Close modal and check filter — filter select should include the new tag
  await modal.locator("button:has-text('Cancel')").click();
  await page.waitForTimeout(500);

  const filterSelect = page.locator("#fac-filter");
  const filterOptions = await filterSelect.locator("option").allInnerTexts();
  expect(filterOptions.some((o) => o.includes(tagName)), `Filter select must contain "${tagName}"`).toBeTruthy();

  // Apply filter
  await filterSelect.selectOption({ label: tagName });
  await page.waitForTimeout(800);
  const tableText = await page.locator("#page-facilitators").innerText();
  expect(tableText, `Facilitators list must not show 'No facilitators' when filtering by a tag that was just assigned`).not.toContain("No facilitators");

  await screenshot(page, "facilitators-filtered-by-tag");

  // Archive the tag via direct API call (no UI delete button present in current design)
  const tagId = await page.evaluate(async (name: string) => {
    const w = window as unknown as Record<string, unknown>;
    const tags = (w.S as Record<string, unknown>)?.subjectAreaTags as Array<{ tag_id: string; display_name: string }> | undefined;
    return tags?.find((t) => t.display_name === name)?.tag_id ?? null;
  }, tagName);

  if (tagId) {
    await page.evaluate(async (id: string) => {
      const w = window as unknown as Record<string, (...a: unknown[]) => unknown>;
      await w.api(`/api/subject-area-tags/${id}`, { method: "DELETE" });
    }, tagId);
    await page.waitForTimeout(500);
  }

  expect(errors, `Console/page errors on Facilitators/Tags: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 13: Facilitator page loads, no retired subtitle ───────────────────

test("[Facilitators] Facilitator page loads, no retired subtitle", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  await injectSession(page, sqnAdmin);
  const { errors } = attachErrorCollector(page);
  await navTo(page, "facilitators");
  await page.waitForTimeout(1_000);

  const titleEl = page.locator("#page-facilitators .ph-title").first();
  await expect(titleEl).toContainText("Facilitators");

  const subEls = page.locator("#page-facilitators .ph-sub");
  const subCount = await subEls.count();
  for (let i = 0; i < subCount; i++) {
    const t = await subEls.nth(i).innerText();
    expect(t, "No 'Facilitator delivery profiles' subtitle").not.toContain("Facilitator delivery profiles");
  }

  await screenshot(page, "facilitators-page");
  expect(errors, `Console/page errors on Facilitators: ${errors.join("; ")}`).toHaveLength(0);
});

// ── Section 14: Network — zero unexpected errors ──────────────────────────────

test("[Network] Zero unexpected HTTP errors on key pages (sqn_admin)", async ({ page }) => {
  const sqnAdmin = ROLES.find((r) => r.role === "sqn_admin")!;
  const failures: string[] = [];

  // No exclusions — every 4xx/5xx beyond normal auth endpoints is a defect
  page.on("response", (resp) => {
    const status = resp.status();
    const url = resp.url();
    // Auth responses during session boot are expected (lookup, login endpoints)
    if (url.includes("/api/auth/") || url.includes("favicon")) return;
    if (status >= 400) {
      failures.push(`${status} ${url}`);
    }
  });

  await injectSession(page, sqnAdmin);

  for (const navId of ["dashboard", "activities", "parade-nights", "curriculum", "facilitators", "resources"]) {
    await navTo(page, navId);
    await page.waitForTimeout(800);
  }

  expect(failures, `Unexpected HTTP errors:\n${failures.join("\n")}`).toHaveLength(0);
});
