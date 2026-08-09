/**
 * Fix verification: PW-CTX-01, HOL-EDIT-01, HOL-TYPE-01, F-FUNC-01
 */
import { test, expect, Page } from "@playwright/test";
import { ROLES, injectSession } from "./helpers/auth";

const API = process.env.STAGING_API ?? "https://aafc-tms-backend-staging.up.railway.app";
const PW_BASE = "https://aafc-tms-planning-workspace-preview-staging.up.railway.app";

const SQN_ADMIN = ROLES.find((r) => r.role === "sqn_admin")!;
const SYS_ADMIN = ROLES.find((r) => r.role === "system_admin")!;
const WING_ADMIN = ROLES.find((r) => r.role === "wing_admin")!;
const NATIONAL_ADMIN = ROLES.find((r) => r.role === "national_admin")!;

// Navigate to Activities page and select the first available planning year.
// Returns false if no planning years exist on staging.
async function navToActivitiesYear(page: Page): Promise<boolean> {
  await page.evaluate(() => (window as any).nav("activities"));
  await page.waitForTimeout(2000);

  const pySelect = page.locator("#py-select");
  // #py-select is inside the active page — it resolves but CSS hides the whole page
  // if it's not active. Wait for the select to be inside a visible context.
  const isVis = await pySelect.isVisible().catch(() => false);
  if (!isVis) {
    // The Activities page might not be active yet — check via evaluate
    const activeId = await page.evaluate(() => document.querySelector(".page.active")?.id ?? "none");
    console.log("Active page after nav('activities'):", activeId);
  }

  // Use evaluate to read select options — avoids strict visibility check
  const optVals: string[] = await page.evaluate(() => {
    const sel = document.getElementById("py-select") as HTMLSelectElement | null;
    if (!sel) return [];
    return Array.from(sel.options).map((o) => o.value).filter((v) => v.trim());
  });
  console.log("Planning year options:", optVals);
  if (optVals.length === 0) return false;

  // Use evaluate to select the year and trigger loadYearMap
  await page.evaluate((id) => {
    const sel = document.getElementById("py-select") as HTMLSelectElement;
    sel.value = id;
    sel.dispatchEvent(new Event("change"));
  }, optVals[0]);
  await page.waitForTimeout(2500);
  return true;
}

// ── PW-CTX-01 ─────────────────────────────────────────────────────────────────
test("PW-CTX-01: Planning Workspace loads in module mode without crash", async ({ page }) => {
  // Log in via main TMS first (sets the aafc_session cookie for cross-origin PW handoff)
  await injectSession(page, SQN_ADMIN);

  const pageErrors: string[] = [];
  page.on("pageerror", (e) => pageErrors.push(e.message));

  // Navigate directly to PW — staging deploys with MODULE_MODE=true
  await page.goto(`${PW_BASE}/planning`);
  await page.waitForTimeout(3000);

  const body = await page.locator("body").innerText().catch(() => "");
  expect(body, "PW body must not show React error boundary text").not.toContain("Something went wrong");
  expect(body, "PW body must not be blank (crash leaves empty page)").not.toBe("");
  await expect(page.locator("#root"), "#root must not be empty — React must have mounted").not.toBeEmpty();
  // These three assertions alone previously also passed against the
  // NotAuthenticated "Session not found" screen (non-empty body, no crash
  // text, non-empty #root) -- that screen is a legitimate, different UI
  // state, not evidence the actual Planning Workspace content loaded. Assert
  // real workspace chrome is present so a broken cross-origin handoff (which
  // is exactly what this test's own auth setup silently had until 2026-08-08
  // — see the comment in helpers/auth.ts's injectSession) fails loudly.
  expect(body, "must not have silently landed on the cross-origin auth-handoff failure screen").not.toContain("Session not found");
  await expect(page.getByText("Select a squadron above").or(page.locator(".pw-ctx"))).toBeVisible({ timeout: 10000 });

  await page.screenshot({ path: "test-results/pw-ctx-01.png", fullPage: false });
  expect(pageErrors, `PW page errors: ${pageErrors.join("; ")}`).toHaveLength(0);
});

