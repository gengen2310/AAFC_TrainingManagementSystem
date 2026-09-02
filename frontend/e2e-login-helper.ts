// REM-84: LoginPage.tsx now collects unit type / wing / squadron / role
// before the access-code field (resolving a user_id via /api/auth/lookup
// first is what puts a login on the backend's scoped, per-account-lockout
// path -- see auth.py's own comments). Every e2e spec that previously did
// `page.getByLabel("Access code").fill(code)` directly on a fresh page needs
// to drive the new multi-step UI instead. This helper centralises that,
// mapping this repo's known seed-data demo codes (seed_all.py) to their
// (unit_type, identifier, role) triple so call sites barely change.

import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

interface LoginParams {
  unitType: "squadron" | "wing" | "national";
  identifier?: string;
  role: string;
}

const NATIONAL_CODES: Record<string, string> = {
  ADMINNATIONAL: "national_admin",
  NATIONAL2026: "national_viewer",
  SYSADMIN2026: "system_admin",
  AUDITOR2026: "auditor",
};

function resolveLoginParams(code: string): LoginParams {
  if (code in NATIONAL_CODES) {
    return { unitType: "national", role: NATIONAL_CODES[code] };
  }
  if (code === "ADMIN7WG") return { unitType: "wing", identifier: "7WG", role: "wing_admin" };
  if (code === "7WG2026") return { unitType: "wing", identifier: "7WG", role: "wing_viewer" };
  const sqnAdmin = code.match(/^ADMIN(\d+)$/);
  if (sqnAdmin) return { unitType: "squadron", identifier: sqnAdmin[1], role: "sqn_admin" };
  const sqnGeneral = code.match(/^(\d+)SQN2026$/);
  if (sqnGeneral) return { unitType: "squadron", identifier: sqnGeneral[1], role: "sqn_general" };
  throw new Error(`loginPW: no (unit_type, identifier, role) mapping known for code "${code}" -- add one to e2e-login-helper.ts`);
}

/** Drives the real rendered multi-step login UI (not a direct API call) --
 * for specs that need to specifically exercise the UI, or as the default
 * "get into the app" helper.
 *
 * Clears both the aafc_session cookie AND the aafc_token sessionStorage
 * entry, then re-navigates to "/" so AuthProvider's GET /api/auth/me call
 * fires with no auth state and returns 401, forcing the login form to
 * render.  Playwright shares the browser context (and therefore cookies
 * and sessionStorage) across tests in the same worker, so without both
 * clears the prior test's session bypasses the login page entirely.
 *
 * callers that need AAFC_API_BASE set via addInitScript should register
 * their script before calling loginPW — addInitScript fires on every
 * navigation including the one this function performs. */
export async function loginPW(page: Page, code: string) {
  await page.context().clearCookies();
  // sessionStorage persists across same-tab navigations; clear the
  // Bearer token so AuthProvider's me() call has no auth whatsoever.
  await page.evaluate(() => sessionStorage.clear());
  await page.goto("/");
  const { unitType, identifier, role } = resolveLoginParams(code);
  await page.getByLabel("Login as").selectOption(unitType);
  if (unitType !== "national") {
    await page.getByLabel("Wing", { exact: true }).selectOption("7WG");
  }
  if (unitType === "squadron") {
    await page.getByLabel("Squadron / Unit").selectOption(identifier!);
  }
  await page.getByLabel("Role", { exact: true }).selectOption(role);
  await page.getByLabel("Access code").fill(code);
  await page.getByRole("button", { name: "Log in" }).click();
}

/** loginPW + navigate to "/" first + wait for a real post-login page element
 * to appear, matching the pattern most specs actually want. */
export async function loginPWAndWait(page: Page, code: string, waitForSelector: string) {
  await page.goto("/");
  await loginPW(page, code);
  await expect(page.locator(waitForSelector).first()).toBeVisible({ timeout: 10000 });
}
