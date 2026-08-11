import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-12: "Progress by element" — the element-scoped sibling of the
// existing "Progress by phase" card on the Squadron Dashboard, answering
// "how much [element] have we delivered" (previously only filterable in
// Mission Backlog, never aggregated). See backend/app/routers/dashboard.py's
// _element_curriculum_progress / _elements_for_squadron and
// backend/tests/test_dashboard_charts.py for the backend-level coverage —
// this spec exercises the actual rendered chart card end to end.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

async function loginSquadron(page: Page, code: string) {
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
  await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });
}

async function apiBase() {
  return process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000";
}

test.describe("Squadron Dashboard — Progress by element (CLASS-12)", () => {
  test("card renders the seeded national element catalogue and reflects a delivered session", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await loginSquadron(page, "ADMIN703");
    const token = await page.evaluate(() => (window as any).tokenGet?.() ?? sessionStorage.getItem("aafc_token"));
    const base = await apiBase();
    const auth = { Authorization: `Bearer ${token}` };

    // Seed a curriculum item tagged "Drill" (one of the 7 default national
    // elements, seed_all.py's _DEFAULT_ELEMENTS) and deliver one session
    // against it, so the chart has a real, checkable non-zero bar rather
    // than only an empty default catalogue.
    const suffix = String(Date.now());
    const ciRes = await page.request.post(`${base}/api/curriculum`, {
      data: { code: `C12-${suffix.slice(-6)}`, title: "Element Progress E2E Item",
              phase: "A. Orientation", element: "Drill", duration_minutes: 60 },
      headers: auth,
    });
    expect(ciRes.ok()).toBe(true);
    const ciId = (await ciRes.json()).curriculum_id as string;

    const testDate = `2071-06-${String((Number(suffix.slice(-2)) % 27) + 1).padStart(2, "0")}`;
    const pnRes = await page.request.post(`${base}/api/parade-nights`, {
      data: { date: testDate }, headers: auth,
    });
    expect(pnRes.ok()).toBe(true);
    const pnId = (await pnRes.json()).parade_night_id as string;

    const sessRes = await page.request.post(`${base}/api/sessions`, {
      data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" },
      headers: auth,
    });
    expect(sessRes.ok()).toBe(true);
    const sid = (await sessRes.json()).session_id as string;

    const editRes = await page.request.put(`${base}/api/sessions/${sid}`, {
      data: { parade_night_id: pnId, period_number: 1, curriculum_item_id: ciId, status: "delivered" },
      headers: auth,
    });
    expect(editRes.ok()).toBe(true);

    // Reload so the Dashboard's own loadData()/loadDashCharts() picks up the
    // freshly seeded session rather than relying on stale state from login.
    await page.reload();
    await expect(page.locator(".ph-title", { hasText: "Training Dashboard" })).toBeVisible({ timeout: 10000 });

    const card = page.locator(".card", { has: page.locator(".ctitle", { hasText: "Progress by element" }) });
    await expect(card).toBeVisible({ timeout: 10000 });
    const chart = card.locator("#chart-element-curriculum-progress");
    // The seeded default national catalogue (Drill, Air_Space, ...) must
    // appear -- this was the exact bug found during implementation: the
    // shared bar-chart renderer only ever checked row.phase, so every row in
    // this new chart silently rendered as "—" until fixed.
    await expect(chart.getByText("Drill", { exact: true })).toBeVisible();
    // The delivered session's bar must actually be non-empty for the Drill
    // row -- proven via the row's own aria-label (role="img"), which encodes
    // "<name>: <pct>% delivered" and is unaffected by the 14-char name
    // truncation applied to the visible label text.
    await expect(chart.locator('[role="img"][aria-label^="Drill:"]')).not.toHaveAttribute("aria-label", "Drill: 0% delivered");

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });

  // NOTE: _chartStackedBarH() (the renderer shared by both "Progress by
  // phase" and "Progress by element") never attaches an onclick to its rows
  // -- unlike _chartHBar's rows, which do wire drillDashChart() via
  // chart.drill_down/r.drill_id. drillDashChart()'s own phase/element
  // branches and drillPhaseDash() are therefore unreachable dead code today,
  // a PRE-EXISTING gap in the phase chart this task mirrors, not something
  // CLASS-12 introduced or is scoped to fix -- recorded as a residual
  // limitation in the gap register rather than silently worked around here.
  test("both progress cards render side by side with no console errors, confirming shared-renderer wiring survived the new chart", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    const phaseCard = page.locator(".card", { has: page.locator(".ctitle", { hasText: "Progress by phase" }) });
    const elementCard = page.locator(".card", { has: page.locator(".ctitle", { hasText: "Progress by element" }) });
    await expect(phaseCard).toBeVisible({ timeout: 10000 });
    await expect(elementCard).toBeVisible({ timeout: 10000 });
    // PH_S remaps phase display labels ("A. Orientation" -> "Orientation");
    // elements have no such remap, so "Drill" renders verbatim.
    await expect(phaseCard.getByText("Orientation", { exact: true })).toBeVisible();
    await expect(elementCard.getByText("Drill", { exact: true })).toBeVisible();
    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);
  });
});