// ── PW-CTX-01 (P0 incident, 2026-08-08): wing/national scope, missing selector ────
//
// The test above only ever exercised sqn_admin, whose squadron is implicit
// (session.squadron_id) and never hits useScopedSquadron()'s needsSelection
// branch at all -- it could not have caught this. wing_admin/national_admin
// DO hit that branch, and the empty state told them to "Select a squadron
// above" while AppShell (the only thing that ever rendered SquadronSelector)
// is never mounted in MODULE_MODE at all -- there was no selector anywhere
// on the page, a genuine dead end. Fixed by rendering SquadronSelector
// inline in PlanningWorkspace.tsx's own empty state (frontend/src/routes/
// PlanningWorkspace.tsx) so it works regardless of which shell renders the
// route. This test would have failed before that fix (selector count 0,
// stuck on the prompt with no way to proceed) and must keep passing after.
for (const role of [WING_ADMIN, NATIONAL_ADMIN]) {
  test(`PW-CTX-01b: ${role.label} sees a working squadron selector in module-mode Planning Workspace`, async ({ page }) => {
    await injectSession(page, role);

    const pageErrors: string[] = [];
    page.on("pageerror", (e) => pageErrors.push(e.message));

    await page.goto(`${PW_BASE}/planning`);
    await page.waitForTimeout(3000);

    const body = await page.locator("body").innerText().catch(() => "");
    expect(body, "PW body must never show the provider-throw message").not.toContain(
      "useSquadronView must be used within SquadronViewProvider"
    );
    expect(body, "PW body must not show React error boundary text").not.toContain("Something went wrong");

    // The actual defect: no <select> anywhere let a wing/national user act on
    // "Select a squadron above". Assert a real, populated selector exists.
    const selector = page.locator("#sqn-view-select");
    await expect(selector, "squadron selector must be present and visible").toBeVisible({ timeout: 10000 });
    const optionCount = await selector.locator("option").count();
    expect(optionCount, "squadron selector must be populated with real squadrons, not just the placeholder").toBeGreaterThan(1);

    // Selecting a squadron must actually load the workspace, not stay stuck.
    const firstRealValue = await selector.locator("option").nth(1).getAttribute("value");
    await selector.selectOption(firstRealValue!);
    await page.waitForTimeout(2000);
    const bodyAfterSelect = await page.locator("body").innerText().catch(() => "");
    expect(bodyAfterSelect, "after selecting a squadron, the empty-state prompt must be gone").not.toContain(
      "Select a squadron above to view its Planning Workspace"
    );

    expect(pageErrors, `PW page errors: ${pageErrors.join("; ")}`).toHaveLength(0);
  });
}

// ── HOL-TYPE-01 ───────────────────────────────────────────────────────────────
test("HOL-TYPE-01: Add Holiday modal has type selector; list shows Type column", async ({ page }) => {
  await injectSession(page, SQN_ADMIN);
  const hasYear = await navToActivitiesYear(page);
  if (!hasYear) {
    test.skip(true, "No planning years on staging — cannot verify holiday UI");
    return;
  }

  // Add Holiday button is in the header (plan-write-el) — use evaluate to trigger
  const addHolVisible = await page.evaluate(() => {
    const btn = document.querySelector<HTMLElement>("button[onclick='openAddHolidayModal()']");
    return btn ? btn.style.display !== "none" : false;
  });
  console.log("HOL-TYPE-01: Add Holiday button visible:", addHolVisible);

  if (!addHolVisible) {
    // Trigger directly via evaluate
    await page.evaluate(() => (window as any).openAddHolidayModal());
  } else {
    await page.locator("button[onclick='openAddHolidayModal()']").first().click();
  }
  await page.waitForTimeout(500);

  // Type selector must be visible in the modal
  const typeSelect = page.locator("#hol-type-inp");
  await expect(typeSelect, "#hol-type-inp type selector must appear in Add Holiday modal").toBeVisible({ timeout: 5000 });
  const options = await typeSelect.locator("option").allInnerTexts();
  console.log("HOL-TYPE-01: type options =", options.join(", "));
  expect(options, "Must include School Holiday").toContain("School Holiday");
  expect(options, "Must include Public Holiday").toContain("Public Holiday");
  expect(options.length, "Must have more than 2 options").toBeGreaterThan(2);

  await page.screenshot({ path: "test-results/hol-type-01-modal.png", fullPage: false });

  // Close modal
  await page.locator("#m-add-holiday button").filter({ hasText: /cancel/i }).first().click();
  await page.waitForTimeout(400);

  // Check for Type column header in the holiday table
  const headers: string[] = await page.evaluate(() => {
    const ths = Array.from(document.querySelectorAll("#page-activities th"));
    return ths.map((th) => (th as HTMLElement).innerText);
  });
  console.log("HOL-TYPE-01: table headers =", headers.join(", "));
  expect(headers.join(" ").toUpperCase(), "Holiday table must have a TYPE column").toContain("TYPE");
});

