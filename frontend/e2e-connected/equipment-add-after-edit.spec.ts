import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// "+ Add Equipment" must not inherit state from a previous "Edit".
//
// Same defect as the activities one (REM-147): editEquipId was cleared only on
// the PATCH branch of saveEquip(), and the "+ Add Equipment" button called
// openModal('m-add-equip') directly with no reset -- so Edit -> close -> Add ->
// Save renamed the item opened earlier instead of adding a new one.
//
// Rooms, sixty lines away in the same file, already had openAddRoomModal()
// doing exactly this reset. Equipment never got the equivalent. This test pins
// it so the two stay in step.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// connected-frontend declares state and handlers as top-level script bindings,
// not window properties -- `window.S` is undefined, `S` is not.
declare const S: any;
declare const editEquipId: string | null;
declare function api(path: string, opts?: any): Promise<any>;
declare function editEquip(id: string): void;
declare function openAddEquipModal(): void;
declare function closeModal(id: string): void;
declare function saveEquip(): Promise<void>;
declare function reloadAndRender(): Promise<void>;

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000"
  );
});

async function loginSquadron(page: Page, code = "ADMIN703") {
  if (LOCAL_API_BASE) {
    await page.addInitScript((base) => { (window as any).AAFC_API_BASE = base; }, LOCAL_API_BASE);
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

async function seedEquipment(page: Page, name: string): Promise<string> {
  return await page.evaluate(async (n) => {
    await api("/api/equipment", { method: "POST", body: JSON.stringify({ name: n, quantity: 3 }) });
    await reloadAndRender();
    return S.equip.find((e: any) => e.name === n).id;
  }, name);
}

test("EQUIP-ADD-01: + Add Equipment after cancelling an Edit adds a new item and leaves the edited one alone", async ({ page }) => {
  await loginSquadron(page);

  const victimName = `Radio Set ${Date.now()}`;
  const victimId = await seedEquipment(page, victimName);
  const countBefore = await page.evaluate(() => S.equip.length);

  await page.evaluate((id) => editEquip(id), victimId);
  await expect(page.locator("#equip-modal-title")).toHaveText("Edit Equipment");
  await page.evaluate(() => closeModal("m-add-equip"));

  await page.evaluate(() => openAddEquipModal());
  await expect(page.locator("#equip-modal-title")).toHaveText("+ Add Equipment");
  await expect(page.locator("#equip-name")).toHaveValue("");
  expect(await page.evaluate(() => editEquipId)).toBeNull();

  await page.locator("#equip-name").fill("Brand New Equipment");
  await page.evaluate(async () => { await saveEquip(); });

  const after = await page.evaluate(async () => {
    await reloadAndRender();
    return S.equip.map((e: any) => ({ id: e.id, name: e.name }));
  });

  expect(after.length).toBe(countBefore + 1);
  expect(after.some((e: any) => e.name === "Brand New Equipment")).toBe(true);
  expect(after.find((e: any) => e.id === victimId)?.name).toBe(victimName);
});

test("EQUIP-ADD-02: editing still updates in place and does not create a stray item", async ({ page }) => {
  await loginSquadron(page);

  const name = `Tent ${Date.now()}`;
  const id = await seedEquipment(page, name);
  const countBefore = await page.evaluate(() => S.equip.length);

  await page.evaluate((i) => editEquip(i), id);
  await expect(page.locator("#equip-name")).toHaveValue(name);
  await page.locator("#equip-name").fill(`${name} (renamed)`);
  await page.evaluate(async () => { await saveEquip(); });

  const after = await page.evaluate(async () => {
    await reloadAndRender();
    return S.equip.map((e: any) => ({ id: e.id, name: e.name }));
  });

  expect(after.length).toBe(countBefore);
  expect(after.find((e: any) => e.id === id)?.name).toBe(`${name} (renamed)`);
  await expect(page.locator("#equip-modal-title")).toHaveText("+ Add Equipment");
  expect(await page.evaluate(() => editEquipId)).toBeNull();
});
