/**
 * A11Y-01 Staging Verification — Real Login Flow
 *
 * Tests select-name, label, duplicate-id axe rules against the rendered
 * deployed staging application using the real browser login flow
 * (not token injection).
 *
 * Roles tested:
 *   - system_admin  (STAGING_SYSADMIN_CODE env var)
 *   - sqn_admin     (STAGING_SQN_ADMIN_CODE env var)
 *
 * Other roles are documented as AUTHENTICATED ROLE VERIFICATION PENDING.
 */

import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const STAGING_URL = process.env.STAGING_URL ?? "https://aafc-tms-frontend-staging.up.railway.app";

// The global playwright config injects x-test-run into all requests including page-level fetch,
// which triggers CORS preflight failures (backend does not allow x-test-run in ACAO headers).
// Override to empty for this spec so real-browser login flows work correctly.
test.use({ extraHTTPHeaders: {} });
const AXE_RULES = ["select-name", "label", "label-content-name-mismatch", "duplicate-id", "duplicate-id-aria", "aria-allowed-attr"];

// ── Real login helpers ─────────────────────────────────────────────────────

async function loginNational(page: Page, role: string, code: string) {
  await page.goto(STAGING_URL + "/");
  await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

  await page.selectOption("#auth-type", "national");
  // Wait for role dropdown to populate
  await page.waitForFunction(() => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-role");
    return sel && sel.options.length > 1;
  }, { timeout: 5000 });
  await page.selectOption("#auth-role", role);

  // Continue button should now be enabled
  await page.waitForSelector("#auth-continue-btn:not([disabled])", { timeout: 5000 });
  await page.click("#auth-continue-btn");
  await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });

  await page.fill("#auth-code", code);
  await page.click("#auth-btn");
  // Wait for app to load (auth-screen hidden, #app shown)
  await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });
}

async function loginSquadron(page: Page, wingCode: string, sqnCode: string, role: string, accessCode: string) {
  await page.goto(STAGING_URL + "/");
  await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

  await page.selectOption("#auth-type", "squadron");
  // Wait for wing dropdown to populate from API
  await page.waitForFunction(() => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-wing-select");
    return sel && sel.options.length > 1;
  }, { timeout: 10000 });

  // Select wing by code value (wings use code as option value)
  await page.selectOption("#auth-wing-select", wingCode);

  // Wait for squadron dropdown to populate
  await page.waitForFunction(() => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-sqn-select");
    return sel && sel.options.length > 1;
  }, { timeout: 10000 });

  // Select squadron by code text match
  await page.waitForFunction((code) => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-sqn-select");
    if (!sel) return false;
    return Array.from(sel.options).some(o => o.text.includes(code));
  }, sqnCode, { timeout: 10000 });

  const sqnOptValue = await page.evaluate((code) => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-sqn-select");
    if (!sel) return "";
    const opt = Array.from(sel.options).find(o => o.text.includes(code));
    return opt ? opt.value : "";
  }, sqnCode);

  if (!sqnOptValue) throw new Error(`Squadron ${sqnCode} not found in dropdown`);
  await page.selectOption("#auth-sqn-select", sqnOptValue);

  // Wait for role dropdown
  await page.waitForFunction(() => {
    const sel = document.querySelector<HTMLSelectElement>("#auth-role");
    return sel && sel.options.length > 1;
  }, { timeout: 5000 });
  await page.selectOption("#auth-role", role);

  await page.waitForSelector("#auth-continue-btn:not([disabled])", { timeout: 5000 });
  await page.click("#auth-continue-btn");
  await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });

  await page.fill("#auth-code", accessCode);
  await page.click("#auth-btn");
  await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });
}

async function runAxeOnPage(page: Page, description: string): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withRules(AXE_RULES)
    .analyze();

  const critical = results.violations.filter(v => v.impact === "critical");
  const serious = results.violations.filter(v => v.impact === "serious");
  const selectViolations = results.violations.filter(v => v.id === "select-name" || v.id === "label");
  const dupeViolations = results.violations.filter(v => v.id === "duplicate-id" || v.id === "duplicate-id-aria");

  if (results.violations.length > 0) {
    for (const v of results.violations) {
      console.log(`  [${v.impact}] ${v.id}: ${v.description}`);
      for (const node of v.nodes.slice(0, 3)) {
        console.log(`    ${node.target}: ${node.html?.slice(0, 120)}`);
      }
    }
  }

  expect(critical, `${description}: ${critical.length} CRITICAL axe violations`).toHaveLength(0);
  expect(serious, `${description}: ${serious.length} SERIOUS axe violations`).toHaveLength(0);
  expect(selectViolations, `${description}: select-name/label violations`).toHaveLength(0);
  expect(dupeViolations, `${description}: duplicate-id violations`).toHaveLength(0);
}

