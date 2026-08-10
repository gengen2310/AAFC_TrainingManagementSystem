import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-08: the Training Class picker inside CadetClassMembershipModal groups
// options by Training Stage (<optgroup>) and offers a text filter, instead of
// one long flat <select> -- confirmed via direct investigation that a real
// squadron's worth of accumulated classes across several Stages renders as a
// 100+ option flat list with no grouping at all without this. This test seeds
// two distinct Stages with two Training Classes each and proves both the
// grouping and the filter narrow correctly.

const API_BASE = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";

test.beforeAll(async () => {
  await resetBackendRateLimits(API_BASE);
});

const ADMIN_CODE = "ADMIN703";

async function authHeader(page: Page, code: string): Promise<Record<string, string>> {
  const r = await page.request.post(`${API_BASE}/api/auth/login`, { data: { code } });
  const token = (await r.json()).token as string;
  return { Authorization: `Bearer ${token}` };
}

test("Training Class picker: options are grouped by Stage and a text filter narrows them", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const suffix = String(Date.now());

  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;

  const years = await (await page.request.get(`${API_BASE}/api/planning/years`, { headers: hdr })).json();
  const yearId = years[0].planning_year_id as string;

  // Two distinct Stages, two Training Classes each -- enough to prove
  // grouping without depending on this dev DB's accumulated stage count.
  const stageAName = `CLASS-08-E2E-A-${suffix}`;
  const stageBName = `CLASS-08-E2E-B-${suffix}`;
  const stageARes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageAName, display_name: stageAName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  const stageBRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageBName, display_name: stageBName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageARes.ok()).toBe(true);
  expect(stageBRes.ok()).toBe(true);
  const stageAId = (await stageARes.json()).phase_id as string;
  const stageBId = (await stageBRes.json()).phase_id as string;

  const classNames = {
    a1: `CLASS-08-E2E ${suffix} Alpha One`,
    a2: `CLASS-08-E2E ${suffix} Alpha Two`,
    b1: `CLASS-08-E2E ${suffix} Bravo One`,
    b2: `CLASS-08-E2E ${suffix} Bravo Two`,
  };
  const classIds: string[] = [];
  for (const [stageId, name] of [
    [stageAId, classNames.a1],
    [stageAId, classNames.a2],
    [stageBId, classNames.b1],
    [stageBId, classNames.b2],
  ] as const) {
    const res = await page.request.post(`${API_BASE}/api/training-classes`, {
      data: { training_year_id: yearId, training_stage_id: stageId, display_name: name },
      headers: hdr,
    });
    expect(res.ok()).toBe(true);
    classIds.push((await res.json()).training_class_id as string);
  }

  await page.goto("/cadets");
  await expect(page.getByRole("heading", { name: "Cadets" })).toBeVisible({ timeout: 10000 });

  const firstManageBtn = page.getByRole("button", { name: "Manage" }).first();
  await expect(firstManageBtn).toBeVisible({ timeout: 8000 });
  await firstManageBtn.click();

  const modal = page.getByRole("dialog");
  await expect(modal).toBeVisible({ timeout: 5000 });

  const select = modal.locator("#ccm-class-select");

  // Grouping: both seeded stage names appear as distinct optgroup labels,
  // each containing exactly its own two classes.
  const groupA = select.locator(`optgroup[label="${stageAName}"]`);
  const groupB = select.locator(`optgroup[label="${stageBName}"]`);
  await expect(groupA).toHaveCount(1);
  await expect(groupB).toHaveCount(1);
  await expect(groupA.locator("option")).toHaveCount(2);
  await expect(groupB.locator("option")).toHaveCount(2);
  await expect(groupA.getByRole("option", { name: classNames.a1 })).toHaveCount(1);
  await expect(groupA.getByRole("option", { name: classNames.a2 })).toHaveCount(1);
  await expect(groupB.getByRole("option", { name: classNames.b1 })).toHaveCount(1);
  await expect(groupB.getByRole("option", { name: classNames.b2 })).toHaveCount(1);

  // Filter: narrowing to "Bravo" removes the Alpha optgroup entirely and
  // leaves only the two Bravo options under the Bravo optgroup.
  const filterInput = modal.locator("#ccm-class-filter");
  await filterInput.fill(`${suffix} Bravo`);
  await expect(select.locator(`optgroup[label="${stageAName}"]`)).toHaveCount(0);
  await expect(select.locator(`optgroup[label="${stageBName}"] option`)).toHaveCount(2);

  // Narrowing further to a single class name leaves exactly one option.
  await filterInput.fill(classNames.b1);
  await expect(select.locator("option")).toHaveCount(2); // "— choose —" + the one match
  await expect(select.getByRole("option", { name: classNames.b1 })).toHaveCount(1);

  // Adding still works end-to-end after filtering.
  await select.selectOption({ label: classNames.b1 });
  await modal.getByRole("button", { name: "Add" }).click();
  const row = modal.locator("li", { hasText: classNames.b1 });
  await expect(row).toBeVisible({ timeout: 8000 });
  await row.getByRole("button", { name: "End membership" }).click();
  await expect(row).toBeHidden({ timeout: 8000 });

  // Cleanup.
  for (const id of classIds) {
    await page.request.delete(`${API_BASE}/api/training-classes/${id}`, { headers: hdr });
  }
});
