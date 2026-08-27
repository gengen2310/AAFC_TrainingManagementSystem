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
  await expect(page.locator("#acct-tabs")).toBeVisible({ timeout: 15000 });
}

// Reference Data now lives behind the Configuration tab, so tests that touch it
// must open the tab first. Two further waits are needed after that: the rows are
// drawn by _renderRefData() (before which getElementById returns null), and they
// render a "counting..." placeholder before _refDataCounts() supplies the number.
// Waiting for only one of the three stages made a test race look like a product bug.
async function openConfigTab(page: Page) {
  await page.click("#acct-tab-config");
  await expect(page.locator("#refdata-count-subjarea")).toBeVisible({ timeout: 15000 });
  await expect(page.locator("#refdata-count-subjarea")).toHaveText(/\d+\s*active/, { timeout: 15000 });
}

test("REFDATA-01: all six datasets appear as grouped summary rows, not stacked editors", async ({ page }) => {
  await loginSquadron(page);
  await openConfigTab(page);

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
  await openConfigTab(page);

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
  await openConfigTab(page);

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

// ── Nesting / containment ────────────────────────────────────────────────────
// Three cards on this page opened a <div> inside an <h2> and then wrote
// </h2></div> in that order. The parser force-closed the div at </h2>, leaving
// the </div> to close #page-accounts early -- so the Units, Flights and
// Reference Data cards were siblings of the page rather than children of it.
//
// Reference Data ended up a direct child of <body>, which meant nav() could not
// hide it: once you opened Account Management it stayed on screen on Curriculum,
// Activities, Parade Nights and Dashboard. Measured on the unfixed build, that
// is what "I don't like having the screen below" was describing.
//
// getComputedStyle(child).display does NOT become "none" when an ancestor is
// hidden, so these assertions use real visibility (offsetParent + box height).
// The first version of this check used computed display and reported the bug as
// still present after it was fixed.
test("REFDATA-04: the configuration cards live inside the Accounts page and leave with it", async ({ page }) => {
  await loginSquadron(page);

  for (const id of ["acct-units-card", "acct-flights-card", "acct-refdata-card"]) {
    const inside = await page.evaluate(
      (i) => !!document.getElementById("page-accounts")?.contains(document.getElementById(i)),
      id,
    );
    expect(inside, `${id} must be inside #page-accounts`).toBe(true);
  }

  const reallyVisible = () =>
    page.evaluate(() => {
      const e = document.getElementById("acct-refdata-card");
      if (!e) return false;
      return e.offsetParent !== null && e.getBoundingClientRect().height > 0;
    });

  await page.click("#acct-tab-config");
  await expect.poll(reallyVisible, { timeout: 10000 }).toBe(true);

  // Navigating away must take it with the page.
  for (const p2 of ["curriculum", "activities", "dashboard"]) {
    await page.evaluate((x) => nav(x), p2);
    await expect.poll(reallyVisible, { timeout: 5000 }).toBe(false);
  }
});

test("REFDATA-05: the Configuration tab is scoped and does not fight other tab bars", async ({ page }) => {
  await loginSquadron(page);

  await page.click("#acct-tab-config");
  await expect(page.locator("#acct-tab-config")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#acct-tab-accounts")).toHaveAttribute("aria-selected", "false");

  // Curriculum's setCurrTab clears .active on EVERY .tab-btn in the document.
  // These buttons must not be collateral damage, and vice versa.
  await page.evaluate(() => nav("curriculum"));
  const curriculumActive = await page.locator("#page-curriculum .tab-btn.active").count();
  expect(curriculumActive).toBe(1);

  await page.evaluate(() => nav("accounts"));
  await expect(page.locator("#acct-tabs .tab-btn.active")).toHaveCount(1);
});
