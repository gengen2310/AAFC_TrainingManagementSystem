import { useState } from "react";
import { useAuth } from "./AuthProvider";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { login } = useAuth();
  const [code, setCode] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr(""); setBusy(true);
    try { await login(code.trim()); }
    catch (e) { setErr(e instanceof ApiError ? e.friendly : "Invalid access code."); }
    finally { setBusy(false); }
  };

  return (
    <div className="login-wrap">
      <main id="main" className="login-box">
        <h1 style={{ textAlign: "center", color: "var(--aafc-dark-blue)", fontSize: 18 }}>
          AAFC Training<br />Management System
        </h1>
        <div className="login-rule" />
        <label htmlFor="code">Access code</label>
        <input id="code" type="password" value={code} autoComplete="off" autoFocus
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
          aria-describedby={err ? "login-err" : undefined} aria-invalid={!!err} />
        {err && <div id="login-err" role="alert" className="err">{err}</div>}
        <button className="btn" style={{ width: "100%" }} onClick={submit} disabled={busy || !code.trim()}>
          {busy ? "Checking…" : "Log in"}
        </button>
        <p className="login-foot">National deployable edition · supports training planning only — not a system of record.</p>
      </main>
    </div>
  );
}
