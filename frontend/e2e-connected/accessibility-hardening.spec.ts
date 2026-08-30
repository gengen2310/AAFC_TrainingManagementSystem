import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

// Phase 8 Hardening — accessibility smoke tests.
// Covers: HARD-03 (prefers-reduced-motion), HARD-04 (focus visibility),
// HARD-05 (modal focus management + Escape-to-close), HARD-06 (landmarks).
//
// These tests verify structural correctness of accessibility primitives —
// they are not a substitute for manual screen reader testing or an Axe audit.

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000"
  );
});

async function loginSquadron(page: Page, code = "ADMIN703") {
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
  await expect(page.locator("#app")).toBeVisible({ timeout: 10000 });
}

// ── Landmarks ────────────────────────────────────────────────────────────────

test("HARD-05: semantic <nav> and <main> landmarks are present after login", async ({ page }) => {
  await loginSquadron(page);
  // role="navigation" from <nav class="sidenav">
  const nav = page.getByRole("navigation");
  await expect(nav).toBeAttached();
  // role="main" from <main class="main" id="main-content">
  const main = page.getByRole("main");
  await expect(main).toBeAttached();
});

test("HARD-05: skip-to-main link is in the DOM and targets #main-content", async ({ page }) => {
  await loginSquadron(page);
  const skip = page.locator(".skip-link");
  await expect(skip).toBeAttached();
  const href = await skip.getAttribute("href");
  expect(href).toBe("#main-content");
});

test("HARD-05: toast region has aria-live=polite", async ({ page }) => {
  await loginSquadron(page);
  const toast = page.locator("#toast-region");
  await expect(toast).toHaveAttribute("aria-live", "polite");
  await expect(toast).toHaveAttribute("aria-atomic", "true");
});

// ── Modal focus management (HARD-05) ─────────────────────────────────────────

test("HARD-05: opening a modal moves focus inside it", async ({ page }) => {
  await loginSquadron(page);
  await page.evaluate(() => (window as any).nav("parade-nights"));

  // Click "+ Add Parade Night" to open a modal
  const addBtn = page.locator("button").filter({ hasText: "+ Add Parade Night" }).first();
  await expect(addBtn).toBeVisible({ timeout: 8000 });
  await addBtn.click();

  const modal = page.locator("#m-add-pn");
  await expect(modal).toHaveClass(/active/, { timeout: 5000 });

  // Focus should now be inside the modal — the first focusable element
  // (50ms delay in openModal; allow generous timeout)
  await page.waitForTimeout(100);
  const focused = await page.evaluate(() => document.activeElement?.closest(".modal-bg")?.id ?? null);
  expect(focused).toBe("m-add-pn");
});

test("HARD-05: Escape key closes an open modal", async ({ page }) => {
  await loginSquadron(page);
  await page.evaluate(() => (window as any).nav("parade-nights"));

  const addBtn = page.locator("button").filter({ hasText: "+ Add Parade Night" }).first();
  await expect(addBtn).toBeVisible({ timeout: 8000 });
  await addBtn.click();

  const modal = page.locator("#m-add-pn");
  await expect(modal).toHaveClass(/active/, { timeout: 5000 });

  await page.keyboard.press("Escape");
  await expect(modal).not.toHaveClass(/active/, { timeout: 3000 });
});

// ── Keyboard focus visibility (HARD-04) ──────────────────────────────────────

test("HARD-04: .btn:focus-visible outline rule is present in the stylesheet", async ({ page }) => {
  await loginSquadron(page);

  // Verify the CSS rule exists: focus-visible on .btn should produce an outline.
  const hasRule = await page.evaluate(() => {
    for (const sheet of Array.from(document.styleSheets)) {
      try {
        for (const rule of Array.from(sheet.cssRules || [])) {
          if (rule instanceof CSSStyleRule) {
            if (rule.selectorText?.includes("btn") && rule.selectorText?.includes("focus-visible")) {
              const style = rule.style;
              if (style.outline || style.getPropertyValue("outline")) return true;
            }
          }
        }
      } catch { /* cross-origin sheet */ }
    }
    return false;
  });
  expect(hasRule).toBe(true);
});

// ── Reduced motion (HARD-03) ─────────────────────────────────────────────────

test("HARD-03: prefers-reduced-motion media rule is present in the stylesheet", async ({ page }) => {
  await loginSquadron(page);

  const hasRule = await page.evaluate(() => {
    for (const sheet of Array.from(document.styleSheets)) {
      try {
        for (const rule of Array.from(sheet.cssRules || [])) {
          if (rule instanceof CSSMediaRule) {
            const text = rule.conditionText || rule.media?.mediaText || "";
            if (/prefers-reduced-motion/.test(text)) return true;
          }
        }
      } catch { /* cross-origin */ }
    }
    return false;
  });
  expect(hasRule).toBe(true);
});

// ── Hamburger aria-expanded (HARD-05) ────────────────────────────────────────

test("HARD-05: hamburger button aria-expanded toggles on open/close at mobile width", async ({ page }) => {
  // Emulate a mobile viewport to make the hamburger appear
  await page.setViewportSize({ width: 390, height: 844 });
  await loginSquadron(page);

  const btn = page.locator("#btn-hamburger");
  await expect(btn).toBeVisible();
  await expect(btn).toHaveAttribute("aria-expanded", "false");

  await btn.click();
  await expect(btn).toHaveAttribute("aria-expanded", "true");

  await btn.click();
  await expect(btn).toHaveAttribute("aria-expanded", "false");
});

// ── HARD-09: promptText() modal replaces native prompt() ─────────────────────