// ── HOL-EDIT-01 ───────────────────────────────────────────────────────────────
test("HOL-EDIT-01: Edit button on holiday row opens modal; PATCH saves successfully", async ({ page }) => {
  await injectSession(page, SQN_ADMIN);
  const hasYear = await navToActivitiesYear(page);
  if (!hasYear) {
    test.skip(true, "No planning years on staging — cannot verify holiday edit");
    return;
  }

  // Check if any holidays exist; if not, add one
  const existingEditBtns = await page.evaluate(() =>
    document.querySelectorAll("button.btn-xs").length > 0
      ? Array.from(document.querySelectorAll("button.btn-xs"))
          .filter((b) => b.textContent?.trim() === "Edit").length
      : 0
  );

  if (existingEditBtns === 0) {
    // Add a test holiday via evaluate
    await page.evaluate(() => (window as any).openAddHolidayModal());
    await page.waitForTimeout(400);
    await page.locator("#hol-name-inp").fill("Edit Test Holiday");
    await page.locator("#hol-start-inp").fill("2026-12-20");
    await page.locator("#hol-end-inp").fill("2026-12-21");
    const modal = page.locator("#m-add-holiday");
    await modal.locator("button").filter({ hasText: /save|add/i }).last().click();
    await page.waitForTimeout(1500);
  }

  // Find and click Edit button on the first holiday row
  const editBtn = page.locator("button.btn-xs").filter({ hasText: /^edit$/i }).first();
  await expect(editBtn, "Edit button must exist on a holiday row").toBeVisible({ timeout: 8000 });
  await editBtn.click();
  await page.waitForTimeout(500);

  // Edit modal must open
  const modal = page.locator("#m-edit-holiday");
  await expect(modal, "#m-edit-holiday edit modal must open").toBeVisible({ timeout: 5000 });
  await expect(page.locator("#hol-edit-type"), "Type selector must exist in edit modal").toBeVisible();

  // Modify name and save. This edits whatever holiday row happens to be
  // first — often a real, long-lived seeded record (e.g. "Labour Day 2026"),
  // not one this test created — so the suffix must never be left in place
  // across runs. Same test-data-accumulation bug class as REM-128: repeated
  // un-reset runs previously grew the name past REM-127's 120-char limit
  // and turned this test into a permanent 422 failure.
  const nameField = page.locator("#hol-edit-name");
  const origName = await nameField.inputValue();
  const editedName = `${origName} (verified)`.slice(0, 120);
  await nameField.fill(editedName);

  const patchErrors: string[] = [];
  page.on("response", (r) => {
    if (r.url().includes("/api/planning/holidays/") && r.request().method() === "PATCH" && r.status() >= 400) {
      patchErrors.push(`PATCH → ${r.status()}`);
    }
  });

  await modal.locator("button").filter({ hasText: /save/i }).click();
  await page.waitForTimeout(1500);

  expect(patchErrors, `PATCH must not return error: ${patchErrors.join(", ")}`).toHaveLength(0);
  expect(await modal.isVisible(), "Edit modal must close after successful PATCH save").toBe(false);

  await page.screenshot({ path: "test-results/hol-edit-01.png", fullPage: false });

  // Revert the name so this test is idempotent across repeated runs instead
  // of accumulating " (verified)" onto the record indefinitely.
  await editBtn.click();
  await page.waitForTimeout(500);
  await expect(modal, "#m-edit-holiday edit modal must reopen for cleanup").toBeVisible({ timeout: 5000 });
  await nameField.fill(origName);
  await modal.locator("button").filter({ hasText: /save/i }).click();
  await page.waitForTimeout(1000);
});

// ── F-FUNC-01 ─────────────────────────────────────────────────────────────────
test("F-FUNC-01: national_viewer GET /api/audit returns 200 (not 403)", async ({ page }) => {
  const nvCode = process.env.STAGING_NATIONAL_VIEWER_CODE;

  if (!nvCode) {
    // Verify via system_admin (always has access) to confirm the endpoint is live and reachable
    await injectSession(page, SYS_ADMIN);
    // page.request is a Node.js context — pass the Bearer token explicitly
    const token = await page.evaluate(() => sessionStorage.getItem("aafc_token") ?? "");
    const resp = await page.request.get(`${API}/api/audit`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(resp.status(), "system_admin GET /api/audit must return 200").toBe(200);
    test.info().annotations.push({
      type: "incomplete",
      description: "STAGING_NATIONAL_VIEWER_CODE not provided — full fix requires national_viewer verification; system_admin path confirmed working",
    });
    return;
  }

  // Full verification: national_viewer must get 200 (was 403 before F-FUNC-01 fix)
  const NV_ROLE = { label: "National Viewer", unitType: "national", identifier: "", role: "national_viewer", envVar: "STAGING_NATIONAL_VIEWER_CODE" };
  await injectSession(page, NV_ROLE);
  const resp = await page.request.get(`${API}/api/audit`);
  expect(resp.status(), "national_viewer must get HTTP 200 from /api/audit (was 403 before fix)").toBe(200);
});
