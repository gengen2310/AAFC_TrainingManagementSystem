// DEFECT-004 (general-release qualification): shared helper for clearing the
// backend's general API rate limiter, DB-backed per-IP login limiter, and
// per-account lockout via POST /api/system/reset-rate-limits
// (backend/app/routers/system.py -- system_admin only, rejected in
// production via settings.is_prod). Used by playwright-global-setup.ts
// (once per full suite invocation) and, per spec file where it's proven
// necessary, a test.beforeAll() call (see e2e-connected/main-tms.spec.ts) --
// a single suite-wide reset was not always enough on its own: a file's own
// request volume, especially when other spec files ran immediately before
// it in the same invocation, can still cross the general limiter's 300
// req/60s budget partway through a run. A per-file reset gives that file
// its own fresh budget without needing every file to opt in speculatively.
//
// Best-effort: returns false (never throws) on any failure -- backend not
// up, wrong credentials, an existing IP lockout the login itself can't
// clear (see the "known limitation" note in playwright-global-setup.ts).
// Callers should log a warning and continue, not fail the test run.
export async function resetBackendRateLimits(
  backendBase: string,
  code: string = "SYSADMIN2026",
): Promise<boolean> {
  try {
    const loginRes = await fetch(`${backendBase}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    if (!loginRes.ok) return false;
    const { token } = (await loginRes.json()) as { token: string };
    const resetRes = await fetch(`${backendBase}/api/system/reset-rate-limits`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    return resetRes.ok;
  } catch {
    return false;
  }
}
