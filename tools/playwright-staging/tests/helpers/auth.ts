import { Page, expect } from "@playwright/test";

const API = process.env.STAGING_API ?? "https://aafc-tms-backend-staging.up.railway.app";

export interface RoleCred {
  label: string;
  unitType: string;
  identifier: string;
  role: string;
  envVar: string;
}

export const ROLES: RoleCred[] = [
  { label: "Squadron Admin (703)",   unitType: "squadron", identifier: "703", role: "sqn_admin",    envVar: "STAGING_SQN_ADMIN_CODE" },
  { label: "Squadron General (703)", unitType: "squadron", identifier: "703", role: "sqn_general",  envVar: "STAGING_SQN_GENERAL_CODE" },
  { label: "Wing Admin (7WG)",       unitType: "wing",     identifier: "7WG", role: "wing_admin",   envVar: "STAGING_WING_ADMIN_CODE" },
  { label: "National Admin",         unitType: "national", identifier: "",    role: "national_admin",envVar: "STAGING_NATIONAL_ADMIN_CODE" },
  { label: "System Admin",           unitType: "national", identifier: "",    role: "system_admin",  envVar: "STAGING_SYSADMIN_CODE" },
];

/** Obtain a Bearer token via the two-step API auth flow (no code in source). */
export async function getToken(role: RoleCred): Promise<string> {
  const code = process.env[role.envVar];
  if (!code) throw new Error(`Missing env var ${role.envVar} for ${role.label}`);

  // Step 1: lookup
  const lookupBody: Record<string, string> = { unit_type: role.unitType, role: role.role };
  if (role.identifier) lookupBody.identifier = role.identifier;
  const lu = await fetch(`${API}/api/auth/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lookupBody),
  });
  if (!lu.ok) {
    const t = await lu.text();
    throw new Error(`Lookup failed for ${role.label}: ${lu.status} ${t}`);
  }
  const { user_id } = (await lu.json()) as { user_id: string };

  // Step 2: login
  const li = await fetch(`${API}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, user_id }),
  });
  if (!li.ok) {
    const t = await li.text();
    throw new Error(`Login failed for ${role.label}: ${li.status} ${t}`);
  }
  const data = (await li.json()) as { token?: string; access_token?: string };
  const token = data.token ?? data.access_token;
  if (!token) throw new Error(`No token in login response for ${role.label}`);
  return token;
}

/**
 * Proxy all backend API requests through Node.js, bypassing the browser's network sandbox.
 *
 * The Playwright headless Chrome cannot make outbound XHR/fetch requests in this environment.
 * page.route() intercepts requests at the Playwright layer (Node.js) and fulfills them from
 * the test runner, which has full network access.
 *
 * Must be called before page.goto() so the intercept is active from the first navigation.
 */
export async function addApiProxy(page: Page): Promise<void> {
  await page.route(`${API}/**`, async (route) => {
    const req = route.request();
    const method = req.method();
    const url = req.url();
    const rawHeaders = req.headers();
    const postData = req.postData();

    // Strip hop-by-hop and browser-only headers that Node.js fetch rejects.
    const skipHeaders = new Set([
      "host", "connection", "transfer-encoding", "te",
      "upgrade", "keep-alive", "proxy-authenticate", "proxy-authorization",
      "trailer",
    ]);
    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(rawHeaders)) {
      if (!skipHeaders.has(k.toLowerCase())) headers[k] = v;
    }

    try {
      const resp = await fetch(url, {
        method,
        headers,
        body: postData ? postData : undefined,
        redirect: "manual",
      });

      const bodyBuffer = Buffer.from(await resp.arrayBuffer());
      const respHeaders: Record<string, string> = {};
      resp.headers.forEach((v, k) => { respHeaders[k] = v; });
      // Remove encoding headers — Node.js has already decoded.
      delete respHeaders["content-encoding"];
      delete respHeaders["transfer-encoding"];

      await route.fulfill({ status: resp.status, headers: respHeaders, body: bodyBuffer });
    } catch (e) {
      await route.abort("failed");
    }
  });
}

/**
 * Authenticate in the SPA by:
 * 1. Installing an API proxy (Node.js proxies all backend fetches from the browser).
 * 2. Loading the page and injecting the Bearer token into sessionStorage.
 * 3. Driving the SPA's own boot sequence (applySession → loadData → bootApp)
 *    so the app renders exactly as it would after a real login.
 *
 * Page reload is NOT used because the SPA has no session-restore-on-load code —
 * bootApp() is only called from doLogin() unless we invoke it directly.
 */
export async function injectSession(page: Page, role: RoleCred): Promise<void> {
  const token = await getToken(role);

  // The connected-frontend/Planning-Workspace cross-origin handoff (see
  // .claude/rules/architecture.md) relies on the `aafc_session` cookie as a
  // fallback when there's no sessionStorage token to send (a fresh tab/origin
  // — exactly what a Playwright test navigating straight to PW_BASE is).
  // getToken() logs in via a Node.js-side fetch(), so any Set-Cookie the
  // backend returned was only ever seen by Node's fetch implementation, never
  // by this page's actual browser cookie jar -- every PW-CTX-01 test that
  // navigated cross-origin was therefore silently hitting the "Session not
  // found" NotAuthenticated screen instead of real Planning Workspace
  // content, undetected because the original assertions (non-empty body, no
  // "Something went wrong" text) are also true for that screen. Found and
  // fixed 2026-08-08 while adding PW-CTX-01b. The token itself IS the cookie
  // value (backend/app/routers/auth.py sets response.set_cookie(COOKIE_NAME,
  // token, ...)), so add it directly to the browser context with the same
  // attributes staging actually uses (SameSite=None; Secure -- confirmed via
  // `railway variable list` against the backend service, not guessed).
  const backendHost = new URL(API).hostname;
  await page.context().addCookies([
    {
      name: "aafc_session",
      value: token,
      domain: backendHost,
      path: "/",
      httpOnly: true,
      secure: true,
      sameSite: "None",
    },
  ]);

  // Proxy must be registered before page.goto() so the first navigation's sub-requests
  // (e.g. loadData API calls triggered by the boot sequence) are also intercepted.
  await addApiProxy(page);
  await page.goto("/");

  // Store token so the SPA's api() helper picks it up via tokenGet().
  await page.evaluate((t) => sessionStorage.setItem("aafc_token", t), token);

  // Drive the SPA's own init sequence via its global functions.
  // api() uses API_BASE (the meta-tag backend URL) + tokenGet() from sessionStorage.
  // All resulting fetches are fulfilled by the Node.js proxy above.
  // loadData() already calls /api/proxy/current and sets S.proxy — no manual seeding needed.
  await page.evaluate(async () => {
    const w = window as unknown as Record<string, (...a: unknown[]) => unknown>;
    const data = (await w.api("/api/auth/me")) as { session: Record<string, unknown> };
    w.applySession(data.session);
    await (w.loadData as () => Promise<void>)();
    w.bootApp();
  });

  // #app becomes display:flex once bootApp() runs.
  await expect(page.locator("#app")).toBeVisible({ timeout: 20_000 });
}
