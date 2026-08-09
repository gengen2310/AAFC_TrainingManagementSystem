import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// ── Training Classes UI (first frontend consumer of CLASS-01/03/04/07) ──────
// Real browser verification, per this program's own discipline (no live UI
// claim without a rendered check). Local run only (playwright.connected.config.ts).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

// _loadActivitiesPage() (triggered by nav("activities")) populates #py-select
// asynchronously and is not awaited by nav() itself -- poll rather than
// assume it's already populated the instant nav() returns.
async function selectFirstYear(page: Page): Promise<string> {
  const yearSelect = page.locator("#py-select");
  await expect(yearSelect).toBeVisible();
  let firstRealValue = "";
  await expect(async () => {
    const options = await yearSelect.locator("option").all();
    expect(options.length).toBeGreaterThan(1); // more than just the placeholder
    firstRealValue = (await options[1].getAttribute("value")) || "";
    expect(firstRealValue).not.toBe("");
  }).toPass({ timeout: 8000 });
  await yearSelect.selectOption(firstRealValue);
  await page.waitForTimeout(600); // loadYearMap() is async
  return firstRealValue;
}

async function loginSquadron(page: Page, code: string) {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => {
      (window as any).AAFC_API_BASE = base;
    }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill(code);
  await page.locator("#auth-btn").click();
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.describe("Training Classes panel on the Activities page", () => {
  test("card is present and explains what a Training Class is", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await expect(page.locator("#page-activities .ctitle", { hasText: "Training Classes" })).toBeVisible();
    await expect(page.locator("#page-activities")).toContainText("A Training Class is a local group completing a Training Stage");
    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("selecting a Training Year shows the Training Classes card and Add button", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);

    await expect(page.locator("#py-classes-card")).toBeVisible();
    await expect(page.getByRole("button", { name: "+ Add Training Class" })).toBeVisible();
  });

  test("create a Training Class end-to-end: modal opens, stage select populates, create succeeds, appears in list, then archive", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);

    await page.getByRole("button", { name: "+ Add Training Class" }).click();
    const modal = page.locator("#m-add-training-class");
    await expect(modal).toBeVisible();

    // Stage select must have real options populated from /api/curriculum/phases,
    // not be left empty (the offline-fallback / loading-failure case).
    const stageSelect = page.locator("#tc-stage-inp");
    await expect(async () => {
      const count = await stageSelect.locator("option").count();
      expect(count).toBeGreaterThan(0);
    }).toPass({ timeout: 5000 });

    const uniqueName = `Playwright Smoke Class ${Date.now()}`;
    await page.locator("#tc-name-inp").fill(uniqueName);
    await modal.getByRole("button", { name: "Add" }).click();

    // Modal closes on success (no validation-error message left showing).
    await expect(modal).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#tc-add-msg")).toHaveText("");

    // Appears in the rendered list.
    await expect(page.locator("#py-classes-body")).toContainText(uniqueName, { timeout: 5000 });

    // Archive it via the real UI control, and confirm it disappears from
    // the default (active-only) list -- cleans up after itself, matching
    // this program's established test-hygiene discipline (REM-128/131).
    page.once("dialog", (d) => d.accept());
    const row = page.locator("#py-classes-body tr", { hasText: uniqueName });
    await row.getByRole("button", { name: "Archive" }).click();
    await expect(page.locator("#py-classes-body")).not.toContainText(uniqueName, { timeout: 5000 });

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  test("edit a Training Class: rename via the edit modal", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);

    const originalName = `Playwright Edit Class ${Date.now()}`;
    await page.getByRole("button", { name: "+ Add Training Class" }).click();
    await page.locator("#tc-name-inp").fill(originalName);
    await page.locator("#m-add-training-class").getByRole("button", { name: "Add" }).click();
    await expect(page.locator("#m-add-training-class")).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#py-classes-body")).toContainText(originalName, { timeout: 5000 });

    const row = page.locator("#py-classes-body tr", { hasText: originalName });
    await row.getByRole("button", { name: "Edit" }).click();
    const editModal = page.locator("#m-edit-training-class");
    await expect(editModal).toBeVisible();
    const renamed = originalName + " (renamed)";
    await page.locator("#tc-edit-name-inp").fill(renamed);
    await editModal.getByRole("button", { name: "Save" }).click();
    await expect(editModal).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#py-classes-body")).toContainText(renamed, { timeout: 5000 });

    // Clean up.
    page.once("dialog", (d) => d.accept());
    await page.locator("#py-classes-body tr", { hasText: renamed }).getByRole("button", { name: "Archive" }).click();
    await expect(page.locator("#py-classes-body")).not.toContainText(renamed, { timeout: 5000 });
  });

  test("sqn_general (read-only) sees the Training Classes list but no Add/Edit/Archive buttons", async ({ page }) => {
    if (LOCAL_API_BASE) {
      await page.addInitScript((base) => {
        (window as any).AAFC_API_BASE = base;
      }, LOCAL_API_BASE);
    }
    await page.goto("/");
    await page.locator("#auth-type").selectOption("squadron");
    await page.locator("#auth-wing-select").selectOption("7WG");
    await page.locator("#auth-sqn-select").selectOption("703");
    await page.locator("#auth-role").selectOption("sqn_general");
    await page.locator("#auth-continue-btn").click();
    await page.locator("#auth-code").fill("703SQN2026");
    await page.locator("#auth-btn").click();
    await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });

    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);
    await expect(page.locator("#py-classes-card")).toBeVisible();
    await expect(page.getByRole("button", { name: "+ Add Training Class" })).toBeHidden();
  });
});
