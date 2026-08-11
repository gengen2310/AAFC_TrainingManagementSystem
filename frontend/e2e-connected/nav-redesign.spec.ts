import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// REM-25: connected-frontend's squadron-scope sidenav was reorganised around
// the Training Officer's actual planning cycle (Overview -> Plan Training ->
// Weekly Program -> People and Resources -> Needs Attention -> Settings)
// instead of the prior ad-hoc feature-area grouping (Overview/Training/
// People & Resources/Admin). Deliberately non-destructive: every existing
// page id/nav('id') target is unchanged, only grouping/order/labels moved --
// this suite proves every previously-reachable page is still reachable via
// the reorganised sidenav, and that role-based show/hide (applyNavScope())
// still works correctly on the new structure.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string, role: "sqn_admin" | "sqn_general" = "sqn_admin") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption(role);
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

test("sqn_admin: every squadron-scope page is still reachable via the reorganised sidenav, and new group headers/labels are present", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");

  // New group headers exist, in the expected order.
  const groups = ["Overview", "Plan Training", "People and Resources", "Needs Attention", "Settings"];
  for (const g of groups) {
    await expect(page.locator(".nav-lbl", { hasText: g })).toBeVisible();
  }
  // Relabelled item.
  await expect(page.getByRole("navigation").getByText("Training Calendar", { exact: true })).toBeVisible();
  // Old group header names are gone (regrouped, not just relabelled a subset).
  // .filter({hasText}) does substring matching -- exact equality needs a regex anchor.
  await expect(page.locator(".nav-lbl").filter({ hasText: /^Training$/ })).toHaveCount(0);
  await expect(page.locator(".nav-lbl").filter({ hasText: /^Admin$/ })).toHaveCount(0);

  // Every squadron-scope page id still exists and is reachable -- clicking
  // each nav item actually activates the matching page-{id} container.
  const pages: [string, string][] = [
    ["getting-started", "Getting Started"],
    ["dashboard", "Dashboard"],
    ["calendar", "Training Calendar"],
    ["curriculum", "Curriculum"],
    ["activities", "Activities"],
    ["parade-nights", "Parade Nights"],
    ["weekly-program", "Weekly Program"],
    ["facilitators", "Facilitators"],
    ["resources", "Locations and Resources"],
    ["action-items", "Needs Attention"],
    ["settings", "Unit Settings"],
    ["accounts", "Account Management"],
  ];
  for (const [id, label] of pages) {
    await page.locator(".nav-item", { hasText: label }).first().click();
    await expect(page.locator(`#page-${id}`)).toHaveClass(/active/, { timeout: 5000 });
  }
});

test("sqn_general (read-only): Settings and Account Management stay hidden under the new Settings group header", async ({ page }) => {
  await loginSquadron(page, "703SQN2026", "sqn_general");
  await expect(page.locator(".nav-item", { hasText: "Unit Settings" })).toBeHidden();
  await expect(page.locator(".nav-item", { hasText: "Account Management" })).toBeHidden();
  // The Settings group header itself must also hide when nothing in it is
  // visible (applyNavScope()'s sibling-walk label-hiding logic).
  await expect(page.locator(".nav-lbl", { hasText: "Settings" })).toBeHidden();
});
