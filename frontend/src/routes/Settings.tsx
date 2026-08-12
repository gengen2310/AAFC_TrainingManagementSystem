import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { authApi, orgApi } from "../api";
import { Card, Button, Loading, ErrorNote } from "../components/ui";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { isAdmin } from "../auth/permissions";
import type { UserRecord } from "../api/types";

const ROLE_LABELS: Record<string, string> = {
  sqn_general: "SQN General", sqn_admin: "SQN Admin",
  wing_viewer: "Wing Viewer", wing_admin: "Wing Admin",
  national_viewer: "NAT Viewer", national_admin: "NAT Admin",
  system_admin: "System", auditor: "Auditor",
};

function roleBadge(role: string) {
  const cls = role.startsWith("sqn") ? "badge blue"
    : role.startsWith("wing") ? "badge ok"
    : (role.startsWith("national") || role === "system_admin") ? "badge warn"
    : "badge muted";
  return <span className={cls}>{ROLE_LABELS[role] ?? role}</span>;
}

function unitLabel(u: UserRecord): string {
  if (u.squadron_code) return `SQN ${u.squadron_code}`;
  if (u.wing_code) return `Wing ${u.wing_code}`;
  if (u.national_id) return "NAT HQ";
  return "—";
}

export function Settings() {
  const { session } = useAuth();

  // ── Self-service: change own code ──────────────────────────────────────────
  const [selfNew, setSelfNew] = useState("");
  const [selfConfirm, setSelfConfirm] = useState("");
  const [selfMsg, setSelfMsg] = useState("");
  const [selfErr, setSelfErr] = useState("");

  const selfChange = useMutation({
    mutationFn: () => authApi.changeCode(session!.user_id, selfNew),
    onSuccess: () => {
      setSelfMsg("Access code updated.");
      setSelfNew(""); setSelfConfirm(""); setSelfErr("");
    },
    onError: (e) => {
      setSelfMsg("");
      setSelfErr(e instanceof ApiError ? e.friendly : "Could not update code.");
    },
  });

  const mismatch = selfConfirm.length > 0 && selfNew !== selfConfirm;
  const selfDisabled = !selfNew.trim() || selfNew !== selfConfirm || selfChange.isPending;

  // ── Admin: reset another user's code ──────────────────────────────────────
  const [selected, setSelected] = useState<UserRecord | null>(null);
  const [filter, setFilter] = useState("");
  const [newCode, setNewCode] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const { data: users, isLoading, error: loadErr } = useQuery({
    queryKey: ["users"],
    queryFn: orgApi.users,
    enabled: isAdmin(session),
  });

  const reset = useMutation({
    mutationFn: () => authApi.changeCode(selected!.user_id, newCode),
    onSuccess: () => {
      setErr("");
      setMsg(`Access code reset for ${selected!.display_name}. Share the new code directly with the user.`);
      setNewCode("");
      setSelected(null);
    },
    onError: (e) => {
      setMsg(""); setErr(e instanceof ApiError ? e.friendly : "Could not reset code.");
    },
  });

  const q = filter.toLowerCase();
  const filtered = (users ?? []).filter((u) =>
    !q
    || u.display_name.toLowerCase().includes(q)
    || u.role.includes(q)
    || (u.squadron_code ?? "").toLowerCase().includes(q)
    || (u.wing_code ?? "").toLowerCase().includes(q),
  );

  function selectUser(u: UserRecord) { setSelected(u); setNewCode(""); setMsg(""); setErr(""); }
  function cancelReset() { setSelected(null); setNewCode(""); setMsg(""); setErr(""); }

  return (
    <div>
      <h1>Access Codes</h1>

      {/* ── Self-service card ── always visible ── */}
      <Card title="Change my access code">
        <p className="muted" style={{ marginBottom: 12 }}>
          Change your own access code. The current code is not required. The previous code cannot
          be recovered once changed.
        </p>
        <div className="form" style={{ maxWidth: 340 }}>
          <label htmlFor="sc-new">New access code</label>
          <input
            id="sc-new"
            type="password"
            value={selfNew}
            onChange={(e) => { setSelfNew(e.target.value); setSelfMsg(""); setSelfErr(""); }}
            autoComplete="new-password"
            placeholder="Enter new code"
          />
          <label htmlFor="sc-confirm">Confirm new code</label>
          <input
            id="sc-confirm"
            type="password"
            value={selfConfirm}
            onChange={(e) => { setSelfConfirm(e.target.value); setSelfMsg(""); setSelfErr(""); }}
            autoComplete="new-password"
            placeholder="Repeat new code"
            aria-invalid={mismatch || undefined}
          />
          {mismatch && <div className="field-err" role="alert">Codes do not match.</div>}
          {selfErr && <div className="errnote" role="alert">{selfErr}</div>}
          {selfMsg && <div className="okmsg" role="status">{selfMsg}</div>}
          <div style={{ marginTop: 6 }}>
            <Button onClick={() => selfChange.mutate()} disabled={selfDisabled}>
              {selfChange.isPending ? "Saving…" : "Change code"}
            </Button>
          </div>
        </div>
      </Card>

      {/* ── Admin section ── user directory + reset ── */}
      {isAdmin(session) && (
        <>
          <Card title="User directory">
            <p className="muted" style={{ marginBottom: 12 }}>
              Select a user to reset their access code. The previous code cannot be recovered once
              a reset is applied. You may only reset users within your authorised scope.
            </p>
            <div className="filter-bar" style={{ marginBottom: 10 }}>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter by name, role, or unit…"
                aria-label="Filter users"
                style={{ flex: 1 }}
              />
              {filter && <Button variant="out" onClick={() => setFilter("")}>Clear</Button>}
            </div>

            {isLoading && <Loading />}
            {loadErr && <ErrorNote error={loadErr} />}
            {!isLoading && !loadErr && filtered.length === 0 && (
              <div className="empty">
                {users?.length === 0 ? "No users in scope." : "No users match the filter."}
              </div>
            )}

            {!isLoading && filtered.length > 0 && (
              <table className="cmp-table" style={{ fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 700 }}>Name</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 700 }}>Role</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", fontWeight: 700 }}>Unit</th>
                    <th style={{ padding: "6px 8px" }} />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => (
                    <tr
                      key={u.user_id}
                      style={selected?.user_id === u.user_id
                        ? { background: "var(--surface-2, #eef2f7)" }
                        : undefined}
                    >
                      <td style={{ padding: "6px 8px", fontWeight: 600 }}>{u.display_name}</td>
                      <td style={{ padding: "6px 8px" }}>{roleBadge(u.role)}</td>
                      <td style={{ padding: "6px 8px", color: "var(--muted-text)", fontSize: 12 }}>
                        {unitLabel(u)}
                      </td>
                      <td style={{ padding: "6px 8px", textAlign: "right" }}>
                        <button
                          className="btn out sm"
                          onClick={() => selectUser(u)}
                          aria-pressed={selected?.user_id === u.user_id}
                        >
                          {selected?.user_id === u.user_id ? "Selected" : "Select"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {msg && <div className="okmsg" role="status" style={{ marginTop: 10 }}>{msg}</div>}
          </Card>

          {selected && (
            <Card title={`Reset code — ${selected.display_name}`}>
              <p className="muted" style={{ marginBottom: 10 }}>
                {roleBadge(selected.role)}
                <span style={{ marginLeft: 8, fontSize: 12 }}>{unitLabel(selected)}</span>
              </p>
              <div className="form" style={{ maxWidth: 340 }}>
                <label htmlFor="cc-code">New access code</label>
                <input
                  id="cc-code"
                  type="password"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value)}
                  autoComplete="new-password"
                  placeholder="Enter new code"
                />
                {err && <div className="errnote" role="alert">{err}</div>}
                <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                  <Button onClick={() => reset.mutate()} disabled={!newCode.trim() || reset.isPending}>
                    {reset.isPending ? "Saving…" : "Reset code"}
                  </Button>
                  <Button variant="out" onClick={cancelReset}>Cancel</Button>
                </div>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
