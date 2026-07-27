import { test, Page } from "@playwright/test";

// Formal staging screenshot evidence for the Planning Workspace preview
// service, captured against the ACTUAL deployed module-mode build (not a
// local Vite dev server, which serves the non-module "full app" build and
// would misrepresent what real users see). Run with:
//   npx playwright test --config=playwright.planning.staging.config.ts e2e-connected/capture-screenshots-planning.spec.ts
//
// Auth: the Planning Workspace preview domain has no login form of its own in
// module mode (ModuleEntry shows NotAuthenticated / redirects) -- per
// .claude/rules/architecture.md, the real cross-origin handoff is the
// aafc_session cookie (SameSite=None; Secure) set by Main TMS's own login.
// This spec logs into Main TMS staging first (same browser context, so the
// cookie persists), then navigates to the Planning Workspace staging domain,
// reproducing the actual production auth path rather than a same-origin
// shortcut.
const SHA = process.env.CAPTURE_SHA || "unknown-sha";
const OUT = `/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source/artifacts/general-release/${SHA}/staging`;
const MAIN_TMS = "https://aafc-tms-frontend-staging.up.railway.app";
const PLANNING = "https://aafc-tms-planning-workspace-preview-staging.up.railway.app";

async function loginViaMainTms(page: Page, code: string) {
  await page.goto(MAIN_TMS);
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await page.locator(".ph-title", { hasText: "Training Dashboard" }).waitFor({ timeout: 10000 });
}

test("capture Planning Workspace desktop + drawer tabs (deployed module-mode build)", async ({ page }) => {
  await loginViaMainTms(page, "ADMIN703");
  await page.goto(PLANNING);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/planning-workspace-desktop.png`, fullPage: true });

  // Bottom drawer is collapsed by default (PlanningWorkspace.tsx bottomOpen=false) --
  // open it via its toggle button before the tab buttons exist in the DOM.
  const drawerToggle = page.getByRole("button", { name: /Activities\s*▲/ });
  if (await drawerToggle.count()) {
    await drawerToggle.click();
    await page.waitForTimeout(500);
  }

  // Drawer tabs (the actually-reachable surface in module mode)
  for (const tab of ["Activities", "Mission Backlog", "Facilitators", "Rooms", "Equipment", "Holidays", "Notices"]) {
    const tabBtn = page.getByRole("button", { name: tab, exact: true });
    if (await tabBtn.count()) {
      await tabBtn.first().click();
      await page.waitForTimeout(600);
      const slug = tab.toLowerCase().replace(/\s+/g, "-");
      await page.screenshot({ path: `${OUT}/planning-drawer-${slug}.png`, fullPage: true });
    }
  }
});

test("capture Planning Workspace mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loginViaMainTms(page, "ADMIN703");
  await page.goto(PLANNING);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${OUT}/planning-workspace-mobile.png`, fullPage: true });
});

test("EVIDENCE: /facilitator-schedule redirects to /planning on the deployed module-mode build (GAP-14)", async ({ page }) => {
  // Facilitator Schedule Explorer (FacilitatorSchedule.tsx, FacilitatorTimeline.tsx,
  // GET /api/dashboard/facilitator-schedule) is fully built and tested at the API
  // layer (see backend/tests/test_facilitator_schedule.py), but the deployed
  // Planning Workspace preview service always runs MODULE_MODE=true, whose
  // ModuleEntry only registers "/planning" + a catch-all redirect back to it
  // (frontend/src/App.tsx:110-122) -- so this route is unreachable in production,
  // the same class of defect as GAP-13 (TRGO-05's CSV import UI). This test
  // captures the actual observed behaviour as evidence, not a synthetic claim.
  await loginViaMainTms(page, "ADMIN703");
  await page.goto(`${PLANNING}/facilitator-schedule`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/gap14-facilitator-schedule-redirect-evidence.png`, fullPage: true });
  console.log(`[GAP-14 evidence] final URL after navigating to /facilitator-schedule: ${page.url()}`);
});

test("capture Planning Workspace high-contrast theme (forced, no discoverable UI toggle)", async ({ page }) => {
  // tokens.css defines a data-theme="hc" variant, but no UI control to activate it
  // was found anywhere in frontend/src -- forcing it via JS to at least capture
  // that the theme itself renders correctly, and noting the missing toggle
  // separately as a smaller, distinct finding.
  await loginViaMainTms(page, "ADMIN703");
  await page.goto(PLANNING);
  await page.waitForTimeout(1500);
  await page.evaluate(() => { document.documentElement.setAttribute("data-theme", "hc"); });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${OUT}/planning-workspace-high-contrast.png`, fullPage: true });
});

test("capture Planning Workspace at 125% and 150% zoom", async ({ page }) => {
  await loginViaMainTms(page, "ADMIN703");
  for (const scale of [1.25, 1.5]) {
    await page.goto(PLANNING);
    await page.waitForTimeout(1500);
    await page.evaluate((s) => { (document.body.style as any).zoom = String(s); }, scale);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/planning-workspace-zoom-${Math.round(scale * 100)}.png`, fullPage: true });
  }
});
