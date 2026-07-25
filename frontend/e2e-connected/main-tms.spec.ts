import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// ── Connected-frontend (Main TMS) verification ──────────────────────────────
// Local run (playwright.connected.config.ts): targets localhost:8080, backend on
// localhost:8000. API base is overridden via addInitScript so the page's own
// <meta name="aafc-api-base"> (which points at production by default in source)
// is never edited on disk.
// Staging run (playwright.connected.staging.config.ts): targets the deployed
// staging URL directly; no override needed — docker-entrypoint.sh already
// rewrote the meta tag to the staging backend at container start.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// DEFECT-004 follow-up: playwright-global-setup.ts resets rate limits once
// per full suite invocation, which isn't always enough -- verified live that
// this file's own request volume, especially with other spec files having
// run immediately before it, can still cross the general API limiter's
// 300 req/60s budget partway through (observed as #auth-wing-select never
// getting populated -- a rate-limited /api/wings fetch, not a real login
// bug). A per-file reset gives this file its own fresh budget. Best-effort;
// see e2e-rate-limit-reset.ts for what this does and its known limitations.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.describe("Retired pages are gone", () => {
  test("no Annual Program / Training Planner / Parade Night Program / Planner Help nav items", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const navText = await page.locator(".nav-item, .nav-item-ext").allTextContents();
    for (const retired of ["Annual Program", "Training Planner", "Parade Night Program", "Planner Help", "Training Summary"]) {
      expect(navText.some(t => t.includes(retired))).toBe(false);
    }
  });
});

test.describe("Planning Workspace restoration", () => {
  test("Planning Workspace nav link is visible for sqn_admin and opens without a second login", async ({ page, context }) => {
    await loginSquadron(page, "ADMIN703");
    const pwLink = page.locator("#nav-pw-link");
    await expect(pwLink).toBeVisible();
    const [popup] = await Promise.all([
      context.waitForEvent("page"),
      pwLink.click(),
    ]);
    await popup.waitForLoadState();
    // No login form in the new tab — it should land directly on an authenticated view.
    await expect(popup.locator("text=Access code")).toHaveCount(0);
  });

  test("Planning Workspace link is hidden when PLANNING_WORKSPACE_URL is not configured", async ({ page }) => {
    // Simulate the unconfigured case by stubbing the ui-config response.
    await page.route("**/api/health/ui-config", route =>
      route.fulfill({ json: { planning_workspace_url: null, training_year: 2026, environment: "development" } })
    );
    await loginSquadron(page, "ADMIN703");
    await expect(page.locator("#nav-pw-link")).toBeHidden();
  });
});

test.describe("Activities page", () => {
  test("has Add Holiday and Import CEA, no separate Import Review tab", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await expect(page.locator("#page-activities .ph-title")).toHaveText("Activities");
    await expect(page.locator("#page-activities")).not.toContainText("Events and activities");
    await expect(page.getByRole("button", { name: "+ Add Holiday" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Import CEA" })).toBeVisible();
    await expect(page.getByText("Import Review", { exact: false })).toHaveCount(0);
  });

  test("Add Holiday modal has name, start, end, affects parade nights", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await page.getByRole("button", { name: "+ Add Holiday" }).click();
    await expect(page.locator("#hol-name-inp")).toBeVisible();
    await expect(page.locator("#hol-start-inp")).toBeVisible();
    await expect(page.locator("#hol-end-inp")).toBeVisible();
    await expect(page.locator("#hol-affects-inp")).toBeVisible();
  });
});

test.describe("Parade Nights — automatic generation", () => {
  test("generator modal has all required fields with correct labels", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("parade-nights"));
    await page.getByRole("button", { name: "Generate Parade Nights" }).click();
    const modal = page.locator("#m-gen-dates");
    for (const label of ["Repeat every", "Parade day", "Program start date", "Program end date",
      "Parade start time", "Parade finish time", "Excluded dates", "Skip existing holiday periods"]) {
      await expect(modal.getByText(label, { exact: false }).first()).toBeVisible();
    }
    const freqOptions = await page.locator("#gen-freq option").allTextContents();
    expect(freqOptions).toEqual(expect.arrayContaining(["Weekly", "Fortnightly", "Yearly"]));
    await expect(page.getByRole("button", { name: "Preview Parade Nights" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create Parade Nights" })).toBeVisible();
  });
});

test.describe("Facilitator statistics", () => {
  test("Facilitators page renders status, workload, coverage and gaps charts", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("facilitators"));
    await expect(page.locator("#page-facilitators .ph-title")).toHaveText("Facilitators");
    await expect(page.locator("#page-facilitators")).not.toContainText("Facilitator delivery profiles");
    await expect(page.locator("#fac-chart-status")).toBeVisible();
    await expect(page.locator("#fac-chart-workload")).toBeVisible();
    await expect(page.locator("#fac-chart-spof")).toBeVisible();
    await expect(page.locator("#fac-chart-gaps")).toBeVisible();
    // Named facilitator list must remain below the charts.
    await expect(page.locator("#fac-tbody tr").first()).toBeVisible();
  });
});

test.describe("Subtitle removal", () => {
  test("Curriculum, Resources pages have no duplicate subtitle", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("curriculum"));
    await expect(page.locator("#page-curriculum")).not.toContainText("Curriculum items");
    await page.evaluate(() => (window as any).nav("resources"));
    await expect(page.locator("#page-resources")).not.toContainText("Rooms and equipment");
  });
});

test.describe("System console does not leak onto other pages", () => {
  test("Resources page for sqn_admin shows no System Overview / Platform Health cards", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("resources"));
    // These sections belong to #page-system-console (correctly hidden via .page{display:none}
    // unless active) — still present in the DOM, so assert not-visible, not absent.
    await expect(page.getByText("System Overview")).not.toBeVisible();
    await expect(page.getByText("Platform Health")).not.toBeVisible();
    await expect(page.getByText("Scope Map")).not.toBeVisible();
  });
});

test.describe("Console and network hygiene", () => {
  test("Dashboard loads with no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", msg => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", err => errors.push(String(err)));
    await loginSquadron(page, "ADMIN703");
    await page.waitForTimeout(1500);
    expect(errors, `Console errors: ${errors.join("; ")}`).toEqual([]);
  });
});

test.describe("Mobile navigation", () => {
  test.use({ viewport: { width: 390, height: 844 } });
  test("hamburger menu opens and closes the sidenav, Planning Workspace link reachable", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    const hamburger = page.locator("#btn-hamburger");
    await expect(hamburger).toBeVisible();
    await hamburger.click();
    await expect(page.locator(".sidenav")).toHaveClass(/nav-open/);
    await expect(page.locator("#nav-pw-link")).toBeVisible();
    // Tap the overlay in the region beyond the sidenav's own width, not its center.
    await page.locator(".nav-overlay").click({ position: { x: 370, y: 400 } });
    await expect(page.locator(".sidenav")).not.toHaveClass(/nav-open/);
  });
});

test.describe("Read-only role", () => {
  test("sqn_general cannot edit but can view Planning Workspace link", async ({ page }) => {
    await loginSquadron(page, "703SQN2026", "sqn_general");
    await expect(page.locator("body")).toHaveClass(/readonly/);
    await expect(page.locator("#nav-pw-link")).toBeVisible();
  });
});