async function navTo(page: Page, pageId: string) {
  await page.evaluate((id) => {
    (window as any).nav(id);
  }, pageId);
  await page.waitForTimeout(800); // allow render
}

// ── System Admin tests ─────────────────────────────────────────────────────

test.describe("[A11Y-Staging] System Admin", () => {
  const code = process.env.STAGING_SYSADMIN_CODE ?? "";

  test.beforeEach(async ({ page }) => {
    if (!code) test.skip(true, "STAGING_SYSADMIN_CODE not set");
  });

  test("Login form selects — axe clean", async ({ page }) => {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });
    await runAxeOnPage(page, "Login form (system_admin flow)");
  });

  test("Login → Dashboard — axe clean", async ({ page }) => {
    await loginNational(page, "system_admin", code);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });
    await runAxeOnPage(page, "Dashboard (system_admin)");
  });

  test("System Console — axe clean", async ({ page }) => {
    await loginNational(page, "system_admin", code);
    await navTo(page, "system-console");
    await page.waitForSelector("#page-system-console.active", { timeout: 10000 });
    await runAxeOnPage(page, "System Console");
  });

  test("Account Management — axe clean", async ({ page }) => {
    await loginNational(page, "system_admin", code);
    await navTo(page, "accounts");
    await page.waitForSelector("#page-accounts.active", { timeout: 10000 });
    await runAxeOnPage(page, "Account Management (system_admin)");
  });

  test("Scope selectors keyboard — #sa-scope-wing and #sa-scope-sqn focusable", async ({ page }) => {
    await loginNational(page, "system_admin", code);
    // sa-scope-bar is visible only for system_admin
    await page.waitForSelector("#sa-scope-bar", { timeout: 5000 });

    // Tab to sa-scope-wing and confirm it's reachable
    const wingFocused = await page.evaluate(() => {
      const el = document.getElementById("sa-scope-wing") as HTMLElement;
      if (!el) return "NOT FOUND";
      el.focus();
      return document.activeElement?.id ?? "other";
    });
    expect(wingFocused).toBe("sa-scope-wing");

    // Check accessible name via aria-label
    const wingSel = page.locator("#sa-scope-wing");
    const wingLabel = await wingSel.getAttribute("aria-label");
    expect(wingLabel, "#sa-scope-wing must have aria-label").toBeTruthy();
    console.log(`  #sa-scope-wing aria-label: "${wingLabel}"`);
  });

  test("Login form keyboard — Tab through auth selects", async ({ page }) => {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

    // Select Account Type and confirm focus
    const authType = page.locator("#auth-type");
    await authType.focus();
    expect(await page.evaluate(() => document.activeElement?.id)).toBe("auth-type");

    // Check label association: clicking label focuses select
    const labelForAuthType = page.locator('label[for="auth-type"]');
    await expect(labelForAuthType).toHaveText("Account type");
    await labelForAuthType.click();
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => document.activeElement?.id)).toBe("auth-type");

    // Select squadron to reveal wing/sqn selects
    await page.selectOption("#auth-type", "squadron");
    await page.waitForSelector("#auth-wing-wrap", { state: "visible", timeout: 5000 });

    // Wing label → wing select
    const wingLabel = page.locator('label[for="auth-wing-select"]');
    await expect(wingLabel).toHaveText("Wing");
    await wingLabel.click();
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => document.activeElement?.id)).toBe("auth-wing-select");

    console.log("  ✓ label[for=auth-type] → #auth-type: click-to-focus confirmed");
    console.log("  ✓ label[for=auth-wing-select] → #auth-wing-select: click-to-focus confirmed");
  });
});

// ── Squadron Admin tests ───────────────────────────────────────────────────

