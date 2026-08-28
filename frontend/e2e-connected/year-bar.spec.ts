import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// The Training Year is a time context, not a workflow object. These tests hold
// the design in docs/design/training-year-frontend-design.md to its own gates.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// The general limiter's 300 req/60s budget is crossed partway through this
// file: each test logs in and the page then fans out a dozen year-scoped
// loads. globalSetup's single reset is necessary but not sufficient -- the
// same reason main-tms.spec.ts carries its own reset.
test.beforeEach(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

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

async function openYearBar(page: Page) {
  // Bare identifier, not window.nav: connected-frontend declares its top-level
  // bindings with const/let in a classic script, so they live in the global
  // LEXICAL environment and are never properties of window. Reading them off
  // window yields undefined, and an assertion against undefined passes
  // vacuously -- which is exactly what happened to this spec once already.
  await page.evaluate("nav('activities')");
  await expect(page.locator("#ynLabel")).toBeVisible({ timeout: 10000 });
}

test("the year bar shows a year and one quiet state line, and the current year carries no arrow", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);

  const year = (await page.locator("#ynLabel").textContent())?.trim() ?? "";
  expect(year).toMatch(/^\d{4}$/);

  const state = (await page.locator("#ynState").textContent())?.trim() ?? "";
  expect(state.length).toBeGreaterThan(0);

  // The arrows mean "away from now"; their absence is what says you are in it.
  const thisYear = new Date().getFullYear();
  if (Number(year) === thisYear) {
    expect(state).toBe("Current year");
    expect(state).not.toContain("←");
    expect(state).not.toContain("→");
  }
});

test("stepping reaches a future year that has no row at all", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);

  const start = Number(await page.locator("#ynLabel").textContent());
  await page.locator("#ynNext").click();
  const next = Number(await page.locator("#ynLabel").textContent());
  expect(next).toBe(start + 1);

  // The whole point, asserted unconditionally so it cannot pass vacuously: the
  // year we stepped onto has NO row, and id-keyed navigation could never have
  // reached it because it was not in the list at all.
  const id = await page.evaluate("P.currentYearId");
  expect(id, "a future year must be reachable with no row behind it").toBeNull();

  const state = (await page.locator("#ynState").textContent())?.trim();
  expect(state).toBe("\u2192 Future year \u00b7 planning ahead");

  const row: any = await page.evaluate(`P.years.find(r => r.year === ${next}) || null`);
  expect(row).not.toBeNull();
  expect(row.materialised).toBe(false);
});

test("the year numeral is tabular: stepping does not change its width", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);

  const widthNow = async () =>
    Math.round((await page.locator("#ynDisplay").boundingBox())!.width);

  const startYear = await page.locator("#ynLabel").textContent();
  const before = await widthNow();
  await page.locator("#ynNext").click();
  await expect(page.locator("#ynLabel")).not.toHaveText(startYear!);
  const after = await widthNow();
  expect(after, "a proportional font would shift every element to its right").toBe(before);
});

test("every year-bar control meets the 44px hit target", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);

  for (const sel of ["#ynPrev", "#ynNext", "#ynDisplay"]) {
    const box = (await page.locator(sel).boundingBox())!;
    expect.soft(Math.round(box.height), `${sel} height`).toBeGreaterThanOrEqual(44);
    expect.soft(Math.round(box.width), `${sel} width`).toBeGreaterThanOrEqual(44);
  }
});

test("the year is no longer administered: no Manage Years control", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  await expect(page.locator("#ynGear")).toHaveCount(0);
});

test("no request is ever made for a null planning year", async ({ page }) => {
  const bad: string[] = [];
  const errors: string[] = [];
  page.on("request", (r) => {
    if (/\/api\/planning\/years\/(null|undefined)\b/.test(r.url())) bad.push(r.url());
  });
  page.on("pageerror", (e) => errors.push(e.message));

  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  await page.locator("#ynNext").click();
  await page.waitForTimeout(1500);

  expect(bad, "requests for /years/null/...").toEqual([]);
  expect(errors, "uncaught page errors").toEqual([]);
});

// --- phase 2: the empty future year, and the past year -----------------------

async function apiToken(page: Page): Promise<string> {
  return await page.evaluate("sessionStorage.getItem('aafc_token')") as string;
}

/** Remove a year's row again so these tests do not poison the shared database
 *  for the "no row at all" test above, which needs 2027 unmaterialised. */
