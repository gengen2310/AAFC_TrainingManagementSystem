import { test, expect } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";
import { loginPW } from "../e2e-login-helper";

const BACKEND = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(BACKEND);
});

/**
 * Planning Workspace is module-only. Authentication belongs to Main TMS and
 * the shared backend session; this suite protects that architecture instead of
 * exercising the retired standalone React login/dashboard shell.
 */
test.describe("Planning Workspace session entry", () => {
  test("unauthenticated entry shows session handoff guidance, not a second login", async ({ page }) => {
    await page.goto("/planning");

    await expect(page.getByRole("heading", { name: "Session not found" })).toBeVisible();
    await expect(page.getByText(/return to the Training Management System and log in first/i)).toBeVisible();
    await expect(page.getByRole("link", { name: "Return to TMS" })).toBeVisible();
    await expect(page.getByRole("button", { name: /log in/i })).toHaveCount(0);
    await expect(page.getByLabel("Access code")).toHaveCount(0);
  });

  test("squadron admin shared session opens the planning module", async ({ page }) => {
    await loginPW(page, "ADMIN703");

    await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible();
    await expect(page.getByRole("heading", { name: "Session not found" })).toHaveCount(0);
    await expect(page.getByLabel("Access code")).toHaveCount(0);
  });

  test("read-only squadron role can enter without gaining write-only setup controls", async ({ page }) => {
    await loginPW(page, "703SQN2026");

    await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible();
    // The guided setup action is deliberately write-gated by canWriteSquadron.
    await expect(page.getByRole("button", { name: /set up year|guided/i })).toHaveCount(0);
  });

  for (const actor of [
    { label: "Wing Admin", code: "ADMIN7WG" },
    { label: "National Admin", code: "ADMINNATIONAL" },
    { label: "System Admin", code: "SYSADMIN2026" },
  ]) {
    test(`${actor.label} must choose a squadron before planning data is shown`, async ({ page }) => {
      await loginPW(page, actor.code);

      const selector = page.getByLabel("Viewing squadron");
      await expect(selector).toBeVisible();
      await expect(page.getByText(/select a squadron above to view its Planning Workspace/i)).toBeVisible();

      // React Query wingOverview fetch is async — wait for at least one real option
      await expect.poll(
        () => selector.locator("option[value]").count(),
        { timeout: 10000, message: "squadron selector options did not load" },
      ).toBeGreaterThan(0);
      const values = await selector.locator("option").evaluateAll(options =>
        options.map(o => (o as HTMLOptionElement).value).filter(Boolean),
      );
      expect(values.length).toBeGreaterThan(0);
      await selector.selectOption(values[0]);

      await expect(selector).toHaveValue(values[0]);
      await expect(page.getByText(/select a squadron above to view its Planning Workspace/i)).toHaveCount(0, { timeout: 10000 });
    });
  }

  test("backend logout invalidates the module session", async ({ page }) => {
    const { token } = await loginPW(page, "ADMIN703");

    const logout = await page.request.post(`${BACKEND}/api/auth/logout`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(logout.ok()).toBeTruthy();

    // page.addInitScript() is sticky — it re-fires on any reload or navigation of
    // this page, restoring aafc_token to sessionStorage. Open a fresh tab in the
    // same context instead: no inherited initScript, no sessionStorage token,
    // and the session cookie was cleared by the logout response.
    const freshPage = await page.context().newPage();
    await freshPage.goto("/planning");
    await expect(freshPage.getByRole("heading", { name: "Session not found" })).toBeVisible({ timeout: 10000 });
    await expect(freshPage.getByLabel("Access code")).toHaveCount(0);
    await freshPage.close();
  });
});
