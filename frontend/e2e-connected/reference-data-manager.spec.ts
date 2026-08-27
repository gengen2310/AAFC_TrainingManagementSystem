import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Reference Data used to render all six datasets stacked down the Account
// Management card, repeating tags -> input -> "+ Add" -> "Show archived" six
// times. It now shows one summary row per dataset, grouped, with a Manage
// button that opens a shared modal.
//
// The refactor is presentational. _loadRefList, _addRefItem, _archiveRefItem,
// _restoreRefItem, _naturalRefScope and the canWrite gate are untouched -- the
// modal body carries the same refdata-*-${key} ids the inline block used, so
// those handlers keep working, including their esc()/_jsAttr escaping.
//
// These tests exist because that claim is only true while the ids match. If
// someone renames one, the summary card still renders and only the editing
// breaks, which is exactly the kind of silent half-failure this codebase has
// produced before (REM-146, REM-148).

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

declare const S: any;
declare const _REFDATA_TYPES: any[];
declare function api(path: string, opts?: any): Promise<any>;
declare function nav(id: string): void;
declare function openRefDataManager(key: string): void;
declare function closeRefDataManager(): void;
declare function _loadRefList(t: any): Promise<void>;
declare function _addRefItem(key: string): Promise<void>;

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
  await expect(page.locator("#app")).toBeVisible({ timeout: 15000 });
  await page.evaluate(() => nav("accounts"));
  await expect(page.locator("#acct-refdata-card")).toBeVisible({ timeout: 15000 });
  // Two waits, because there are two stages. The card becomes visible before
  // _renderRefData() draws the rows (else getElementById returns null), and the
  // rows draw with a "counting..." placeholder before _refDataCounts() fills in
  // the real number. Waiting only for the first made a test race look like a
  // product bug.
  await expect(page.locator("#refdata-count-subjarea")).toBeVisible({ timeout: 15000 });
  await expect(page.locator("#refdata-count-subjarea")).toHaveText(/\d+\s*active/, { timeout: 15000 });
}

test("REFDATA-01: all six datasets appear as grouped summary rows, not stacked editors", async ({ page }) => {
  await loginSquadron(page);

  // Every dataset has a summary row with a count.
  const keys = await page.evaluate(() => _REFDATA_TYPES.map((t) => t.key));
  expect(keys).toHaveLength(6);
  for (const k of keys) {
    await expect(page.locator(`#refdata-count-${k}`)).toBeVisible();
    await expect(page.locator(`#refdata-count-${k}`)).not.toHaveText(/counting/, { timeout: 10000 });
  }

  // The three groups are present. Matched case-insensitively: the headings are
  // styled text-transform:uppercase, and innerText() returns rendered text.
  const text = await page.locator("#refdata-sections").innerText();
  expect(text).toMatch(/training configuration/i);
  expect(text).toMatch(/people configuration/i);
  expect(text).toMatch(/resource configuration/i);

  // And crucially: no inline editor is left stacked on the card.
  await expect(page.locator('#refdata-sections [id^="refdata-new-"]')).toHaveCount(0);
});

test("REFDATA-02: Manage opens the editor, and add / archive / show-archived all still work", async ({ page }) => {
  await loginSquadron(page);

  const name = `Probe Area ${Date.now()}`;

  // Read the active count BEFORE opening the modal. Reading it while the modal
  // is up returned "" for a hidden element, which made the later comparison
  // compare "" with "" and fail for the wrong reason.
  const activeBefore = await page.evaluate(() => {
    const m = (document.getElementById("refdata-count-subjarea")!.textContent || "").match(/(\d+)\s*active/);
    return m ? Number(m[1]) : -1;
  });
  expect(activeBefore).toBeGreaterThanOrEqual(0);

  await page.evaluate(() => openRefDataManager("subjarea"));
  await expect(page.locator("#refdata-modal-title")).toHaveText("Subject Areas");
  await expect(page.locator("#refdata-new-subjarea")).toBeVisible();
  await expect(page.locator("#refdata-show-archived-subjarea")).toBeAttached();

  await page.fill("#refdata-new-subjarea", name);
  await page.evaluate(() => _addRefItem("subjarea"));
  await expect(page.locator("#refdata-list-subjarea")).toContainText(name);

  // Closing must refresh the summary count, or the card lies about what you just did.
  await page.evaluate(() => closeRefDataManager());
  await expect
    .poll(async () => page.evaluate(() => {
      const m = (document.getElementById("refdata-count-subjarea")!.textContent || "").match(/(\d+)\s*active/);
      return m ? Number(m[1]) : -1;
    }), { timeout: 10000 })
    .toBe(activeBefore + 1);

  // Archive it, then bring it back with Show archived.
  await page.evaluate(() => openRefDataManager("subjarea"));
  await expect(page.locator("#refdata-list-subjarea")).toContainText(name);
  const id = await page.evaluate(async (n) => {
    const items = await api("/api/subject-area-tags?include_archived=true");
    return items.find((i: any) => i.display_name === n).tag_id;
  }, name);
  await page.evaluate(async (i) => {
    const t = _REFDATA_TYPES.find((x) => x.key === "subjarea");
    await api(t.archiveUrl(i), { method: t.archiveMethod });
    await _loadRefList(t);
  }, id);
  await expect(page.locator("#refdata-list-subjarea")).not.toContainText(name);

  await page.check("#refdata-show-archived-subjarea");
  await expect(page.locator("#refdata-list-subjarea")).toContainText(name);
});

test("REFDATA-03: a squadron admin still cannot archive a value owned by a higher scope", async ({ page }) => {
  await loginSquadron(page);

  // Training Stages ships national/global entries a squadron must not touch.
  await page.evaluate(() => openRefDataManager("phase"));
  await expect(page.locator("#refdata-list-phase")).toBeVisible();

  const rows = await page.evaluate(async () => {
    const t = _REFDATA_TYPES.find((x) => x.key === "phase");
    const items = await api(t.listUrl);
    const mine = (S.session || {}).squadron_id;
    return items.map((it: any) => ({
      scope: t.ownScopeName(it[t.scopeField]),
      ownedByMe: it.squadron_id === mine,
    }));
  });

  const higherScope = rows.filter((r: any) => r.scope !== "squadron");
  expect(higherScope.length).toBeGreaterThan(0);

  // Higher-scope entries render without an archive control. The count of
  // archive buttons must never exceed the number of rows this squadron owns.
  const archiveButtons = await page.locator('#refdata-list-phase [onclick^="_archiveRefItem"]').count();
  const ownRows = rows.filter((r: any) => r.scope === "squadron" && r.ownedByMe).length;
  expect(archiveButtons).toBeLessThanOrEqual(ownRows);
});
