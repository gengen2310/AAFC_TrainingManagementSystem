import type { FullConfig } from "@playwright/test";
import { resetBackendRateLimits } from "./e2e-rate-limit-reset";

// DEFECT-004 (general-release qualification): clears the backend's general
// API rate limiter, DB-backed per-IP login limiter, and per-account lockout
// once before a full e2e run (see e2e-rate-limit-reset.ts for the actual
// call and its known limitations). Replaces "restart the backend" as the
// de facto reset procedure between local/CI test runs.
//
// Configure per environment via env vars (never hardcode a real credential
// here -- staging's system_admin code is managed separately and must be
// supplied by whoever runs the staging config):
//   E2E_BACKEND_BASE_URL  -- default http://localhost:8000 (local dev)
//   E2E_SYSADMIN_CODE     -- default SYSADMIN2026 (the local seed_all.py
//                            demo code; NOT valid against staging/production)
//
// A single reset here is necessary but not always sufficient for a long
// run: the general limiter's 300 req/60s budget can still be crossed
// partway through a heavy suite. Spec files that have shown this in
// practice add their own test.beforeAll() reset -- see
// e2e-connected/main-tms.spec.ts.
export default async function globalSetup(_config: FullConfig): Promise<void> {
  const backendBase = process.env.E2E_BACKEND_BASE_URL || "http://localhost:8000";
  const code = process.env.E2E_SYSADMIN_CODE || "SYSADMIN2026";
  const ok = await resetBackendRateLimits(backendBase, code);
  if (ok) {
    console.log(`[global-setup] rate limits and login lockouts reset on ${backendBase}.`);
  } else {
    console.warn(`[global-setup] could not reset rate limits on ${backendBase} -- continuing anyway (see e2e-rate-limit-reset.ts for known limitations).`);
  }
}
