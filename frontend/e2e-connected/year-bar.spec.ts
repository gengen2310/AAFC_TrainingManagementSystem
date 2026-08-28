import { test, expect, Page } from "@playwright/test";

// The Training Year is a time context, not a workflow object. These tests hold
// the design in docs/design/training-year-frontend-design.md to its own gates.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

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
