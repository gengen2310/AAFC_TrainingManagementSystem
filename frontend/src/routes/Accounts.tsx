import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { accountApi, orgApi, trainingApi } from "../api";
import type { TagRecord, PhaseRecord } from "../api";
import { friendlyMessage } from "../api/client";
import { Card, Empty, Loading, ErrorNote } from "../components/ui";
import { useAuth } from "../auth/AuthProvider";
import type { AccountRecord, Flight } from "../api/types";

const ROLE_LABELS: Record<string, string> = {
  sqn_general: "SQN General", sqn_admin: "SQN Admin",
  wing_viewer: "Wing Viewer", wing_admin: "Wing Admin",
  national_viewer: "NAT Viewer", national_admin: "NAT Admin",
  system_admin: "System Admin", auditor: "Auditor",
};
const SCOPE_LABELS: Record<string, string> = { squadron: "SQN", wing: "Wing", national: "NAT HQ" };
const WRITE_ROLES = new Set(["sqn_admin", "wing_admin", "national_admin", "system_admin"]);
const CREATE_ROLES: Record<string, string[]> = {
  system_admin: ["system_admin","national_admin","national_viewer","auditor","wing_admin","wing_viewer","sqn_admin","sqn_general"],
  national_admin: ["national_admin","national_viewer","auditor","wing_admin","wing_viewer","sqn_admin","sqn_general"],
  wing_admin: ["wing_viewer","sqn_admin","sqn_general"],
  sqn_admin: ["sqn_general"],
};
// Mirrors backend _CREATE_AUTHORITY / _scope_type (app/routers/accounts.py) --
// same "which roles can this actor assign" map used for account creation
// applies to change-role too, further filtered to the target's own scope
// type below (change-role never crosses scope levels).
const NATIONAL_SCOPE_ROLES = new Set(["national_admin", "national_viewer", "system_admin", "auditor"]);
const WING_SCOPE_ROLES_SET = new Set(["wing_viewer", "wing_admin"]);
function roleScopeType(role: string): string {
  if (NATIONAL_SCOPE_ROLES.has(role)) return "national";
  if (WING_SCOPE_ROLES_SET.has(role)) return "wing";
  return "squadron";
}
function isLocked(a: AccountRecord): boolean {
  return !!a.locked_until && new Date(a.locked_until) > new Date();
}

// One-time code display modal — code shown once; never retrievable after close
function NewCodeModal({ code, forName, onClose }: { code: string; forName: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = () => { navigator.clipboard.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }); };
  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="New access code">
      <div className="modal-box" style={{ maxWidth: 440 }}>
        <h2 style={{ marginTop: 0 }}>New Access Code</h2>
        <div className="alert warn" style={{ fontWeight: 700, marginBottom: 12 }}>
          This code will not be shown again. Copy it now before closing this window.
        </div>
        <div style={{ background: "#1a1a2e", color: "#7efff5", fontFamily: "monospace", fontSize: 22,
          fontWeight: 900, letterSpacing: 4, textAlign: "center", padding: "18px 12px",
          borderRadius: 8, userSelect: "all", marginBottom: 12 }}>{code}</div>
        <p className="muted" style={{ textAlign: "center", fontSize: 12 }}>For: <strong>{forName}</strong></p>
        <button className="btn out" style={{ width: "100%", marginBottom: 6 }} onClick={copy}>
          {copied ? "Copied!" : "Copy to clipboard"}
        </button>
        <div className="modal-foot">
          <button className="btn primary" onClick={onClose}>I have noted this code</button>
        </div>
      </div>
    </div>
  );
}

