import { test, expect, type Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// E2E tests for Planning Workspace filter features implemented in session 15:
//   CLASS-19 — Class focus chip dims non-matching session cells
//   CLASS-21 — Foundation/Extension tier filter (core_status-based)
//   CLASS-22 — Stage focus filter dims sessions whose audience classes belong to a different stage
//   CLASS-23 — Per-block collapse toggle hides / shows block body

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

// ---------------------------------------------------------------------------
// Shared fixture builder: creates an isolated PlanningYear with one stage,
// one class, one parade date + parade night, and one session audience-linked
// to that class. Returns cleanup helpers and the key IDs.
// ---------------------------------------------------------------------------
async function buildFixture(page: Page, hdr: Record<string, string>, testYear: number, label: string) {
  const suffix = String(Date.now());
  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;
  const wingId = me.session.wing_id as string;

  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `PW-Filters ${label} ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;

  const stageName = `PWF-${label}-${suffix}`;
  const stageRes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageName, display_name: stageName, scope_level: "squadron", squadron_id: sqnId },
    headers: hdr,
  });
  expect(stageRes.ok()).toBe(true);
  const stageId = (await stageRes.json()).phase_id as string;

  const className = `PWF Class ${label} ${suffix}`;
  const classRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: className }, headers: hdr,
  });
  expect(classRes.ok()).toBe(true);
  const classId = (await classRes.json()).training_class_id as string;

  // Term 3 date for the test year so it falls inside a rendered block.
  const pnDate = `${testYear}-08-06`;
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pnId = (await pdRes.json()).parade_night_id as string;
  expect(pnId, "parade-dates create must return a parade_night_id").toBeTruthy();

  const sessRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" }, headers: hdr,
  });
  expect(sessRes.ok()).toBe(true);
  const sid = (await sessRes.json()).session_id as string;

  await page.request.put(`${API_BASE}/api/sessions/${sid}/audience`, {
    data: { training_class_ids: [classId] }, headers: hdr,
  });

  const yearLabel = `PW-Filters ${label} ${suffix}`;

  async function cleanup() {
    await page.request.delete(`${API_BASE}/api/training-classes/${classId}`, { headers: hdr });
    await page.request.post(`${API_BASE}/api/curriculum/phases/${stageId}/archive`, { headers: hdr });
    const yr = await (await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr })).json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: yr.version }, headers: hdr,
    });
  }

  return { sqnId, wingId, yearId, stageId, stageName, classId, className, pnId, pnDate, sid, yearLabel, suffix, cleanup };
}

// ---------------------------------------------------------------------------
// CLASS-19: Class focus chip
// ---------------------------------------------------------------------------
test("CLASS-19: class focus chip — clicking a class chip dims sessions not assigned to that class", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const testYear = 2700 + (Date.now() % 50);
  const f = await buildFixture(page, hdr, testYear, "C19");

  // Second class in the same stage — session 2 will NOT have this class assigned.
  const class2Name = `PWF Class C19b ${f.suffix}`;
  const class2Res = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: f.yearId, training_stage_id: f.stageId, display_name: class2Name }, headers: hdr,
  });
  expect(class2Res.ok()).toBe(true);
  const class2Id = (await class2Res.json()).training_class_id as string;

  // Session 2 assigned to class2 only.
  const sess2Res = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: f.pnId, period_number: 2, cadet_group: "senior" }, headers: hdr,
  });
  expect(sess2Res.ok()).toBe(true);
  const sid2 = (await sess2Res.json()).session_id as string;
  await page.request.put(`${API_BASE}/api/sessions/${sid2}/audience`, {
    data: { training_class_ids: [class2Id] }, headers: hdr,
  });

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: f.yearLabel }).click();

    // Left panel "Class focus" section is only rendered when >1 class exists.
    // It uses aria-pressed on each chip button.
    const classChip = page.getByRole("button", { name: f.className, exact: true }).filter({ has: page.locator('[aria-pressed]') });
    await expect(classChip).toBeVisible({ timeout: 10000 });

    // Initially "All" is pressed, none of the period cells are dimmed.
    const allChip = page.locator('.pw-filter-chips button[aria-pressed="true"]').first();
    await expect(allChip).toContainText("All");

    // Click the first class chip.
    await page.getByRole("button", { name: f.className }).filter({ has: page.locator('[aria-pressed]') }).click();

    // The clicked chip should now be selected (aria-pressed="true").
    const pressedChip = page.locator(`button[aria-pressed="true"]`).filter({ hasText: f.className });
    await expect(pressedChip).toBeVisible({ timeout: 5000 });

    // Sessions NOT assigned to classId should be dimmed (opacity 0.22 inline style).
    // We verify that at least one cell carries the dimmed style.
    const dimmedCell = page.locator('td[style*="opacity: 0.22"]');
    await expect(dimmedCell.first()).toBeVisible({ timeout: 5000 });
  } finally {
    await page.request.delete(`${API_BASE}/api/training-classes/${class2Id}`, { headers: hdr });
    await f.cleanup();
  }
});

// ---------------------------------------------------------------------------
// CLASS-21: Foundation / Extension tier filter
// ---------------------------------------------------------------------------
test("CLASS-21: tier filter — 'Foundation' chip dims a session with core_status=additional", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const testYear = 2750 + (Date.now() % 50);
  const f = await buildFixture(page, hdr, testYear, "C21");

  // Create a squadron curriculum item — POST /api/curriculum always creates
  // items with core_status="additional" (squadron-level default).
  const ciCode = `C21-${f.suffix.slice(-8)}`;
  const ciRes = await page.request.post(`${API_BASE}/api/curriculum`, {
    data: { code: ciCode, title: "Tier Filter Test Item", phase: f.stageName }, headers: hdr,
  });
  expect(ciRes.ok(), `CI create: ${await ciRes.text()}`).toBe(true);
  const ciId = (await ciRes.json()).curriculum_id as string;

  // Link the CI to session 1 so it has a known core_status.
  const sessBody = { parade_night_id: f.pnId, period_number: 1, cadet_group: "senior", curriculum_item_id: ciId };
  const sessUpdateRes = await page.request.put(`${API_BASE}/api/sessions/${f.sid}`, {
    data: sessBody, headers: hdr,
  });
  expect(sessUpdateRes.ok(), `session update: ${await sessUpdateRes.text()}`).toBe(true);

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: f.yearLabel }).click();

    // "Session tier" section should be in the left panel.
    const tierSection = page.locator('.pw-section-hdr', { hasText: 'Session tier' });
    await expect(tierSection).toBeVisible({ timeout: 10000 });

    // Initially "All" is pressed (aria-pressed="true") for the tier section.
    const tierAllChip = page.locator('.pw-filter-chips button', { hasText: 'All' }).first();
    await expect(tierAllChip).toHaveAttribute('aria-pressed', 'true');

    // Click "Foundation" chip.
    const foundationChip = page.locator('.pw-filter-chips button', { hasText: 'Foundation' });
    await foundationChip.click();
    await expect(foundationChip).toHaveAttribute('aria-pressed', 'true');

    // Our session has core_status="additional" (not "core"), so it should be dimmed.
    const dimmedCell = page.locator('td[style*="opacity: 0.22"]');
    await expect(dimmedCell.first()).toBeVisible({ timeout: 5000 });

    // Clicking "Extension" should un-dim the "additional" session.
    const extensionChip = page.locator('.pw-filter-chips button', { hasText: 'Extension' });
    await extensionChip.click();
    await expect(extensionChip).toHaveAttribute('aria-pressed', 'true');
    // The "additional" session is now NOT dimmed (it matches "extension" = "additional").
    // Verify no dimmed cells are visible in the block.
    const dimmedAfterExt = page.locator('td[style*="opacity: 0.22"]');
    await expect(dimmedAfterExt).toHaveCount(0);
  } finally {
    await page.request.delete(`${API_BASE}/api/curriculum/${ciId}`, { headers: hdr });
    await f.cleanup();
  }
});

// ---------------------------------------------------------------------------
// CLASS-22: Stage focus filter
// ---------------------------------------------------------------------------
test("CLASS-22: stage focus — clicking a stage chip dims sessions from other stages", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const testYear = 2800 + (Date.now() % 50);
  const me = await (await page.request.get(`${API_BASE}/api/auth/me`, { headers: hdr })).json();
  const sqnId = me.session.squadron_id as string;
  const suffix = String(Date.now());

  const yearRes = await page.request.post(`${API_BASE}/api/planning/years`, {
    data: { year: testYear, name: `PW-Filters C22 ${suffix}` }, headers: hdr,
  });
  expect(yearRes.ok()).toBe(true);
  const yearId = (await yearRes.json()).planning_year_id as string;
  const yearLabel = `PW-Filters C22 ${suffix}`;

  // Two stages.
  const stageAName = `C22-Stage-A-${suffix}`;
  const stageARes = await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageAName, display_name: stageAName, scope_level: "squadron", squadron_id: sqnId }, headers: hdr,
  });
  expect(stageARes.ok()).toBe(true);
  const stageAId = (await stageARes.json()).phase_id as string;

  const stageBName = `C22-Stage-B-${suffix}`;
  const stageBData = await (await page.request.post(`${API_BASE}/api/curriculum/phases`, {
    data: { name: stageBName, display_name: stageBName, scope_level: "squadron", squadron_id: sqnId }, headers: hdr,
  })).json();
  const stageBId = stageBData.phase_id as string;

  // Class A in stage A; class B in stage B.
  const classAName = `C22 Class A ${suffix}`;
  const classARes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageAId, display_name: classAName }, headers: hdr,
  });
  expect(classARes.ok()).toBe(true);
  const classAId = (await classARes.json()).training_class_id as string;

  const classBName = `C22 Class B ${suffix}`;
  const classBRes = await page.request.post(`${API_BASE}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageBId, display_name: classBName }, headers: hdr,
  });
  expect(classBRes.ok()).toBe(true);
  const classBId = (await classBRes.json()).training_class_id as string;

  const pnDate = `${testYear}-08-06`;
  const pdRes = await page.request.post(`${API_BASE}/api/planning/years/${yearId}/parade-dates`, {
    data: { parade_date: pnDate }, headers: hdr,
  });
  expect(pdRes.ok()).toBe(true);
  const pnId = (await pdRes.json()).parade_night_id as string;

  // Session 1 → Class A (Stage A). Session 2 → Class B (Stage B).
  const sessARes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" }, headers: hdr,
  });
  const sidA = (await sessARes.json()).session_id as string;
  await page.request.put(`${API_BASE}/api/sessions/${sidA}/audience`, {
    data: { training_class_ids: [classAId] }, headers: hdr,
  });

  const sessBRes = await page.request.post(`${API_BASE}/api/sessions`, {
    data: { parade_night_id: pnId, period_number: 2, cadet_group: "senior" }, headers: hdr,
  });
  const sidB = (await sessBRes.json()).session_id as string;
  await page.request.put(`${API_BASE}/api/sessions/${sidB}/audience`, {
    data: { training_class_ids: [classBId] }, headers: hdr,
  });

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: yearLabel }).click();

    // "Stage focus" section visible only when multiStage (>1 distinct stage).
    const stageFocusSection = page.locator('.pw-section-hdr', { hasText: 'Stage focus' });
    await expect(stageFocusSection).toBeVisible({ timeout: 10000 });

    // Click Stage A chip.
    const stageAChip = page.locator('.pw-filter-chips button[aria-pressed]', { hasText: stageAName });
    await expect(stageAChip).toBeVisible({ timeout: 5000 });
    await stageAChip.click();
    await expect(stageAChip).toHaveAttribute('aria-pressed', 'true');

    // Session 2 (Stage B) should now be dimmed.
    const dimmedCells = page.locator('td[style*="opacity: 0.22"]');
    await expect(dimmedCells.first()).toBeVisible({ timeout: 5000 });
  } finally {
    await page.request.delete(`${API_BASE}/api/training-classes/${classAId}`, { headers: hdr });
    await page.request.delete(`${API_BASE}/api/training-classes/${classBId}`, { headers: hdr });
    await page.request.post(`${API_BASE}/api/curriculum/phases/${stageAId}/archive`, { headers: hdr });
    await page.request.post(`${API_BASE}/api/curriculum/phases/${stageBId}/archive`, { headers: hdr });
    const yr = await (await page.request.get(`${API_BASE}/api/planning/years/${yearId}`, { headers: hdr })).json();
    await page.request.patch(`${API_BASE}/api/planning/years/${yearId}`, {
      data: { active_status: false, version: yr.version }, headers: hdr,
    });
  }
});

