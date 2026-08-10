import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// CLASS-10: Training Class split/merge lifecycle (addendum §62/§63). Split =
// create a new class + move selected cadets into it. Merge = move every
// active member of a source class into a target class, then archive the
// source (restorable). Neither ever touches SessionAudience -- see the
// backend's own test_merge_does_not_rewrite_session_audience for the direct
// regression proof; this file verifies the same guarantee is reachable
// through the real rendered UI, not just the API.
//
// There is currently no connected-frontend UI for adding a cadet to a
// Training Class (CLASS-09/CadetClassMembership was built API-only) -- so,
// same as this program's established pattern for testing flows with no
// dedicated UI trigger, cadet membership is seeded directly via api() calls
// and only the split/merge/restore actions themselves are driven through
// the real rendered controls.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

// beforeEach, not beforeAll: each test here makes a lot of setup api() calls
// (classes, memberships, sessions), and the general rate limiter is
// per-process, not per-test -- matching the same beforeEach pattern already
// used by other API-call-heavy multi-test files in this suite (e.g.
// activities-inheritance.spec.ts, training-dashboard.spec.ts).
test.beforeEach(async () => {
  await resetBackendRateLimits(process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
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

// Same "choose a real Training Year" helper as training-classes.spec.ts.
async function selectFirstYear(page: Page): Promise<string> {
  const yearSelect = page.locator("#py-select");
  await expect(yearSelect).toBeVisible();
  let firstRealValue = "";
  await expect(async () => {
    const options = await yearSelect.locator("option").all();
    expect(options.length).toBeGreaterThan(1);
    firstRealValue = (await options[1].getAttribute("value")) || "";
    expect(firstRealValue).not.toBe("");
  }).toPass({ timeout: 8000 });
  await yearSelect.selectOption(firstRealValue);
  await page.waitForTimeout(600);
  return firstRealValue;
}

const base = LOCAL_API_BASE || "http://localhost:8000";

async function authedRequest(page: Page) {
  const token = await page.evaluate(() => sessionStorage.getItem("aafc_token"));
  return { Authorization: `Bearer ${token}` };
}

async function makeClass(page: Page, hdr: Record<string, string>, yearId: string, stageId: string, name: string) {
  const r = await page.request.post(`${base}/api/training-classes`, {
    data: { training_year_id: yearId, training_stage_id: stageId, display_name: name },
    headers: hdr,
  });
  expect(r.ok()).toBe(true);
  return (await r.json()).training_class_id as string;
}

async function seedMembership(page: Page, hdr: Record<string, string>, cadetId: string, classId: string) {
  const r = await page.request.post(`${base}/api/cadets/${cadetId}/class-memberships`, {
    data: { training_class_id: classId },
    headers: hdr,
  });
  expect(r.ok()).toBe(true);
}

test.describe("Training Class split/merge/restore (CLASS-10)", () => {
  test("split: moving a cadet creates the new class and it appears in the list", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    const yearId = await selectFirstYear(page);
    const hdr = await authedRequest(page);

    const stageId = await page.evaluate(async () => {
      const phases = await (window as any).api("/api/curriculum/phases");
      return phases.find((p: any) => p.name === "E. Senior").phase_id;
    });
    const suffix = String(Date.now());
    const sourceName = `E2E Split Source ${suffix}`;
    const sourceId = await makeClass(page, hdr, yearId, stageId, sourceName);
    const cadetId = await page.evaluate(async () => (await (window as any).api("/api/cadets"))[0].cadet_id);
    await seedMembership(page, hdr, cadetId, sourceId);

    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);
    await expect(page.locator("#py-classes-body")).toContainText(sourceName, { timeout: 5000 });

    const row = page.locator("#py-classes-body tr", { hasText: sourceName });
    await row.getByRole("button", { name: "Split" }).click();
    const modal = page.locator("#m-split-training-class");
    await expect(modal).toBeVisible();
    await expect(modal).toContainText(sourceName);

    // Roster loaded from GET /training-classes/{id}/members -- the cadet
    // seeded above must be checkable, not an empty "no cadets" state.
    await expect(page.locator(".tcsplit-cadet-chk")).toHaveCount(1, { timeout: 5000 });

    const newClassName = `E2E Split Target ${suffix}`;
    await page.locator("#tcsplit-name-inp").fill(newClassName);
    await page.locator(".tcsplit-cadet-chk").check();
    await modal.getByRole("button", { name: "Split" }).click();

    await expect(modal).toBeHidden({ timeout: 5000 });
    await expect(page.locator("#py-classes-body")).toContainText(newClassName, { timeout: 5000 });
    await expect(page.locator("#py-classes-body")).toContainText(sourceName);

    // Verify the moved cadet actually landed in the new class, not just that
    // the class itself was created.
    const { targetId, members } = await page.evaluate(async (name) => {
      const rows = await (window as any).api("/api/training-classes");
      const target = rows.find((c: any) => c.display_name === name);
      const members = await (window as any).api(`/api/training-classes/${target.training_class_id}/members`);
      return { targetId: target.training_class_id as string, members };
    }, newClassName);
    expect(members.map((m: any) => m.cadet_id)).toContain(cadetId);

    expect(errors, `no uncaught JS errors: ${errors.join("; ")}`).toHaveLength(0);

    // Cleanup.
    await page.request.delete(`${base}/api/training-classes/${sourceId}`, { headers: hdr });
    await page.request.delete(`${base}/api/training-classes/${targetId}`, { headers: hdr });
  });

  test("merge: confirm dialog, source archived, target roster updated, then restore brings source back", async ({ page }) => {
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    const yearId = await selectFirstYear(page);
    const hdr = await authedRequest(page);

    const stageId = await page.evaluate(async () => {
      const phases = await (window as any).api("/api/curriculum/phases");
      return phases.find((p: any) => p.name === "E. Senior").phase_id;
    });
    const suffix = String(Date.now());
    const sourceName = `E2E Merge Source ${suffix}`;
    const targetName = `E2E Merge Target ${suffix}`;
    const sourceId = await makeClass(page, hdr, yearId, stageId, sourceName);
    const targetId = await makeClass(page, hdr, yearId, stageId, targetName);
    const cadetId = await page.evaluate(async () => (await (window as any).api("/api/cadets"))[0].cadet_id);
    await seedMembership(page, hdr, cadetId, sourceId);

    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);
    await expect(page.locator("#py-classes-body")).toContainText(sourceName, { timeout: 5000 });

    const row = page.locator("#py-classes-body tr", { hasText: sourceName });
    await row.getByRole("button", { name: "Merge into…" }).click();
    const mergeModal = page.locator("#m-merge-training-class");
    await expect(mergeModal).toBeVisible();
    await expect(mergeModal).toContainText(sourceName);
    await page.locator("#tcmerge-target-inp").selectOption({ label: targetName });
    await mergeModal.getByRole("button", { name: "Continue…" }).click();
    await expect(mergeModal).toBeHidden();

    // confirmAction()'s real, non-native modal -- not window.confirm().
    const confirmModal = page.locator("#m-confirm");
    await expect(confirmModal).toBeVisible({ timeout: 5000 });
    await expect(confirmModal).toContainText(sourceName);
    await expect(confirmModal).toContainText(targetName);
    await page.locator("#confirm-yes-btn").click();
    await expect(confirmModal).toBeHidden({ timeout: 5000 });

    // Source disappears from the default (active-only) list.
    await expect(page.locator("#py-classes-body")).not.toContainText(sourceName, { timeout: 5000 });

    // Visible again, flagged Archived, via Show archived.
    await page.locator("#tc-show-archived").check();
    const archivedRow = page.locator("#py-classes-body tr", { hasText: sourceName });
    await expect(archivedRow).toBeVisible({ timeout: 5000 });
    await expect(archivedRow).toContainText("Archived");

    // Target roster includes the moved cadet.
    const members = await page.evaluate(
      async (tid) => (window as any).api(`/api/training-classes/${tid}/members`),
      targetId,
    );
    expect(members.map((m: any) => m.cadet_id)).toContain(cadetId);

    // Restore brings the source back to the default (unchecked) view.
    await archivedRow.getByRole("button", { name: "Restore" }).click();
    await page.locator("#tc-show-archived").uncheck();
    await expect(page.locator("#py-classes-body tr", { hasText: sourceName })).toBeVisible({ timeout: 5000 });

    // Cleanup.
    await page.request.delete(`${base}/api/training-classes/${sourceId}`, { headers: hdr });
    await page.request.delete(`${base}/api/training-classes/${targetId}`, { headers: hdr });
  });

  test("merge does not rewrite a past Session's SessionAudience (historical preservation, addendum §62/§63)", async ({ page }) => {
    // The rendered Quick Edit audience picker only lists non-archived
    // classes (a pre-existing scoping decision, unrelated to CLASS-10 --
    // the same was already true for any class archived the ordinary way
    // before split/merge existed), so it is not a display surface for a
    // merged-away class's history. This test instead verifies the same
    // guarantee the backend regression test proves
    // (test_merge_does_not_rewrite_session_audience), but reached through
    // the real rendered Merge button rather than calling the API directly.
    await loginSquadron(page, "ADMIN703");
    await page.evaluate(() => (window as any).nav("activities"));
    const yearId = await selectFirstYear(page);
    const hdr = await authedRequest(page);

    const stageId = await page.evaluate(async () => {
      const phases = await (window as any).api("/api/curriculum/phases");
      return phases.find((p: any) => p.name === "E. Senior").phase_id;
    });
    const suffix = String(Date.now());
    const sourceName = `E2E Audience Source ${suffix}`;
    const targetName = `E2E Audience Target ${suffix}`;
    const sourceId = await makeClass(page, hdr, yearId, stageId, sourceName);
    const targetId = await makeClass(page, hdr, yearId, stageId, targetName);

    // A fresh, unique date per run (not just a fixed +N-day offset) avoids
    // colliding with any other spec/pytest fixture's own parade night on the
    // same computed date -- this suite has hit that exact collision before
    // (703's weekly recurring demo data, and other tests' own day offsets).
    const sessionId = await page.evaluate(async () => {
      const me = await (window as any).api("/api/auth/me");
      const sqnId = me.session.squadron_id, wingId = me.session.wing_id;
      let pn: any = null;
      for (let attempt = 0; attempt < 8 && !pn; attempt++) {
        const d = new Date();
        d.setDate(d.getDate() + 300 + attempt);
        if (d.getDay() === 5) d.setDate(d.getDate() + 1); // avoid 703's weekly Friday collision
        const dateStr = d.toISOString().slice(0, 10);
        try {
          pn = await (window as any).api("/api/parade-nights", {
            method: "POST",
            body: { squadron_id: sqnId, wing_id: wingId, date: dateStr, parade_type: "normal" },
          });
        } catch (e: any) {
          if (e && e.status === 409) continue; // duplicate_date -- try the next day
          throw e;
        }
      }
      if (!pn) throw new Error("could not find a free parade night date after 8 attempts");
      const pnId = pn.parade_night_id || pn.id;
      const sess = await (window as any).api("/api/sessions", {
        method: "POST",
        body: { parade_night_id: pnId, period_number: 1, cadet_group: "senior" },
      });
      return sess.session_id;
    });
    await page.evaluate(
      async ({ sessionId, sourceId }) => {
        await (window as any).api(`/api/sessions/${sessionId}/audience`, {
          method: "PUT",
          body: JSON.stringify({ training_class_ids: [sourceId] }),
        });
      },
      { sessionId, sourceId },
    );

    await page.evaluate(() => (window as any).nav("activities"));
    await selectFirstYear(page);
    const row = page.locator("#py-classes-body tr", { hasText: sourceName });
    await row.getByRole("button", { name: "Merge into…" }).click();
    await page.locator("#tcmerge-target-inp").selectOption({ label: targetName });
    await page.locator("#m-merge-training-class").getByRole("button", { name: "Continue…" }).click();
    await page.locator("#confirm-yes-btn").click();
    await expect(page.locator("#m-confirm")).toBeHidden({ timeout: 5000 });

    const audience = await page.evaluate(
      async (sid) => (window as any).api(`/api/sessions/${sid}/audience`),
      sessionId,
    );
    expect(audience).toHaveLength(1);
    expect(audience[0].training_class_id).toBe(sourceId);

    // Cleanup.
    await page.request.delete(`${base}/api/training-classes/${sourceId}`, { headers: hdr });
    await page.request.delete(`${base}/api/training-classes/${targetId}`, { headers: hdr });
  });
});
