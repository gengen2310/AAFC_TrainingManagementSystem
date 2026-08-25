import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// "+ Add Activity" must not inherit state from a previous "Edit".
//
// _editActId was set by editAct() and cleared ONLY on a successful save. Closing
// the Edit modal left it set, and the "+ Add Activity" button called
// openModal('m-add-act') directly with no reset -- so Edit -> close -> Add ->
// Save issued a PATCH against the activity opened earlier instead of a POST.
// The user saw "activity saved" and got no new activity; the one they had
// merely looked at was silently overwritten with the new values.
//
// Reproduced in a real browser before the fix: the activity was renamed and no
// new record was created.
//
// The modal title was part of why this stayed invisible. editAct() set
// '#act-modal-title', which does not exist -- the element is '#m-add-act-title'
// -- so the header still read "+ Add Activity" while the form was in edit mode.
// Both are fixed together here; the title is the tell, not the defect.

// connected-frontend declares its state and handlers as top-level script
// bindings, not window properties -- `window.S` is undefined, `S` is not.
// These declare the page-context globals used inside page.evaluate below.
declare const S: any;
declare const _editActId: string | null;
declare function api(path: string, opts?: any): Promise<any>;
declare function editAct(id: string): void;
declare function openAddActModal(): void;
declare function closeModal(id: string): void;
declare function saveAct(): Promise<void>;
declare function reloadAndRender(): Promise<void>;

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000"
  );
});

async function loginSquadron(page: Page, code = "ADMIN703") {
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
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

/** Create one activity through the page's own handler and return its id. */
async function seedActivity(page: Page, name: string): Promise<string> {
  return await page.evaluate(async (n) => {
    await api("/api/activities", {
      method: "POST",
      body: JSON.stringify({ activity_name: n, date_start: "2031-06-10", activity_type: "Optional" }),
    });
    await reloadAndRender();
    return S.acts.find((a: any) => a.name === n).id;
  }, name);
}

test("ACT-EDIT-01: + Add Activity after cancelling an Edit creates a new activity and leaves the edited one alone", async ({ page }) => {
  await loginSquadron(page);

  const victimName = `Field Craft ${Date.now()}`;
  const victimId = await seedActivity(page, victimName);
  const countBefore = await page.evaluate(() => S.acts.length);

  // Open Edit on it, then abandon the modal without saving.
  await page.evaluate((id) => editAct(id), victimId);
  await expect(page.locator("#m-add-act-title")).toHaveText("Edit Activity");
  await page.evaluate(() => closeModal("m-add-act"));

  // Now use the "+ Add Activity" button's own handler.
  await page.evaluate(() => openAddActModal());
  await expect(page.locator("#m-add-act-title")).toHaveText("+ Add Activity");
  await expect(page.locator("#act-name")).toHaveValue("");
  expect(await page.evaluate(() => _editActId)).toBeNull();

  await page.locator("#act-name").fill("Brand New Activity");
  await page.locator("#act-date").fill("2031-05-05");
  await page.evaluate(async () => { await saveAct(); });

  const after = await page.evaluate(async () => {
    await reloadAndRender();
    return S.acts.map((a: any) => ({ id: a.id, name: a.name }));
  });

  // A new activity exists...
  expect(after.length).toBe(countBefore + 1);
  expect(after.some((a: any) => a.name === "Brand New Activity")).toBe(true);
  // ...and the one merely opened for editing is untouched.
  expect(after.find((a: any) => a.id === victimId)?.name).toBe(victimName);
});

test("ACT-EDIT-02: editing still updates in place and does not create a stray activity", async ({ page }) => {
  await loginSquadron(page);

  const name = `Open Day ${Date.now()}`;
  const id = await seedActivity(page, name);
  const countBefore = await page.evaluate(() => S.acts.length);

  await page.evaluate((i) => editAct(i), id);
  await expect(page.locator("#act-name")).toHaveValue(name);
  await page.locator("#act-name").fill(`${name} (renamed)`);
  await page.evaluate(async () => { await saveAct(); });

  const after = await page.evaluate(async () => {
    await reloadAndRender();
    return S.acts.map((a: any) => ({ id: a.id, name: a.name }));
  });

  expect(after.length).toBe(countBefore);
  expect(after.find((a: any) => a.id === id)?.name).toBe(`${name} (renamed)`);
  // Save must hand the form back in a clean state for the next "+ Add".
  await expect(page.locator("#m-add-act-title")).toHaveText("+ Add Activity");
  expect(await page.evaluate(() => _editActId)).toBeNull();
});