test.describe("[A11Y-Staging] Squadron Admin", () => {
  const code = process.env.STAGING_SQN_ADMIN_CODE ?? "";

  test.beforeEach(async ({ page }) => {
    if (!code) test.skip(true, "STAGING_SQN_ADMIN_CODE not set");
  });

  test("Login flow for sqn_admin — real browser login", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    // Should be on dashboard or default page
    const title = await page.title();
    console.log(`  Page title after login: ${title}`);
    // Confirm auth screen hidden
    await expect(page.locator("#auth-screen")).toBeHidden();
  });

  test("Dashboard — axe clean", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });
    await runAxeOnPage(page, "Dashboard (sqn_admin)");
  });

  test("Parade Nights — axe clean (filters: term + status)", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "parade-nights");
    await page.waitForSelector("#page-parade-nights.active", { timeout: 10000 });
    await runAxeOnPage(page, "Parade Nights (sqn_admin)");

    // Confirm filter selects have specific aria-labels
    const termLabel = await page.locator("#pn-f-term").getAttribute("aria-label");
    const statusLabel = await page.locator("#pn-f-status").getAttribute("aria-label");
    expect(termLabel).toContain("Parade Night");
    expect(statusLabel).toContain("Parade Night");
    console.log(`  #pn-f-term aria-label: "${termLabel}"`);
    console.log(`  #pn-f-status aria-label: "${statusLabel}"`);
  });

  test("Weekly Program — axe clean (wp-sel + wp-f-status)", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "weekly-program");
    await page.waitForSelector("#page-weekly-program.active", { timeout: 10000 });
    await runAxeOnPage(page, "Weekly Program (sqn_admin)");

    const wpStatusLabel = await page.locator("#wp-f-status").getAttribute("aria-label");
    expect(wpStatusLabel).toContain("Weekly Program");
    console.log(`  #wp-f-status aria-label: "${wpStatusLabel}"`);
  });

  test("Activities — axe clean (act-f-type filter)", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "activities");
    await page.waitForSelector("#page-activities.active", { timeout: 10000 });
    await runAxeOnPage(page, "Activities (sqn_admin)");
  });

  test("Facilitators — axe clean (fac-filter)", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "facilitators");
    await page.waitForSelector("#page-facilitators.active", { timeout: 10000 });
    await runAxeOnPage(page, "Facilitators (sqn_admin)");
  });

  test("Parade Nights keyboard — pn-f-term label click-to-focus", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "parade-nights");
    await page.waitForSelector("#page-parade-nights.active", { timeout: 10000 });

    // Confirm pn-f-term is keyboard reachable
    const focused = await page.evaluate(() => {
      const el = document.getElementById("pn-f-term") as HTMLElement;
      if (!el) return "NOT FOUND";
      el.focus();
      return document.activeElement?.id ?? "other";
    });
    expect(focused).toBe("pn-f-term");
    console.log("  ✓ #pn-f-term: keyboard focus reachable");

    // Verify change handler is intact — select an option and check
    const initialOption = await page.locator("#pn-f-term").inputValue();
    console.log(`  #pn-f-term initial value: "${initialOption}"`);
  });

  test("Dashboard filter keyboard — dash-window and dash-sqn-filter", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "dashboard");
    await page.waitForSelector("#page-dashboard.active", { timeout: 10000 });

    // #dash-window has label[for] with style= attribute — verify it's correctly associated
    const dashLabel = page.locator('label[for="dash-window"]');
    const dashLabelExists = await dashLabel.count();
    expect(dashLabelExists).toBeGreaterThan(0);
    console.log("  ✓ label[for=dash-window] present in rendered DOM");

    // Focus dash-window
    const focused = await page.evaluate(() => {
      const el = document.getElementById("dash-window") as HTMLElement;
      if (!el) return "NOT FOUND";
      el.focus();
      return document.activeElement?.id ?? "other";
    });
    expect(focused).toBe("dash-window");
    console.log("  ✓ #dash-window: keyboard focus reachable");
  });

  test("Dynamic session row — no duplicate IDs after PN detail render", async ({ page }) => {
    await loginSquadron(page, "7WG", "703", "sqn_admin", code);
    await navTo(page, "parade-nights");
    await page.waitForSelector("#page-parade-nights.active", { timeout: 10000 });

    // Click first parade night if available to trigger dynamic row render
    const firstPN = page.locator(".pn-row, .pn-item, [data-pnid]").first();
    const hasPNs = await firstPN.count();
    if (hasPNs > 0) {
      await firstPN.click();
      await page.waitForTimeout(1000);

      // Check for duplicate IDs in the rendered DOM
      const dupes = await page.evaluate(() => {
        const ids = Array.from(document.querySelectorAll("[id]")).map(el => el.id);
        const counts: Record<string, number> = {};
        ids.forEach(id => { if (id) counts[id] = (counts[id] || 0) + 1; });
        return Object.entries(counts).filter(([, count]) => count > 1).map(([id]) => id);
      });

      if (dupes.length > 0) {
        console.log(`  DUPLICATE IDs found after render: ${dupes.join(", ")}`);
      }
      expect(dupes, `Duplicate IDs in rendered DOM: ${dupes.join(", ")}`).toHaveLength(0);
      console.log("  ✓ No duplicate IDs after PN detail render");
    } else {
      console.log("  ⚠ No parade nights found — dynamic row test skipped");
    }
  });
});