async function deleteYear(page: Page, year: number) {
  const token = await apiToken(page);
  const base = LOCAL_API_BASE!;
  const rows = await (await page.request.get(
    `${base}/api/planning/years`, { headers: { Authorization: `Bearer ${token}` } })).json();
  const row = rows.find((r: any) => r.year === year);
  if (row?.planning_year_id) {
    await page.request.delete(`${base}/api/planning/years/${row.planning_year_id}`,
      { headers: { Authorization: `Bearer ${token}` } });
  }
}

test("an empty future year offers exactly the two things that can be done", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const current = Number(await page.locator("#ynLabel").textContent());
  await page.locator("#ynNext").click();
  const target = current + 1;

  const notice = page.locator("#yn-year-notice .yn-notice");
  await expect(notice).toBeVisible();
  // Never say the year does not exist.
  await expect(notice).not.toContainText("does not exist");
  await expect(notice).toContainText(`Nothing has been set up for ${target} yet`);

  const buttons = notice.locator("button");
  await expect(buttons).toHaveCount(2);
  await expect(buttons.nth(0)).toHaveText(`Set up ${target}`);
  // Names the source year, not "copy previous".
  await expect(buttons.nth(1)).toHaveText(`Copy setup from ${current}`);
});

test("Set up materialises the year and the panel goes away", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const current = Number(await page.locator("#ynLabel").textContent());
  const target = current + 1;
  await page.locator("#ynNext").click();
  await expect(page.locator("#yn-year-notice .yn-notice")).toBeVisible();

  try {
    await page.locator("#yn-year-notice button", { hasText: `Set up ${target}` }).click();
    await expect(page.locator("#yn-year-notice .yn-notice")).toHaveCount(0);
    expect(await page.evaluate("P.currentYearId")).not.toBeNull();
    expect(Number(await page.locator("#ynLabel").textContent())).toBe(target);
  } finally {
    await deleteYear(page, target);
  }
});

test("Copy setup brings the class structure across and says how much it copied", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const current = Number(await page.locator("#ynLabel").textContent());
  const target = current + 1;
  await page.locator("#ynNext").click();

  try {
    await page.locator("#yn-year-notice button", { hasText: `Copy setup from ${current}` }).click();
    await expect(page.locator("#yn-year-notice .yn-notice")).toHaveCount(0);

    const token = await apiToken(page);
    const id = await page.evaluate("P.currentYearId");
    const classes = await (await page.request.get(
      `${LOCAL_API_BASE}/api/training-classes?training_year_id=${id}`,
      { headers: { Authorization: `Bearer ${token}` } })).json();
    expect(classes.length).toBeGreaterThan(0);
  } finally {
    await deleteYear(page, target);
  }
});

test("a past year states it is read-only and names the way to correct it", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const token = await apiToken(page);
  const past = 2019;

  await page.request.post(`${LOCAL_API_BASE}/api/planning/years`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { year: past, name: `${past} Training Year` },
  });

  try {
    // Refresh the year list in place rather than reloading: a reload restarts
    // the app's bootstrap and the bar is not mounted when nav() is called.
    await page.evaluate("_ynFetchYears()");
    await page.evaluate(`setCurrentYear(P.years.find(y => y.year === ${past}))`);

    await expect(page.locator("#ynState")).toHaveText("← Previous year · training record");
    const notice = page.locator("#yn-year-notice .yn-notice-locked");
    await expect(notice).toBeVisible();
    // Read-only is the message; it leads, and it is not carried by an icon.
    await expect(notice.locator("strong")).toHaveText("Read-only.");
    await expect(notice).toContainText("Delegated Intervention");
    // A wall that does not say what to do instead is not acceptable.
    await expect(notice.locator("button")).toHaveCount(0);
  } finally {
    await deleteYear(page, past);
  }
});

// --- phase 3: the year menu --------------------------------------------------

test("the year menu lists what can be selected, tagged by what each year is for", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);

  const btn = page.locator("#ynDisplay");
  await expect(btn).toHaveAttribute("aria-expanded", "false");
  await btn.click();
  await expect(btn).toHaveAttribute("aria-expanded", "true");

  const items = page.locator("#ynMenu button");
  await expect(items.first()).toBeVisible();
  const count = await items.count();
  expect(count).toBeGreaterThanOrEqual(3);

  // RECORD, not PAST: it says what the year is for, and it is the word the
  // read-only notice uses.
  const tags = await page.locator("#ynMenu .yn-tag").allTextContents();
  expect(new Set(tags.filter(Boolean))).toEqual(
    new Set(tags.filter(Boolean).filter(t => ["CURRENT", "FUTURE", "RECORD"].includes(t))));
  expect(tags).toContain("CURRENT");

  // exactly one year is marked current, and it is the one on the bar
  const current = page.locator('#ynMenu button[aria-current="true"]');
  await expect(current).toHaveCount(1);
  await expect(current).toContainText(String(await page.locator("#ynLabel").textContent()));
});

