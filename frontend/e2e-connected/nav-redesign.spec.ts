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

test("sqn_general (read-only) reaches Settings, Account Management and Audit through the real nav, all read-only, with no Planning Workspace entry", async ({ page }) => {
  // Product decision 2026-09-28: sqn_general sees everything read-only and has
  // no Planning Workspace access. Navigate by clicking the real nav items --
  // calling nav() directly would bypass exactly the gating under test.
  await loginSquadron(page, "703SQN2026", "sqn_general");

  // Planning Workspace: every Main TMS entry point hidden.
  await expect(page.locator("#nav-pw-link")).toBeHidden();
  await expect(page.locator("#nav-pw-unconfigured")).toBeHidden();

  // Unit Settings: reachable, visible cards read-only, write/credential tools absent.
  await page.locator(".nav-item", { hasText: "Unit Settings" }).click();
  await expect(page.locator("#page-settings")).toHaveClass(/active/, { timeout: 5000 });
  await expect(page.locator("#settings-training-classes-wrap")).toBeVisible();
  await expect(page.locator("#settings-training-years-wrap")).toBeVisible();
  await expect(page.locator("#settings-custom-phases-wrap")).toBeVisible();
  await expect(page.locator("#s-addr")).toBeDisabled();
  await expect(page.locator("#page-settings button", { hasText: "Save Settings" })).toBeHidden();
  await expect(page.locator("#page-settings button", { hasText: "Open Planning Workspace" })).toBeHidden();
  await expect(page.locator("#page-settings .ctitle", { hasText: "Access Code" })).toBeHidden();
  await expect(page.locator("#user-dir-card")).toBeHidden();
  await expect(page.locator("#settings-custom-phases-wrap button:visible", { hasText: /^(Edit|Delete)$/ })).toHaveCount(0);

  // Account Management: reachable, no write controls.
  await page.locator(".nav-item", { hasText: "Account Management" }).click();
  await expect(page.locator("#page-accounts")).toHaveClass(/active/, { timeout: 5000 });
  await expect(page.locator("#acct-create-btn")).toBeHidden();
  await expect(page.locator("#page-accounts button:visible", { hasText: /^(Disable|Archive|Reset Code|Change Scope)$/ })).toHaveCount(0);

  // Audit: reachable and actually permitted (not the "cannot read" state).
  await page.locator(".nav-item", { hasText: "Audit" }).click();
  await expect(page.locator("#page-audit")).toHaveClass(/active/, { timeout: 5000 });
  await expect(page.locator("#audit-tbody")).not.toContainText("cannot read the audit log");
});
