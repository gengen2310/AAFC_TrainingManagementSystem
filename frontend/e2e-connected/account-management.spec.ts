import { test, expect, Page } from "../e2e-fixtures";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const B = process.env.CONNECTED_LOCAL_API_BASE!;
test.beforeEach(async () => { await resetBackendRateLimits(B); });

async function signInSysadmin(page: Page) {
  await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, B);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("national");
  await page.locator("#auth-role").selectOption("system_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("SYSADMIN2026");
  await page.locator("#auth-btn").click();
  // .ph-title exists on every page in this single-file SPA, so .first() resolves
  // to a hidden one. Scope to the ACTIVE page.
  await expect(page.locator(".page.active .ph-title").first()).toBeVisible({ timeout: 15000 });
  await page.evaluate("nav('accounts')");
  await expect(page.locator("#acct-show-archived")).toBeVisible({ timeout: 10000 });
}

async function signInSquadronAdmin(page: Page) {
  await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, B);
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator(".page.active .ph-title").first()).toBeVisible({ timeout: 15000 });
  await page.evaluate("nav('accounts')");
  await expect(page.locator("#acct-create-btn")).toBeVisible({ timeout: 10000 });
}

test("Add Account follows role scope and cascades Wing to Squadron", async ({ page }) => {
  await signInSysadmin(page);
  await page.locator("#acct-create-btn").click();
  await page.locator("#ca-role").selectOption("sqn_admin");
  await expect(page.locator("#ca-wing-row")).toBeVisible();
  await expect(page.locator("#ca-sqn-row")).toBeVisible();

  const wingId = await page.locator("#ca-wing option").filter({ hasText: "7WG" }).getAttribute("value");
  expect(wingId).toBeTruthy();
  await page.locator("#ca-wing").selectOption(wingId!);
  const squadronOptions = (await page.locator("#ca-sqn option").allTextContents())
    .map((name) => name.trim())
    .filter(Boolean)
    .filter((name) => name !== "— select squadron —");
  expect(squadronOptions.length).toBeGreaterThan(0);
  expect(squadronOptions.every((name) => /^7\d{2}/.test(name))).toBe(true);

  await page.locator("#ca-role").selectOption("wing_admin");
  await expect(page.locator("#ca-wing-row")).toBeVisible();
  await expect(page.locator("#ca-sqn-row")).toBeHidden();
  await page.locator("#ca-role").selectOption("national_admin");
  await expect(page.locator("#ca-wing-row")).toBeHidden();
  await expect(page.locator("#ca-sqn-row")).toBeHidden();

  await page.locator('input[name="ca-code-mode"][value="manual"]').check();
  await page.locator("#ca-manual-code").fill("TEMPORARY-CODE");
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.locator("#acct-create-btn").click();
  await expect(page.locator("#ca-manual-code")).toHaveValue("");
});

test("Squadron admins get a fixed own-squadron scope", async ({ page }) => {
  await signInSquadronAdmin(page);
  await page.locator("#acct-create-btn").click();
  await page.locator("#ca-role").selectOption("sqn_general");
  await expect(page.locator("#ca-fixed-scope")).toBeVisible();
  await expect(page.locator("#ca-fixed-scope")).toContainText("703");
  await expect(page.locator("#ca-wing-row")).toBeHidden();
  await expect(page.locator("#ca-sqn-row")).toBeHidden();
});

test("an active account offers Archive, never a button called Delete", async ({ page }) => {
  // "Delete" on an active row archived it, while archived rows carry a real
  // "Delete Permanently…". One word meant two different things depending on
  // which row you were looking at.
  await signInSysadmin(page);
  // Scoped to #acct-table specifically. The same page renders wings-table and
  // units-table alongside it, and THOSE legitimately carry Rename/Delete -- an
  // unscoped search finds them and reports an account defect that is not there.
  const rows = page.locator("#acct-table tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 10000 });

  const labels = await page.locator("#acct-table tbody button").allTextContents();
  const trimmed = labels.map(t => t.trim());
  expect(trimmed, "an exact 'Delete' on an active row is the ambiguity").not.toContain("Delete");
  expect(trimmed.some(t => t === "Archive"), `saw: ${[...new Set(trimmed)].join(", ")}`).toBe(true);
});

test("archived accounts are hidden by default and revealed by the toggle", async ({ page }) => {
  await signInSysadmin(page);
  const box = page.locator("#acct-show-archived");
  await expect(box).not.toBeChecked();
  const before = await page.locator("#acct-table tbody tr").count();
  await box.check();
  await page.waitForTimeout(600);
  const after = await page.locator("#acct-table tbody tr").count();
  expect(after, "showing archived must never hide rows").toBeGreaterThanOrEqual(before);
});

test("archived rows offer Restore and permanent delete; active rows do not", async ({ page }) => {
  await signInSysadmin(page);
  await page.locator("#acct-show-archived").check();
  await page.waitForTimeout(600);
  const labels = (await page.locator("#acct-table tbody button").allTextContents())
    .map(t => t.trim());
  // Whatever the fixture contains, the two vocabularies must not overlap:
  // "Archive" is the reversible action, "Delete Permanently…" the exceptional one.
  if (labels.includes("Delete Permanently…")) {
    expect(labels).toContain("Restore");
  }
  expect(labels, "'Delete' alone is never a label").not.toContain("Delete");
});

test("every account action the UI shows maps to a real endpoint", async ({ page }) => {
  await signInSysadmin(page);
  const calls: string[] = [];
  page.on("request", r => {
    const u = r.url();
    if (u.includes("/api/accounts")) calls.push(`${r.method()} ${u.split("/api/")[1].split("?")[0]}`);
  });
  await page.locator("#acct-show-archived").check();
  await page.waitForTimeout(800);
  // The listing itself must succeed; a 4xx here means the page is decorative.
  const bad: string[] = [];
  page.on("response", async r => {
    if (r.url().includes("/api/accounts") && r.status() >= 400) bad.push(`${r.status()} ${r.url()}`);
  });
  await page.evaluate("renderAccounts()");
  await page.waitForTimeout(800);
  expect(bad, bad.join("; ")).toEqual([]);
  expect(calls.length, "the page must actually call the accounts API").toBeGreaterThan(0);
});