test("choosing a year from the menu moves the bar and closes the menu", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const start = Number(await page.locator("#ynLabel").textContent());

  await page.locator("#ynDisplay").click();
  await page.locator("#ynMenu button", { hasText: String(start + 1) }).click();

  await expect(page.locator("#ynMenu")).toBeHidden();
  await expect(page.locator("#ynDisplay")).toHaveAttribute("aria-expanded", "false");
  expect(Number(await page.locator("#ynLabel").textContent())).toBe(start + 1);
});

test("Escape closes the year menu and returns focus to the control", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  await page.locator("#ynDisplay").click();
  await expect(page.locator("#ynMenu")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator("#ynMenu")).toBeHidden();
  expect(await page.evaluate("document.activeElement.id")).toBe("ynDisplay");
});

test("every year-menu item meets the 44px hit target", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  await page.locator("#ynDisplay").click();
  const items = page.locator("#ynMenu button");
  for (let i = 0; i < await items.count(); i++) {
    const box = (await items.nth(i).boundingBox())!;
    expect.soft(Math.round(box.height), `item ${i} height`).toBeGreaterThanOrEqual(44);
  }
});

test("the year menu is actually on screen, not clipped by its container", async ({ page }) => {
  // toBeVisible only asks whether the element has a box and is not display:none.
  // An absolutely-positioned child of an overflow:hidden parent passes that and
  // renders nothing -- which is exactly what happened. Hit-test instead.
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  await page.locator("#ynDisplay").click();

  const first = page.locator("#ynMenu button").first();
  const box = (await first.boundingBox())!;
  const vp = page.viewportSize()!;
  expect(box.x, "menu runs off the left edge").toBeGreaterThanOrEqual(0);
  expect(box.x + box.width, "menu runs off the right edge").toBeLessThanOrEqual(vp.width);

  const hit = await page.evaluate(([x, y]) => {
    const el = document.elementFromPoint(x as number, y as number);
    return el ? !!el.closest("#ynMenu") : false;
  }, [box.x + box.width / 2, box.y + box.height / 2]);
  expect(hit, "the point at the centre of a menu item does not belong to the menu").toBe(true);
});

// --- phase 4: the year rolling over mid-session ------------------------------

/** Simulate midnight: the year the user is on becomes past, the next becomes
 *  current. Nothing is written -- that is the point -- so this is exactly what
 *  the server's derived state would return the moment the date changes. */
async function simulateMidnight(page: Page, from: number) {
  await page.evaluate(`
    P._ynWasCurrentYear = ${from};
    P.currentYearInt = ${from};
    P.years = P.years.map(y =>
      y.year === ${from} ? { ...y, state: 'past' }
      : y.year === ${from + 1} ? { ...y, state: 'current' }
      : y);
    _ynUpdateDisplay();
  `);
}

test("when the year rolls over mid-session the bar says so and offers the switch", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const on = Number(await page.locator("#ynLabel").textContent());
  await simulateMidnight(page, on);

  const notice = page.locator("#yn-rollover .yn-rollover");
  await expect(notice).toBeVisible();
  await expect(notice).toContainText(`${on + 1} is now the current training year.`);
  await expect(notice.locator("button")).toHaveText(`Switch to ${on + 1}`);

  // and it does NOT move the user
  expect(Number(await page.locator("#ynLabel").textContent())).toBe(on);
});

test("taking the switch moves to the new year and clears the notice", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const on = Number(await page.locator("#ynLabel").textContent());
  await simulateMidnight(page, on);

  await page.locator("#yn-rollover button").click();
  expect(Number(await page.locator("#ynLabel").textContent())).toBe(on + 1);
  await expect(page.locator("#yn-rollover")).toBeHidden();
});

test("deliberately opening a past year does not claim the year just rolled over", async ({ page }) => {
  await loginSquadron(page, "ADMIN703");
  await openYearBar(page);
  const token = await apiToken(page);
  const past = 2018;
  await page.request.post(`${LOCAL_API_BASE}/api/planning/years`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { year: past, name: `${past} Training Year` } });

  try {
    await page.evaluate("_ynFetchYears()");
    await page.evaluate(`setCurrentYear(P.years.find(y => y.year === ${past}))`);
    await expect(page.locator("#ynState")).toHaveText("← Previous year · training record");
    // The read-only notice is right; the rollover notice would be a lie.
    await expect(page.locator("#yn-year-notice .yn-notice-locked")).toBeVisible();
    await expect(page.locator("#yn-rollover")).toBeHidden();
  } finally {
    await deleteYear(page, past);
  }
});