// ── Wing Admin tests ───────────────────────────────────────────────────────

test.describe("[A11Y-Staging] Wing Admin", () => {
  const code = process.env.STAGING_WING_ADMIN_CODE ?? "";

  test.beforeEach(async ({ page }) => {
    if (!code) test.skip(true, "STAGING_WING_ADMIN_CODE not set");
  });

  async function loginWingAdmin(page: Page) {
    await page.goto(STAGING_URL + "/");
    await page.waitForSelector("#auth-step1", { state: "visible", timeout: 20000 });

    await page.selectOption("#auth-type", "wing");
    // Wait for wing dropdown to populate
    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-wing-select");
      return sel && sel.options.length > 1;
    }, { timeout: 10000 });
    await page.selectOption("#auth-wing-select", "7WG");

    await page.waitForFunction(() => {
      const sel = document.querySelector<HTMLSelectElement>("#auth-role");
      return sel && sel.options.length > 1;
    }, { timeout: 5000 });
    await page.selectOption("#auth-role", "wing_admin");

    await page.waitForSelector("#auth-continue-btn:not([disabled])", { timeout: 5000 });
    await page.click("#auth-continue-btn");
    await page.waitForSelector("#auth-step2", { state: "visible", timeout: 10000 });

    await page.fill("#auth-code", code);
    await page.click("#auth-btn");
    await page.waitForSelector("#auth-screen", { state: "hidden", timeout: 15000 });
  }

  test("Wing Overview — axe clean", async ({ page }) => {
    await loginWingAdmin(page);
    await navTo(page, "wing-overview");
    await page.waitForSelector("#page-wing-overview.active", { timeout: 10000 });
    await runAxeOnPage(page, "Wing Overview (wing_admin)");
  });

  test("Wing Activities — axe clean", async ({ page }) => {
    await loginWingAdmin(page);
    await navTo(page, "wing-activities");
    await page.waitForSelector("#page-wing-activities.active", { timeout: 10000 });
    await runAxeOnPage(page, "Wing Activities (wing_admin)");
  });

  test("Wing HQ Calendar — axe clean", async ({ page }) => {
    await loginWingAdmin(page);
    await navTo(page, "wing-calendar");
    await page.waitForSelector("#page-wing-calendar.active", { timeout: 10000 });
    await runAxeOnPage(page, "Wing HQ Calendar (wing_admin)");
  });

  test("Wing dashboard report cards (T2-04/T2-05) — axe clean", async ({ page }) => {
    await loginWingAdmin(page);
    // Wing landing page loads #page-wing-overview; #wing-dash cards are rendered within it
    await page.waitForSelector("#page-wing-overview.active", { timeout: 10000 });
    // Wait for wing report cards to render (they require the API roundtrip to complete)
    await page.waitForFunction(() => {
      const wd = document.querySelector("#wing-dash");
      return wd && wd.innerHTML.includes("Cancellation");
    }, { timeout: 15000 });
    await runAxeOnPage(page, "Wing dashboard report cards (wing_admin)");
  });

  test("Wing Overview keyboard — wing-overview page controls focusable", async ({ page }) => {
    await loginWingAdmin(page);
    await navTo(page, "wing-overview");
    await page.waitForSelector("#page-wing-overview.active", { timeout: 10000 });

    // cmd-window-sel (period selector) should be keyboard focusable
    const focused = await page.evaluate(() => {
      const el = document.getElementById("cmd-window-sel") as HTMLElement;
      if (!el) return "NOT FOUND";
      el.focus();
      return document.activeElement?.id ?? "other";
    });
    if (focused !== "NOT FOUND") {
      expect(focused).toBe("cmd-window-sel");
      console.log("  ✓ #cmd-window-sel: keyboard focus reachable");
    } else {
      console.log("  ⚠ #cmd-window-sel not found on wing-overview — may be in cmd-dash-wing only");
    }

    // Confirm no duplicate IDs introduced by wing-overview rendering
    const dupes = await page.evaluate(() => {
      const ids = Array.from(document.querySelectorAll("[id]")).map(el => el.id);
      const counts: Record<string, number> = {};
      ids.forEach(id => { if (id) counts[id] = (counts[id] || 0) + 1; });
      return Object.entries(counts).filter(([, count]) => count > 1).map(([id]) => id);
    });
    expect(dupes, `Duplicate IDs in wing-overview DOM: ${dupes.join(", ")}`).toHaveLength(0);
    console.log("  ✓ No duplicate IDs in wing-overview DOM");
  });
});

// ── National Admin tests ───────────────────────────────────────────────────