// ---------------------------------------------------------------------------
// CLASS-23: Per-block collapse toggle
// ---------------------------------------------------------------------------
test("CLASS-23: collapse button — clicking collapse hides block body; clicking again expands", async ({ page }) => {
  const hdr = await authHeader(page, ADMIN_CODE);
  const testYear = 2850 + (Date.now() % 50);
  const f = await buildFixture(page, hdr, testYear, "C23");

  try {
    await page.goto("/planning");
    await expect(page.getByRole("main", { name: /planning workspace/i })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: f.yearLabel }).click();

    // Wait for at least one parade night block to appear.
    const collapseBtn = page.locator('.pw-block-collapse-btn').first();
    await expect(collapseBtn).toBeVisible({ timeout: 10000 });

    // Initially expanded: aria-expanded="true".
    await expect(collapseBtn).toHaveAttribute('aria-expanded', 'true');

    // Block body contains the period grid table (.pw-night-grid), hidden on collapse.
    const blockGrid = page.locator('.pw-night-grid').first();
    await expect(blockGrid).toBeVisible({ timeout: 5000 });

    // Collapse.
    await collapseBtn.click();
    await expect(collapseBtn).toHaveAttribute('aria-expanded', 'false');

    // Grid should be hidden.
    await expect(blockGrid).not.toBeVisible({ timeout: 5000 });

    // Expand again.
    await collapseBtn.click();
    await expect(collapseBtn).toHaveAttribute('aria-expanded', 'true');
    await expect(blockGrid).toBeVisible({ timeout: 5000 });
  } finally {
    await f.cleanup();
  }
});
