import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Attribute-context injection, the GAP-24 pattern, at sites that still used
// esc() instead of _jsAttr().
//
// esc() turns ' into &#39;. Inside a double-quoted attribute the HTML parser
// decodes that back to ' BEFORE the value is parsed as JavaScript, so a title
// containing  '),code,('  closes the argument list, runs whatever follows, and
// reopens it. _jsAttr() exists precisely for this: it backslash-escapes \ and '
// first, then esc()s, so the quote survives as an escaped quote inside the JS
// string literal.
//
// Reproduced before the fix -- the injected expression executed:
//   openAssignModal('cur-1','Safety Brief'),window.__xssFired=true,('','X1',1)
// After: ...,'Safety Brief\'),window.__xssFired=true,(\'',...  -- inert.
//
// Curriculum titles are settable by squadron and wing admins and inherit
// downward, so a wing-scope item renders in every squadron admin's browser in
// that wing. That is why this is tested against a real stored record rather
// than a synthetic string.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

declare const S: any;
declare function api(path: string, opts?: any): Promise<any>;
declare function reloadAndRender(): Promise<void>;
declare function _wizRenderCurrList(q?: string): void;

// A marker, never alert() -- a modal dialog would block the whole session.
const PAYLOAD = "Safety Brief'),window.__xssFired=true,('";

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

test("XSS-ATTR-01: a hostile curriculum title cannot break out of the guided-mode wizard's onclick", async ({ page }) => {
  await loginSquadron(page);

  const code = `XS${Date.now()}`.slice(0, 12);
  await page.evaluate(async ([c, title]) => {
    await api("/api/curriculum", {
      method: "POST",
      body: JSON.stringify({
        code: c, title, phase: "A. Orientation",
        learning_hub_url: "https://example.invalid/learning-hub/xss-fixture",
      }),
    });
    await reloadAndRender();
  }, [code, PAYLOAD]);

  const result = await page.evaluate((c) => {
    (window as any).__xssFired = false;
    // The wizard's list container exists in markup; render straight into it.
    let list = document.getElementById("wiz-curr-list");
    if (!list) { list = document.createElement("div"); list.id = "wiz-curr-list"; document.body.appendChild(list); }
    _wizRenderCurrList(c);
    const item = list.querySelector<HTMLElement>(".wiz-curr-item");
    const attr = item ? item.getAttribute("onclick") : null;
    if (item) item.click();
    return { attr, fired: (window as any).__xssFired === true };
  }, code);

  expect(result.attr).not.toBeNull();
  // The payload must appear backslash-escaped, still inside the string argument.
  expect(result.attr).toContain("\\'");
  expect(result.fired).toBe(false);
});

// NOTE ON SCOPE: this second test builds the template inline, so it pins the
// _jsAttr() CONTRACT for this payload shape -- it does not read the shipped
// renderMissions() source and would not catch that call site regressing back to
// esc(). A call-site test is not possible today: renderMissions() renders into
// #missions-body, which does not exist in the markup (REM-148), so the function
// is unreachable. If that container is ever restored, replace this with a real
// call-site test.
test("XSS-ATTR-02: _jsAttr() neutralises this payload shape in an onclick argument", async ({ page }) => {
  await loginSquadron(page);

  const result = await page.evaluate((title) => {
    (window as any).__xssFired = false;
    const m = { curriculum_id: "cur-1", title, code: "X1", part_count: 1 };
    const host = document.createElement("div");
    // mirrors renderMissions()'s Assign button template
    host.innerHTML = `<button class="btn-xs" onclick="openAssignModal('${(window as any).esc(m.curriculum_id)}','${(window as any)._jsAttr(m.title)}','${(window as any)._jsAttr(m.code)}',${m.part_count})">Assign</button>`;
    document.body.appendChild(host);
    const btn = host.querySelector("button")!;
    const attr = btn.getAttribute("onclick");
    try { btn.click(); } catch { /* handler may throw after firing */ }
    const fired = (window as any).__xssFired === true;
    host.remove();
    return { attr, fired };
  }, PAYLOAD);

  expect(result.fired).toBe(false);
  expect(result.attr).toContain("\\'");
});