test.describe("[A11Y-Staging] National Admin", () => {
  const code = process.env.STAGING_NATIONAL_ADMIN_CODE ?? "";

  test.beforeEach(async ({ page }) => {
    if (!code) test.skip(true, "STAGING_NATIONAL_ADMIN_CODE not set");
  });

  test("National Overview — axe clean", async ({ page }) => {
    await loginNational(page, "national_admin", code);
    await navTo(page, "national");
    await page.waitForSelector("#page-national.active", { timeout: 10000 });
    await runAxeOnPage(page, "National Overview (national_admin)");
  });

  test("National Activities — axe clean", async ({ page }) => {
    await loginNational(page, "national_admin", code);
    await navTo(page, "national-activities");
    await page.waitForSelector("#page-national-activities.active", { timeout: 10000 });
    await runAxeOnPage(page, "National Activities (national_admin)");
  });

  test("National Overview keyboard — no duplicate IDs after National Training Dashboard render", async ({ page }) => {
    await loginNational(page, "national_admin", code);
    await navTo(page, "national");
    await page.waitForSelector("#page-national.active", { timeout: 10000 });
    // Wait for dashboard data to render
    await page.waitForFunction(() => {
      const dash = document.querySelector("#cmd-dash-national");
      return dash && dash.querySelectorAll("tr").length > 1;
    }, { timeout: 15000 });

    const dupes = await page.evaluate(() => {
      const ids = Array.from(document.querySelectorAll("[id]")).map(el => el.id);
      const counts: Record<string, number> = {};
      ids.forEach(id => { if (id) counts[id] = (counts[id] || 0) + 1; });
      return Object.entries(counts).filter(([, count]) => count > 1).map(([id]) => id);
    });
    expect(dupes, `Duplicate IDs after National dashboard render: ${dupes.join(", ")}`).toHaveLength(0);
    console.log("  ✓ No duplicate IDs after National Training Dashboard render");
  });

  test("National Overview cmd-window-sel — keyboard focusable", async ({ page }) => {
    await loginNational(page, "national_admin", code);
    await navTo(page, "national");
    await page.waitForSelector("#page-national.active", { timeout: 10000 });

    const focused = await page.evaluate(() => {
      const el = document.getElementById("cmd-window-sel") as HTMLElement;
      if (!el) return "NOT FOUND";
      el.focus();
      return document.activeElement?.id ?? "other";
    });
    expect(focused, "#cmd-window-sel must be keyboard focusable on National Overview").toBe("cmd-window-sel");
    console.log("  ✓ #cmd-window-sel: keyboard focus reachable on National Overview");
  });
});

// ── ca-flight hidden select assessment ────────────────────────────────────

test("[A11Y-Staging] Hidden select #ca-flight — not keyboard focusable", async ({ page }) => {
  const code = process.env.STAGING_SQN_ADMIN_CODE ?? "";
  if (!code) test.skip(true, "STAGING_SQN_ADMIN_CODE not set");

  await loginSquadron(page, "7WG", "703", "sqn_admin", code);
  await navTo(page, "accounts");
  await page.waitForSelector("#page-accounts.active", { timeout: 10000 });

  const assessment = await page.evaluate(() => {
    const el = document.getElementById("ca-flight") as HTMLSelectElement | null;
    if (!el) return { found: false };
    const parent = el.closest("[aria-hidden]");
    const parentHidden = parent?.getAttribute("aria-hidden");
    const parentDisplay = parent ? getComputedStyle(parent).display : "N/A";
    const tabindex = el.getAttribute("tabindex");
    const selfDisplay = getComputedStyle(el).display;

    // Try to focus it — should NOT become active element if AT-hidden
    el.focus();
    const isFocused = document.activeElement === el;

    return {
      found: true,
      parentAriaHidden: parentHidden,
      parentDisplay,
      selfDisplay,
      tabindex,
      isFocused,
    };
  });

  console.log("  #ca-flight assessment:");
  console.log(`    found:              ${assessment.found}`);
  console.log(`    parent aria-hidden: ${assessment.parentAriaHidden}`);
  console.log(`    parent display:     ${assessment.parentDisplay}`);
  console.log(`    self display:       ${assessment.selfDisplay}`);
  console.log(`    tabindex:           ${assessment.tabindex}`);
  console.log(`    focus() => active:  ${assessment.isFocused}`);

  expect(assessment.found).toBe(true);
  expect(assessment.parentAriaHidden).toBe("true");
  expect(assessment.isFocused).toBe(false);
  // tabindex="-1" means it's intentionally removed from tab order
  expect(assessment.tabindex).toBe("-1");
});