test("HARD-09: #m-text-input modal exists in DOM with correct ARIA attributes", async ({ page }) => {
  await loginSquadron(page);
  const modal = page.locator("#m-text-input");
  await expect(modal).toBeAttached();
  await expect(modal).toHaveAttribute("role", "dialog");
  await expect(modal).toHaveAttribute("aria-modal", "true");
  await expect(modal).toHaveAttribute("aria-labelledby", "ti-title");
  // Input must be labelled
  await expect(modal.locator("#ti-input")).toBeAttached();
  await expect(modal.locator("#ti-label")).toBeAttached();
  // Required button infrastructure
  await expect(modal.locator("#ti-ok-btn")).toBeAttached();
});

test("HARD-09: promptText() modal opens, accepts input, and closes on OK", async ({ page }) => {
  await loginSquadron(page);
  // Invoke promptText() directly via JS to test the modal lifecycle
  const valuePromise = page.evaluate(async () => {
    return new Promise<string | null>((resolve) => {
      const p: Promise<string | null> = (window as any).promptText("Test title", "Test label", {
        context: "Test context",
        okLabel: "Submit",
      });
      p.then(resolve);
    });
  });

  const modal = page.locator("#m-text-input");
  await expect(modal).toHaveClass(/active/, { timeout: 3000 });
  await expect(page.locator("#ti-title")).toHaveText("Test title");
  await expect(page.locator("#ti-ok-btn")).toHaveText("Submit");

  // Fill the input and press Enter
  const input = page.locator("#ti-input");
  await expect(input).toBeFocused({ timeout: 1000 });
  await input.fill("test value");
  await page.keyboard.press("Enter");

  await expect(modal).not.toHaveClass(/active/, { timeout: 3000 });
  const result = await valuePromise;
  expect(result).toBe("test value");
});

test("HARD-09: Escape key cancels the promptText() modal and resolves null", async ({ page }) => {
  await loginSquadron(page);
  const valuePromise = page.evaluate(async () => {
    return (window as any).promptText("Cancel test", "Value");
  });

  const modal = page.locator("#m-text-input");
  await expect(modal).toHaveClass(/active/, { timeout: 3000 });

  await page.keyboard.press("Escape");
  await expect(modal).not.toHaveClass(/active/, { timeout: 3000 });
  const result = await valuePromise;
  expect(result).toBeNull();
});

// ── VIS-04: Keyboard navigation of sidebar nav items ─────────────────────────

test("VIS-04: visible nav items have tabindex=0 after login", async ({ page }) => {
  // VIS-04 fix: applyNavScope() sets shown nav items to tabindex="0" and hidden
  // items to tabindex="-1". This prevents keyboard users reaching hidden items.
  await loginSquadron(page);
  const visibleNavItems = page.locator(".nav-item:visible");
  const count = await visibleNavItems.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    const tab = await visibleNavItems.nth(i).getAttribute("tabindex");
    expect(tab).toBe("0");
  }
});

test("VIS-04: pressing Enter on a nav item navigates to that page", async ({ page }) => {
  // VIS-04 fix: delegated keydown listener on .sidenav triggers click() on
  // Enter/Space, so keyboard-only users can navigate without a pointer device.
  await loginSquadron(page);
  // Find the "Parade Nights" nav item (sqn_admin scope always includes it).
  // By role and name, not a data-page hook: the nav items never had one, so
  // this test matched nothing and passed no judgement on anything for as long
  // as it has existed. Selecting the way a user perceives the control also
  // asserts its accessible name.
  const pnNavItem = page.getByRole("link", { name: "Parade Nights", exact: true });
  await expect(pnNavItem).toBeVisible({ timeout: 8000 });
  // Focus it and press Enter.
  await pnNavItem.focus();
  await page.keyboard.press("Enter");
  // The parade-nights page should become active.
  await expect(page.locator("#page-parade-nights")).toBeVisible({ timeout: 8000 });
});

test("VIS-04: pressing Space on a nav item navigates to that page", async ({ page }) => {
  // Same keyboard wiring — Space should behave identically to Enter on nav items.
  await loginSquadron(page);
  const dashNavItem = page.getByRole("link", { name: "Training Dashboard", exact: true });
  await expect(dashNavItem).toBeVisible({ timeout: 8000 });
  // First navigate away so we can confirm Space brings us back.
  await page.evaluate(() => (window as any).nav("parade-nights"));
  await expect(page.locator("#page-parade-nights")).toBeVisible({ timeout: 5000 });
  // Now focus the dashboard nav item and press Space.
  await dashNavItem.focus();
  await page.keyboard.press("Space");
  await expect(page.locator("#page-dashboard")).toBeVisible({ timeout: 8000 });
});

test("HARD-09: validate param blocks submission when check fails", async ({ page }) => {
  await loginSquadron(page);
  void page.evaluate(() => {
    (window as any).promptText("Type-to-confirm", "Type CONFIRM", {
      validate: (v: string) => (v !== "CONFIRM" ? "Type exactly: CONFIRM" : ""),
    });
  });

  const modal = page.locator("#m-text-input");
  await expect(modal).toHaveClass(/active/, { timeout: 3000 });

  // Submit wrong value — modal should stay open with error
  await page.locator("#ti-input").fill("wrong");
  await page.locator("#ti-ok-btn").click();
  await expect(modal).toHaveClass(/active/);
  await expect(page.locator("#ti-err")).toHaveText("Type exactly: CONFIRM");

  // Submit correct value — modal closes
  await page.locator("#ti-input").fill("CONFIRM");
  await page.locator("#ti-ok-btn").click();
  await expect(modal).not.toHaveClass(/active/, { timeout: 3000 });
});