export function Accounts() {
  const { session } = useAuth();
  const qc = useQueryClient();
  const canWrite = WRITE_ROLES.has(session?.role ?? "");

  // Filters
  const [wingFilter, setWingFilter] = useState("");
  const [sqnFilter, setSqnFilter] = useState("");
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  // Queries
  const accounts = useQuery({
    queryKey: ["accounts", wingFilter, sqnFilter, includeArchived],
    queryFn: () => accountApi.list({ wing_id: wingFilter || undefined, squadron_id: sqnFilter || undefined, include_archived: includeArchived }),
  });
  const flights = useQuery({ queryKey: ["flights"], queryFn: () => accountApi.flights() });
  const wings = useQuery({ queryKey: ["wings"], queryFn: orgApi.wings });
  const squadrons = useQuery({ queryKey: ["squadrons"], queryFn: orgApi.squadrons });

  // One-time code display
  const [newCode, setNewCode] = useState<{ code: string; forName: string } | null>(null);

  // Create account form state
  const [showCreate, setShowCreate] = useState(false);
  const [createRole, setCreateRole] = useState("");
  const [createName, setCreateName] = useState("");
  const [createWing, setCreateWing] = useState(session?.wing_id ?? "");
  const [createSqn, setCreateSqn] = useState(session?.squadron_id ?? "");
  const [createFlight, setCreateFlight] = useState("");
  const [createCodeMode, setCreateCodeMode] = useState<"auto" | "manual">("auto");
  const [createManualCode, setCreateManualCode] = useState("");
  const [createErr, setCreateErr] = useState("");

  // Reset code form state
  const [resetUid, setResetUid] = useState<string | null>(null);
  const [resetMode, setResetMode] = useState<"auto" | "manual">("auto");
  const [resetManual, setResetManual] = useState("");

  // Edit account form state
  const [editUid, setEditUid] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editFlight, setEditFlight] = useState("");

  // Change role form state (REM-46)
  const [roleUid, setRoleUid] = useState<string | null>(null);
  const [roleValue, setRoleValue] = useState("");
  const [roleErr, setRoleErr] = useState("");

  // Permanent-delete confirmation state (REM-46)
  const [deleteUid, setDeleteUid] = useState<string | null>(null);
  const [deleteErr, setDeleteErr] = useState("");

  // Rename flight form state
  const [renameFid, setRenameFid] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");

  // Create flight form state
  const [showCreateFlight, setShowCreateFlight] = useState(false);
  const [flightName, setFlightName] = useState("");
  const [flightSqn, setFlightSqn] = useState(session?.squadron_id ?? "");

  // Mutations
  const createMut = useMutation({
    mutationFn: accountApi.create,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      setShowCreate(false);
      setNewCode({ code: data.new_code, forName: data.display_name });
    },
    onError: (e: Error) => setCreateErr(friendlyMessage(e, "Request failed.")),
  });
  const resetMut = useMutation({
    mutationFn: ({ uid, code }: { uid: string; code?: string }) => accountApi.resetCode(uid, code),
    onSuccess: (data, vars) => {
      const acct = (accounts.data ?? []).find(a => a.user_id === vars.uid);
      qc.invalidateQueries({ queryKey: ["accounts"] });
      setResetUid(null);
      setNewCode({ code: data.new_code, forName: acct?.display_name ?? vars.uid });
    },
  });
  const disableMut = useMutation({
    mutationFn: accountApi.disable,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
  const reactivateMut = useMutation({
    mutationFn: accountApi.reactivate,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
  const editMut = useMutation({
    mutationFn: ({ uid, body }: { uid: string; body: { display_name?: string; flight_id?: string } }) =>
      accountApi.update(uid, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setEditUid(null); },
  });
  // REM-46: archive/restore/permanent-delete/change-role/unlock parity with connected-frontend
  const archiveMut = useMutation({
    mutationFn: ({ uid, reason }: { uid: string; reason?: string }) => accountApi.archive(uid, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
  const restoreMut = useMutation({
    mutationFn: accountApi.restore,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
  const deleteMut = useMutation({
    mutationFn: accountApi.remove,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setDeleteUid(null); setDeleteErr(""); },
    onError: (e: Error) => setDeleteErr(friendlyMessage(e, "Request failed.")),
  });
  const unlockMut = useMutation({
    mutationFn: accountApi.unlock,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
  const changeRoleMut = useMutation({
    mutationFn: ({ uid, new_role }: { uid: string; new_role: string }) => accountApi.changeRole(uid, new_role),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["accounts"] }); setRoleUid(null); setRoleErr(""); },
    onError: (e: Error) => setRoleErr(friendlyMessage(e, "Request failed.")),
  });
  const createFlightMut = useMutation({
    mutationFn: accountApi.createFlight,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["flights"] }); setShowCreateFlight(false); },
  });
  const renameFlightMut = useMutation({
    mutationFn: ({ fid, name }: { fid: string; name: string }) => accountApi.renameFlight(fid, { name }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["flights"] }); setRenameFid(null); },
  });
  const archiveFlightMut = useMutation({
    mutationFn: accountApi.archiveFlight,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["flights"] });
      qc.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  const filteredAccounts = (accounts.data ?? []).filter(a => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (a.display_name ?? "").toLowerCase().includes(s) ||
      (a.role ?? "").includes(s) ||
      (a.squadron_code ?? "").toLowerCase().includes(s) ||
      (a.scope_type ?? "").includes(s);
  });

  const sqnsForWing = (wid: string) => (squadrons.data ?? []).filter(s => !wid || s.wing_id === wid);
  const flightsForSqn = (sid: string) => (flights.data ?? []).filter(f => f.squadron_id === sid);

  const allowedRoles = CREATE_ROLES[session?.role ?? ""] ?? [];
  const sqnScopeRoles = new Set(["sqn_general", "sqn_admin"]);
  const wingScopeRoles = new Set(["wing_viewer", "wing_admin"]);

  const openEdit = (a: AccountRecord) => {
    setEditUid(a.user_id);
    setEditName(a.display_name);
    setEditFlight(a.flight_id ?? "");
  };

  return (
    <div>
      <h1>Account Management</h1>

      {/* Filters */}
      <Card title="Accounts">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          <input placeholder="Search by name, role, unit…" value={search}
            onChange={e => setSearch(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
          {(session?.is_national) && (
            <select value={wingFilter} onChange={e => { setWingFilter(e.target.value); setSqnFilter(""); }}>
              <option value="">— all wings —</option>
              {(wings.data ?? []).map(w => <option key={w.wing_id} value={w.wing_id}>{w.code}</option>)}
            </select>
          )}
          {(session?.is_national || session?.is_wing) && (
            <select value={sqnFilter} onChange={e => setSqnFilter(e.target.value)}>
              <option value="">— all squadrons —</option>
              {sqnsForWing(wingFilter).map(s => <option key={s.squadron_id} value={s.squadron_id}>{s.code}</option>)}
            </select>
          )}
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <input type="checkbox" checked={includeArchived} onChange={e => setIncludeArchived(e.target.checked)} />
            Show archived
          </label>
          {canWrite && <button className="btn primary sm" onClick={() => { setShowCreate(true); setCreateErr(""); }}>+ Add Account</button>}
        </div>

        {accounts.isLoading ? <Loading /> : accounts.error ? <ErrorNote error={accounts.error} /> :
          filteredAccounts.length === 0 ? <Empty msg="No accounts match." /> : (
            <table>
              <caption className="vis-hidden">Accounts</caption>
              <thead>
                <tr>
                  <th>Name</th><th>Role</th><th>Scope</th><th>Unit</th>
                  <th>Status</th><th>Last Login</th>
                  {canWrite && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {filteredAccounts.map(a => (
                  <tr key={a.user_id}>
                    <td><strong>{a.display_name}</strong></td>
                    <td><span className="badge">{ROLE_LABELS[a.role] ?? a.role}</span></td>
                    <td><span className="badge">{SCOPE_LABELS[a.scope_type] ?? a.scope_type}</span></td>
                    <td className="muted" style={{ fontSize: 11 }}>
                      {a.squadron_code ? `SQN ${a.squadron_code}` : a.wing_code ? `Wing ${a.wing_code}` : "NAT HQ"}
                    </td>
                    <td>
                      {a.is_archived ? <span className="badge muted">Archived</span>
                        : a.active_status ? <span className="badge ok">Active</span> : <span className="badge warn">Disabled</span>}
                      {isLocked(a) && <span className="badge warn" style={{ marginLeft: 4 }}>Locked</span>}
                    </td>
                    <td style={{ fontSize: 11 }}>
                      {a.last_login_at ? new Date(a.last_login_at).toLocaleDateString("en-AU") : "Never"}
                    </td>
                    {canWrite && (
                      <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                        {!a.is_archived && <button className="btn sm" onClick={() => openEdit(a)}>Edit</button>}
                        {!a.is_archived && (
                          <button className="btn sm" onClick={() => { setResetUid(a.user_id); setResetMode("auto"); setResetManual(""); }}>
                            Reset code
                          </button>
                        )}
                        {!a.is_archived && (
                          <button className="btn sm" onClick={() => { setRoleUid(a.user_id); setRoleValue(a.role); setRoleErr(""); }}>
                            Change role
                          </button>
                        )}
                        {isLocked(a) && (
                          <button className="btn sm" onClick={() => unlockMut.mutate(a.user_id)}>Unlock</button>
                        )}
                        {!a.is_archived && (a.active_status
                          ? <button className="btn sm danger" onClick={() => { if (window.confirm(`Disable ${a.display_name}?`)) disableMut.mutate(a.user_id); }}>Disable</button>
                          : <button className="btn sm ok" onClick={() => reactivateMut.mutate(a.user_id)}>Reactivate</button>)}
                        {!a.is_archived && (
                          <button className="btn sm danger" onClick={() => { if (window.confirm(`Archive ${a.display_name}? This can be undone via Restore.`)) archiveMut.mutate({ uid: a.user_id, reason: undefined }); }}>
                            Archive
                          </button>
                        )}
                        {a.is_archived && (
                          <button className="btn sm ok" onClick={() => restoreMut.mutate(a.user_id)}>Restore</button>
                        )}
                        {a.is_archived && (
                          <button className="btn sm danger" onClick={() => { setDeleteUid(a.user_id); setDeleteErr(""); }}>
                            Delete permanently
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>

      {/* Flights card */}
      {canWrite && (
        <Card title="Flights (local groupings)">
          <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            Flights are local display groupings within a squadron. They do not change permissions or tenancy.
          </p>
          <button className="btn primary sm" style={{ marginBottom: 12 }} onClick={() => { setShowCreateFlight(true); setFlightName(""); setFlightSqn(session?.squadron_id ?? ""); }}>
            + Add Flight
          </button>
          {flights.isLoading ? <Loading /> : (flights.data ?? []).length === 0 ? <Empty msg="No flights." /> : (
            <table>
              <caption className="vis-hidden">Flights</caption>
              <thead><tr><th>Name</th><th>Squadron</th><th>Actions</th></tr></thead>
              <tbody>
                {(flights.data ?? []).map((f: Flight) => (
                  <tr key={f.flight_id}>
                    <td><strong>{f.name}</strong></td>
                    <td className="muted" style={{ fontSize: 11 }}>{f.squadron_code ?? f.squadron_name ?? "—"}</td>
                    <td style={{ display: "flex", gap: 4 }}>
                      <button className="btn sm" onClick={() => { setRenameFid(f.flight_id); setRenameName(f.name); }}>Rename</button>
                      <button className="btn sm danger" onClick={() => {
                        if (window.confirm(`Archive flight "${f.name}"? Users assigned to it will be unassigned.`))
                          archiveFlightMut.mutate(f.flight_id);
                      }}>Archive</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      )}

      {canWrite && <ReferenceDataCard />}

      {/* Create account modal */}
      {showCreate && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Create account">
          <div className="modal-box">
            <h2 style={{ marginTop: 0 }}>Add Account</h2>
            <label>Display Name<input value={createName} onChange={e => setCreateName(e.target.value)} /></label>
            <label>Role
              <select value={createRole} onChange={e => { setCreateRole(e.target.value); setCreateFlight(""); }}>
                <option value="">— select role —</option>
                {allowedRoles.map(r => <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>)}
              </select>
            </label>
            {(wingScopeRoles.has(createRole) || sqnScopeRoles.has(createRole)) && (
              <label>Wing
                <select value={createWing} onChange={e => { setCreateWing(e.target.value); setCreateSqn(""); }}
                  disabled={session?.is_wing && !session?.is_national}>
                  <option value="">— select wing —</option>
                  {(wings.data ?? []).map(w => <option key={w.wing_id} value={w.wing_id}>{w.code}</option>)}
                </select>
              </label>
            )}
            {sqnScopeRoles.has(createRole) && (
              <label>Squadron
                <select value={createSqn} onChange={e => { setCreateSqn(e.target.value); setCreateFlight(""); }}
                  disabled={!!session?.squadron_id}>
                  <option value="">— select squadron —</option>
                  {sqnsForWing(createWing).map(s => <option key={s.squadron_id} value={s.squadron_id}>{s.code}</option>)}
                </select>
              </label>
            )}
            {sqnScopeRoles.has(createRole) && createSqn && (
              <label>Flight (optional)
                <select value={createFlight} onChange={e => setCreateFlight(e.target.value)}>
                  <option value="">— no flight —</option>
                  {flightsForSqn(createSqn).map(f => <option key={f.flight_id} value={f.flight_id}>{f.name}</option>)}
                </select>
              </label>
            )}
            <div style={{ margin: "10px 0" }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="radio" name="code-mode" value="auto" checked={createCodeMode === "auto"} onChange={() => setCreateCodeMode("auto")} />
                Generate new access code (recommended)
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="radio" name="code-mode" value="manual" checked={createCodeMode === "manual"} onChange={() => setCreateCodeMode("manual")} />
                Set access code manually
              </label>
              {createCodeMode === "manual" && (
                <input type="password" placeholder="New code (min 6 chars)" autoComplete="new-password"
                  value={createManualCode} onChange={e => setCreateManualCode(e.target.value)} />
              )}
            </div>
            {createErr && <p className="error">{createErr}</p>}
            <div className="modal-foot">
              <button className="btn out" onClick={() => setShowCreate(false)}>Cancel</button>
              <button className="btn primary" disabled={createMut.isPending} onClick={() => {
                if (!createName.trim()) { setCreateErr("Display name is required."); return; }
                if (!createRole) { setCreateErr("Select a role."); return; }
                if (sqnScopeRoles.has(createRole) && !createSqn) { setCreateErr("Select a squadron."); return; }
                setCreateErr("");
                createMut.mutate({
                  display_name: createName.trim(),
                  role: createRole,
                  wing_id: createWing || undefined,
                  squadron_id: createSqn || undefined,
                  flight_id: createFlight || undefined,
                  new_code: createCodeMode === "manual" ? createManualCode : undefined,
                });
              }}>
                {createMut.isPending ? "Creating…" : "Create Account"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset code modal */}
      {resetUid && (() => {
        const acct = (accounts.data ?? []).find(a => a.user_id === resetUid);
        return (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Reset access code">
            <div className="modal-box" style={{ maxWidth: 420 }}>
              <h2 style={{ marginTop: 0 }}>Reset Access Code</h2>
              <p className="muted">Account: <strong>{acct?.display_name ?? resetUid}</strong></p>
              <div className="alert warn" style={{ fontSize: 12, marginBottom: 10 }}>
                The existing code will be invalidated immediately.
              </div>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="radio" name="reset-mode" value="auto" checked={resetMode === "auto"} onChange={() => setResetMode("auto")} />
                Generate new access code (recommended)
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input type="radio" name="reset-mode" value="manual" checked={resetMode === "manual"} onChange={() => setResetMode("manual")} />
                Set new access code manually
              </label>
              {resetMode === "manual" && (
                <input type="password" placeholder="New code" autoComplete="new-password"
                  value={resetManual} onChange={e => setResetManual(e.target.value)} />
              )}
              <div className="modal-foot">
                <button className="btn out" onClick={() => setResetUid(null)}>Cancel</button>
                <button className="btn primary" disabled={resetMut.isPending} onClick={() =>
                  resetMut.mutate({ uid: resetUid, code: resetMode === "manual" ? resetManual : undefined })
                }>
                  {resetMut.isPending ? "Resetting…" : "Reset access code"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Edit account modal */}
      {editUid && (() => {
        const acct = (accounts.data ?? []).find(a => a.user_id === editUid);
        const sqnFlights = acct?.squadron_id ? flightsForSqn(acct.squadron_id) : [];
        return (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Edit account">
            <div className="modal-box" style={{ maxWidth: 380 }}>
              <h2 style={{ marginTop: 0 }}>Edit Account</h2>
              <label>Display Name<input value={editName} onChange={e => setEditName(e.target.value)} /></label>
              {acct?.scope_type === "squadron" && sqnFlights.length > 0 && (
                <label>Flight (optional)
                  <select value={editFlight} onChange={e => setEditFlight(e.target.value)}>
                    <option value="">— no flight —</option>
                    {sqnFlights.map(f => <option key={f.flight_id} value={f.flight_id}>{f.name}</option>)}
                  </select>
                </label>
              )}
              <div className="modal-foot">
                <button className="btn out" onClick={() => setEditUid(null)}>Cancel</button>
                <button className="btn primary" disabled={editMut.isPending} onClick={() => {
                  const body: { display_name?: string; flight_id?: string } = {};
                  if (editName.trim()) body.display_name = editName.trim();
                  if (acct?.scope_type === "squadron") body.flight_id = editFlight;
                  editMut.mutate({ uid: editUid, body });
                }}>
                  {editMut.isPending ? "Saving…" : "Save Changes"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Change role modal (REM-46) */}
      {roleUid && (() => {
        const acct = (accounts.data ?? []).find(a => a.user_id === roleUid);
        const allowed = (CREATE_ROLES[session?.role ?? ""] ?? []).filter(
          r => acct && roleScopeType(r) === acct.scope_type,
        );
        return (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Change role">
            <div className="modal-box" style={{ maxWidth: 380 }}>
              <h2 style={{ marginTop: 0 }}>Change Role</h2>
              <p className="muted">Account: <strong>{acct?.display_name ?? roleUid}</strong></p>
              <p className="muted" style={{ fontSize: 12 }}>
                Only roles at the same scope level ({SCOPE_LABELS[acct?.scope_type ?? ""] ?? acct?.scope_type}) can be assigned here.
                Changing scope level requires archiving this account and creating a new one.
              </p>
              <label>New Role
                <select value={roleValue} onChange={e => setRoleValue(e.target.value)}>
                  {allowed.map(r => <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>)}
                </select>
              </label>
              {roleErr && <p className="error">{roleErr}</p>}
              <div className="modal-foot">
                <button className="btn out" onClick={() => setRoleUid(null)}>Cancel</button>
                <button className="btn primary" disabled={changeRoleMut.isPending || roleValue === acct?.role}
                  onClick={() => changeRoleMut.mutate({ uid: roleUid, new_role: roleValue })}>
                  {changeRoleMut.isPending ? "Saving…" : "Change Role"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Permanent delete confirmation (REM-46) */}
      {deleteUid && (() => {
        const acct = (accounts.data ?? []).find(a => a.user_id === deleteUid);
        return (
          <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Delete account permanently">
            <div className="modal-box" style={{ maxWidth: 420 }}>
              <h2 style={{ marginTop: 0 }}>Delete Account Permanently</h2>
              <p className="muted">Account: <strong>{acct?.display_name ?? deleteUid}</strong></p>
              <div className="alert warn" style={{ fontSize: 12, marginBottom: 10 }}>
                This cannot be undone. Only succeeds if the account has no audit or login
                history — otherwise it remains archived (the safe, reversible default).
              </div>
              {deleteErr && <p className="error">{deleteErr}</p>}
              <div className="modal-foot">
                <button className="btn out" onClick={() => { setDeleteUid(null); setDeleteErr(""); }}>Cancel</button>
                <button className="btn danger" disabled={deleteMut.isPending} onClick={() => deleteMut.mutate(deleteUid)}>
                  {deleteMut.isPending ? "Deleting…" : "Delete Permanently"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Rename flight modal */}
      {renameFid && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Rename flight">
          <div className="modal-box" style={{ maxWidth: 360 }}>
            <h2 style={{ marginTop: 0 }}>Rename Flight</h2>
            <label>Flight Name<input value={renameName} onChange={e => setRenameName(e.target.value)} /></label>
            <div className="modal-foot">
              <button className="btn out" onClick={() => setRenameFid(null)}>Cancel</button>
              <button className="btn primary" disabled={renameFlightMut.isPending} onClick={() =>
                renameFlightMut.mutate({ fid: renameFid, name: renameName.trim() })
              }>
                {renameFlightMut.isPending ? "Saving…" : "Rename Flight"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create flight modal */}
      {showCreateFlight && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Create flight">
          <div className="modal-box" style={{ maxWidth: 380 }}>
            <h2 style={{ marginTop: 0 }}>Add Flight</h2>
            <label>Flight Name<input value={flightName} onChange={e => setFlightName(e.target.value)} /></label>
            <label>Squadron
              <select value={flightSqn} onChange={e => setFlightSqn(e.target.value)}
                disabled={!!session?.squadron_id}>
                <option value="">— select squadron —</option>
                {(squadrons.data ?? []).map(s => <option key={s.squadron_id} value={s.squadron_id}>{s.code}</option>)}
              </select>
            </label>
            <p className="muted" style={{ fontSize: 12 }}>Flights are local display groupings only — they do not create separate permissions.</p>
            <div className="modal-foot">
              <button className="btn out" onClick={() => setShowCreateFlight(false)}>Cancel</button>
              <button className="btn primary" disabled={createFlightMut.isPending} onClick={() => {
                if (!flightName.trim() || !flightSqn) return;
                createFlightMut.mutate({ name: flightName.trim(), squadron_id: flightSqn });
              }}>
                {createFlightMut.isPending ? "Creating…" : "Create Flight"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* One-time new code display */}
      {newCode && <NewCodeModal code={newCode.code} forName={newCode.forName} onClose={() => setNewCode(null)} />}
    </div>
  );
}

// ── Reference Data (Training Stages / Facilitator Types / Subject Areas) ──
// "Respective to their scope" (risk-register submission) -- each admin role
// creates at its own natural scope: sqn_admin -> squadron, wing_admin ->
// wing, national_admin/system_admin -> national (tags call this "global").
// Mirrors connected-frontend's equivalent card exactly. Backed by the
// already-governed /api/curriculum/phases, /api/subject-area-tags,
// /api/facilitator-type-tags endpoints -- see backend/app/routers/
// training.py's _can_create_tag / _can_create_phase for the full scope/proxy
// rules this UI intentionally simplifies down to the common case.
type RefScope = "squadron" | "wing" | "national";
type RefItem = TagRecord | PhaseRecord;
interface RefConfig {
  key: "phase" | "factype" | "subjarea";
  label: string;
  list: () => Promise<RefItem[]>;
  create: (name: string, scope: RefScope) => Promise<unknown>;
  archive: (id: string) => Promise<unknown>;
  idOf: (item: RefItem) => string;
  scopeOf: (item: RefItem) => RefScope;
  wingIdOf: (item: RefItem) => string | null;
  squadronIdOf: (item: RefItem) => string | null;
}
function naturalRefScope(role: string | undefined): RefScope | null {
  if (role === "sqn_admin") return "squadron";
  if (role === "wing_admin") return "wing";
  if (role === "national_admin" || role === "system_admin") return "national";
  return null;
}
const REF_CONFIGS: RefConfig[] = [
  {
    key: "phase", label: "Training Stages",
    list: () => trainingApi.phases(),
    create: (name, scope) => trainingApi.createPhase(name, scope),
    archive: (id) => trainingApi.archivePhase(id),
    idOf: (i) => (i as PhaseRecord).phase_id,
    scopeOf: (i) => ((i as PhaseRecord).scope_level === "national" ? "national" : (i as PhaseRecord).scope_level) as RefScope,
    wingIdOf: (i) => (i as PhaseRecord).wing_id,
    squadronIdOf: (i) => (i as PhaseRecord).squadron_id,
  },
  {
    key: "factype", label: "Facilitator Types",
    list: () => trainingApi.facilitatorTypeTags() as unknown as Promise<RefItem[]>,
    create: (name, scope) => trainingApi.createFacilitatorTypeTag(name, scope === "national" ? "global" : scope),
    archive: (id) => trainingApi.archiveFacilitatorTypeTag(id),
    idOf: (i) => (i as TagRecord).tag_id,
    scopeOf: (i) => ((i as TagRecord).scope === "global" ? "national" : (i as TagRecord).scope) as RefScope,
    wingIdOf: (i) => (i as TagRecord).wing_id,
    squadronIdOf: (i) => (i as TagRecord).squadron_id,
  },
  {
    key: "subjarea", label: "Subject Areas",
    list: () => trainingApi.subjectAreaTags(),
    create: (name, scope) => trainingApi.createSubjectAreaTag(name, scope === "national" ? "global" : scope),
    archive: (id) => trainingApi.archiveSubjectAreaTag(id),
    idOf: (i) => (i as TagRecord).tag_id,
    scopeOf: (i) => ((i as TagRecord).scope === "global" ? "national" : (i as TagRecord).scope) as RefScope,
    wingIdOf: (i) => (i as TagRecord).wing_id,
    squadronIdOf: (i) => (i as TagRecord).squadron_id,
  },
];

function RefDataSection({ config, naturalScope, ownWingId, ownSquadronId }: {
  config: RefConfig; naturalScope: RefScope; ownWingId: string | null; ownSquadronId: string | null;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const q = useQuery({ queryKey: ["refdata", config.key], queryFn: config.list });

  const createMut = useMutation({
    mutationFn: () => config.create(name.trim(), naturalScope),
    onSuccess: () => { setName(""); setErr(null); qc.invalidateQueries({ queryKey: ["refdata", config.key] }); },
    onError: (e) => setErr(e),
  });
  const archiveMut = useMutation({
    mutationFn: (id: string) => config.archive(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["refdata", config.key] }),
  });

  const items = q.data ?? [];

  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 800, textTransform: "uppercase", letterSpacing: ".06em", marginBottom: 6 }}>
        {config.label}
      </div>
      {q.isLoading ? <Loading /> : items.length === 0 ? (
        <p className="muted" style={{ fontSize: 11 }}>None yet.</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
          {items.map((it) => {
            const scope = config.scopeOf(it);
            const mine = scope === naturalScope && (
              naturalScope === "national" ||
              (naturalScope === "wing" && config.wingIdOf(it) === ownWingId) ||
              (naturalScope === "squadron" && config.squadronIdOf(it) === ownSquadronId)
            );
            const label = "display_name" in it ? it.display_name : "";
            return (
              <span key={config.idOf(it)} className="badge" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                {label} <em className="muted" style={{ fontStyle: "normal", fontSize: 9 }}>{scope}</em>
                {mine && (
                  <button
                    onClick={() => { if (window.confirm("Archive this item? It will no longer appear in pickers, but existing records are unaffected.")) archiveMut.mutate(config.idOf(it)); }}
                    style={{ border: "none", background: "none", cursor: "pointer", color: "var(--danger)", fontSize: 11, padding: 0 }}
                    title="Archive"
                  >×</button>
                )}
              </span>
            );
          })}
        </div>
      )}
      <div style={{ display: "flex", gap: 6 }}>
        <input
          value={name} onChange={(e) => setName(e.target.value)}
          placeholder={`New ${config.label.replace(/s$/, "")} name…`}
          style={{ flex: 1, minWidth: 160 }}
        />
        <button className="btn sm primary" disabled={!name.trim() || createMut.isPending} onClick={() => createMut.mutate()}>
          {createMut.isPending ? "Adding…" : "+ Add"}
        </button>
      </div>
      {err != null && <ErrorNote error={err} />}
    </div>
  );
}

function ReferenceDataCard() {
  const { session } = useAuth();
  const naturalScope = naturalRefScope(session?.role);
  if (!naturalScope) return null;
  return (
    <Card title="Reference Data">
      <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        Training stages, facilitator types, and subject areas are created here at your own scope ({naturalScope}).
      </p>
      <div style={{ display: "grid", gap: 14 }}>
        {REF_CONFIGS.map((c) => (
          <RefDataSection
            key={c.key}
            config={c}
            naturalScope={naturalScope}
            ownWingId={session?.wing_id ?? null}
            ownSquadronId={session?.squadron_id ?? null}
          />
        ))}
      </div>
    </Card>
  );
}
