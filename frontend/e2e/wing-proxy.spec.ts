import { test, expect } from "@playwright/test";

// ── Wing proxy workflow ───────────────────────────────────────────────────────
// Requires seeded ADMIN7WG and backend on :8000.

test("wing admin can enter and exit proxy mode", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("ADMIN7WG");
  await page.getByRole("button", { name: "Log in" }).click();
  // WingOverview renders <h1>Wing Assurance</h1>
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  // Select a squadron and enter proxy. Exact match: Block 8 added a second,
  // legitimate "Viewing squadron" selector (SquadronSelector) to the same nav
  // for read-only squadron browsing without proxy — /squadron/i now matches
  // both, so this must target the proxy-mode select specifically.
  await page.getByLabel("Squadron", { exact: true }).selectOption({ index: 1 });
  await page.getByPlaceholder(/reason/i).fill("Assisting squadron with planning");
  await page.getByRole("button", { name: /enter proxy/i }).click();
  await expect(page.getByText(/proxy mode active/i)).toBeVisible({ timeout: 5000 });
  // Exit proxy
  await page.getByRole("button", { name: /exit proxy/i }).click();
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 5000 });
});

test("wing viewer cannot enter proxy mode", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Access code").fill("7WG2026");
  await page.getByRole("button", { name: "Log in" }).click();
  // WingOverview renders <h1>Wing Assurance</h1>
  await expect(page.getByRole("heading", { name: /wing assurance/i })).toBeVisible({ timeout: 10000 });
  // Wing viewer sees the proxy entry button but it must be disabled (not clickable)
  await expect(page.getByRole("button", { name: /enter proxy/i })).toBeDisabled();
});
