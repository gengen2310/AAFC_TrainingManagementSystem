import type { Page } from "@playwright/test";
import { expect } from "@playwright/test";

/**
 * Planning Workspace is a module of the Main TMS, not a second application.
 * It therefore has no login UI of its own. E2E tests establish the same backend
 * session the Main TMS would hand across, then place the returned bearer token
 * in sessionStorage before React mounts. The backend also sets the shared
 * aafc_session cookie on the Playwright browser context.
 */
interface LoginParams {
  unitType: "squadron" | "wing" | "national";
  identifier?: string;
  role: string;
}

export interface PWLoginResult {
  token: string;
  session: Record<string, unknown>;
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
  throw new Error(`loginPW: no seeded login mapping for code "${code}"`);
}

function backendBase(): string {
  return process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";
}

/** Establish a real scoped backend session and enter the module at /planning. */
export async function loginPW(page: Page, code: string): Promise<PWLoginResult> {
  const { unitType, identifier, role } = resolveLoginParams(code);

  // Remove state from a previous test before issuing a fresh login. Navigate to
  // the app origin once so sessionStorage is addressable, then clear it.
  await page.context().clearCookies();
  await page.goto("/");
  await page.evaluate(() => sessionStorage.clear());

  const base = backendBase();
  const lookup = await page.request.post(`${base}/api/auth/lookup`, {
    data: { unit_type: unitType, identifier, role },
  });
  expect(lookup.ok(), `lookup failed for ${unitType}/${identifier ?? "national"}/${role}: ${lookup.status()}`).toBeTruthy();
  const userId = (await lookup.json()).user_id as string;

  const login = await page.request.post(`${base}/api/auth/login`, {
    data: { code, user_id: userId },
  });
  expect(login.ok(), `login failed for ${role}: ${login.status()}`).toBeTruthy();
  const body = await login.json() as { token?: string; access_token?: string; session?: Record<string, unknown> };
  const token = body.token || body.access_token || "";
  expect(token, `login for ${role} returned no bearer token`).not.toBe("");

  // addInitScript runs before the module's AuthProvider on the next navigation,
  // matching the Main-TMS handoff contract in src/main.tsx without resurrecting
  // a standalone Planning Workspace login page.
  await page.addInitScript((t: string) => {
    sessionStorage.setItem("aafc_token", t);
  }, token);
  await page.goto("/planning");
  await expect(page.locator('[role="main"][aria-label="Planning workspace"]')).toBeVisible({ timeout: 10000 });

  return { token, session: body.session ?? {} };
}

/** loginPW plus a caller-specific readiness assertion. */
export async function loginPWAndWait(page: Page, code: string, waitForSelector: string): Promise<PWLoginResult> {
  const result = await loginPW(page, code);
  await expect(page.locator(waitForSelector).first()).toBeVisible({ timeout: 10000 });
  return result;
}
