import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

// Wing/National Command Dashboard (Sections A/B) -- previously had zero
// Planning Workspace consumer at all (GET /api/dashboard/command). Now
// rendered on WingOverview/NationalOverview via the shared
// CommandDashboardSection component.
test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000");
});

test("wing_admin sees the Command Dashboard on Wing Assurance", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMIN7WG");
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Command Dashboard/i)).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("A1 — Next parade night readiness")).toBeVisible();
  await expect(page.getByText("A2 — Eight-week risk forecast")).toBeVisible();
  await expect(page.getByText("B1 — Training delivered each week")).toBeVisible();
});

test("national_admin sees the Command Dashboard on National Assurance", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMINNATIONAL");
  await expect(page.getByRole("heading", { name: /national assurance/i })).toBeVisible({ timeout: 10000 });
  // .first() -- REM-72's own wing-drill-down selector label also contains
  // "Command Dashboard", making this text ambiguous on National Assurance
  // specifically (it isn't on Wing Assurance, which has no such selector).
  await expect(page.getByText(/Command Dashboard/i).first()).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("A3 — Immediate issues requiring support")).toBeVisible();
  await expect(page.getByText("B4 — Cancellation and non-delivery causes")).toBeVisible();
});

// REM-72 residual: national_admin previously had no UI control to view one
// specific wing's Command Dashboard from National Assurance -- the backend
// already supported a wing_id param and CommandDashboardSection already
// accepted a wingId prop, only the selector itself was missing.
test("national_admin can drill the Command Dashboard into one specific wing", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMINNATIONAL");
  await expect(page.getByRole("heading", { name: /national assurance/i })).toBeVisible({ timeout: 10000 });

  const select = page.getByLabel("Command Dashboard scope");
  await expect(select).toBeVisible({ timeout: 10000 });
  await expect(select.locator("option").first()).toHaveText("All Wings (national)");

  // Default is the national aggregate.
  const initialTitle = page.getByText(/Command Dashboard — National/i);
  await expect(initialTitle).toBeVisible();

  // Selecting a specific wing switches the section's own title from
  // "National" to "Wing" -- the clearest, most direct proof the wingId prop
  // is actually reaching the API call, not just a cosmetic no-op selector.
  // options[0] is always "All Wings" (empty value); options[1] is the first
  // real wing -- the seeded data always has at least 7 Wing.
  const options = await select.locator("option").all();
  const wingValue = await options[1].getAttribute("value");
  await select.selectOption(wingValue!);
  await expect(page.getByText(/Command Dashboard — Wing/i)).toBeVisible({ timeout: 10000 });

  // Switching back to "All Wings" returns to the national aggregate.
  await select.selectOption("");
  await expect(page.getByText(/Command Dashboard — National/i)).toBeVisible({ timeout: 10000 });
});

test("Purpose, measure & action info toggle expands chart narrative", async ({ page }) => {
  await page.goto("/");
  await loginPW(page, "ADMIN7WG");
  await expect(page.getByText(/Command Dashboard/i)).toBeVisible({ timeout: 10000 });
  const toggle = page.getByRole("button", { name: "Purpose, measure & action" }).first();
  await toggle.click();
  await expect(page.getByText("Purpose").first()).toBeVisible();
  await expect(page.getByText("Measure").first()).toBeVisible();
});
