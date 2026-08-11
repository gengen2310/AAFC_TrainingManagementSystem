import { useEffect, useMemo, useState } from "react";
import { useAuth } from "./AuthProvider";
import { authApi } from "../api";
import { ApiError, friendlyMessage } from "../api/client";
import type { LoginOrganisations, LoginUnitType } from "../api/types";

// REM-84: previously a single access-code field, sending POST /api/auth/login
// with no user_id -- this hits the backend's own documented "legacy scan-all
// path (used by tests; production always provides user_id via /lookup)",
// which has no per-account lockout tracking at all (only the shared IP-wide
// rate limiter applies). connected-frontend's 5-step flow (unit type -> wing
// -> squadron -> role -> code) exists specifically to resolve a user_id via
// /api/auth/lookup BEFORE calling /login, which is what gives the scoped,
// per-account lockout path (auth.py's _raise_if_locked/ac.failed_attempts).
// This was not just a UX inconsistency between the two frontends -- it was a
// real gap in which security path Planning Workspace's login actually took.
// Rebuilt here to collect the same fields and call the same two endpoints,
// closing that gap while keeping this page's own visual implementation
// (not a shared component/token source with connected-frontend).

type Step = "type" | "org" | "role" | "code";

const ROLES: Record<LoginUnitType, { value: string; label: string }[]> = {
  squadron: [{ value: "sqn_admin", label: "Admin" }, { value: "sqn_general", label: "Viewer" }],
  wing: [{ value: "wing_admin", label: "Admin" }, { value: "wing_viewer", label: "Viewer" }],
  national: [
    { value: "national_admin", label: "National Admin" },
    { value: "national_viewer", label: "National Viewer" },
    { value: "system_admin", label: "System Admin" },
    { value: "auditor", label: "Auditor" },
  ],
};

export function LoginPage() {
  const { login } = useAuth();
  const [orgs, setOrgs] = useState<LoginOrganisations | null>(null);
  const [orgsErr, setOrgsErr] = useState("");

  const [unitType, setUnitType] = useState<LoginUnitType | "">("");
  const [wingCode, setWingCode] = useState("");
  const [squadronCode, setSquadronCode] = useState("");
  const [role, setRole] = useState("");
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    authApi.organisations()
      .then(setOrgs)
      .catch((e) => setOrgsErr(friendlyMessage(e, "Could not load the unit list.")));
  }, []);

  const wings = orgs?.wings ?? [];
  const squadrons = useMemo(
    () => wings.find((w) => w.code === wingCode)?.squadrons ?? [],
    [wings, wingCode],
  );

  const identifier = unitType === "wing" ? wingCode : unitType === "squadron" ? squadronCode : undefined;
  const needsWing = unitType === "wing" || unitType === "squadron";
  const needsSquadron = unitType === "squadron";
  const roleOptions = unitType ? ROLES[unitType] : [];

  const step: Step = !unitType ? "type" : (needsWing && !identifier) ? "org" : !role ? "role" : "code";

  function resetFrom(next: Step) {
    setErr("");
    if (next === "type") { setWingCode(""); setSquadronCode(""); setRole(""); }
    if (next === "org") { setSquadronCode(""); setRole(""); }
    if (next === "role") { setRole(""); }
  }

  async function submit() {
    if (!unitType || !role || !code.trim()) return;
    setErr(""); setBusy(true);
    try {
      const { user_id } = await authApi.lookup(unitType, identifier, role);
      await login(code.trim(), user_id);
    } catch (e) {
      setErr(e instanceof ApiError ? e.friendly : "Invalid access code.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <main id="main" className="login-box">
        <h1 style={{ textAlign: "center", color: "var(--aafc-dark-blue)", fontSize: 18 }}>
          AAFC Training<br />Management System
        </h1>
        <div className="login-rule" />

        <label htmlFor="login-unit-type">Login as</label>
        <select
          id="login-unit-type"
          value={unitType}
          onChange={(e) => { setUnitType(e.target.value as LoginUnitType | ""); resetFrom("type"); }}
        >
          <option value="">Select…</option>
          <option value="squadron">Squadron</option>
          <option value="wing">Wing</option>
          <option value="national">National</option>
        </select>

        {needsWing && (
          <>
            <label htmlFor="login-wing">Wing</label>
            {orgsErr ? (
              <div id="login-err" role="alert" className="err">{orgsErr}</div>
            ) : (
              <select
                id="login-wing"
                value={wingCode}
                onChange={(e) => { setWingCode(e.target.value); resetFrom("org"); }}
              >
                <option value="">Select wing…</option>
                {wings.map((w) => <option key={w.code} value={w.code}>{w.name}</option>)}
              </select>
            )}
          </>
        )}

        {needsSquadron && wingCode && (
          <>
            <label htmlFor="login-squadron">Squadron / Unit</label>
            <select
              id="login-squadron"
              value={squadronCode}
              onChange={(e) => { setSquadronCode(e.target.value); resetFrom("role"); }}
            >
              <option value="">Select squadron…</option>
              {squadrons.length === 0 && <option value="" disabled>No squadrons configured for this wing yet</option>}
              {squadrons.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          </>
        )}

        {step !== "type" && step !== "org" && unitType && (
          <>
            <label htmlFor="login-role">Role</label>
            <select
              id="login-role"
              value={role}
              onChange={(e) => { setRole(e.target.value); setErr(""); }}
            >
              <option value="">Select…</option>
              {roleOptions.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </>
        )}

        {step === "code" && (
          <>
            <label htmlFor="code">Access code</label>
            <input id="code" type="password" value={code} autoComplete="off"
              onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
              aria-describedby={err ? "login-err" : undefined} aria-invalid={!!err} />
          </>
        )}

        {err && <div id="login-err" role="alert" className="err">{err}</div>}

        <button className="btn" style={{ width: "100%" }} onClick={submit}
          disabled={busy || step !== "code" || !code.trim()}>
          {busy ? "Checking…" : "Log in"}
        </button>
        <p className="login-foot">National deployable edition · supports training planning only — not a system of record.</p>
      </main>
    </div>
  );
}
